/** # deno esbuild server
 * ### about
 * this is a deno live-time-server (lts) that compiles the `GET` requested local filesystem file and
 * `Respond`s with the compiled javascript file as plain text string (with javascript mime type). <br>
 * 
 * ### cli
 * ```cmd
 * deno run -A "./deno_lts_esbuild.ts" --cwd="c:/my/project/folder/" --port="3000" --callback="http://localhost:8000/deno_lts_esbuild/loaded/"
 * ```
 * - `cwd`: set current working directory of this server. this is needed if your typescript files do relative imports
 *   - defaults to `"./"` (i.e. the directory where this script resides in)
 * - `port`: which localhost port to assign to this server for communication.
 *   - defaults to `"3000"`
 * - `callback`: call some server endpoint to inform them that this script's server has loaded and is ready to accept file compilation requests.
 *   - defaults to `undefined`
 * 
 * ### server json requests
 * - compile a file
 *   - see {@link RequestCompileFileBody}
 * - set cache of all files to dirty (hence requiring a forced re-compilation)
 *   - see {@link cacheDirtyServerPattern}, {@link cacheInfoServerPattern}
*/

import { parse as cliParse } from "https://deno.land/std@0.184.0/flags/mod.ts"
import { ConnInfo, serve } from "https://deno.land/std@0.184.0/http/server.ts"
import { join as pathJoin } from "https://deno.land/std@0.184.0/path/mod.ts"
import { BuildOptions as ESBuildOptions, OutputFile as ESOutputFile, Plugin as ESPlugin, build as esbuild, stop as esstop } from "https://deno.land/x/esbuild@v0.17.18/mod.js"
import { solidPlugin } from "https://esm.sh/esbuild-plugin-solid?external=esbuild"
import { denoPlugins } from "https://deno.land/x/esbuild_deno_loader@0.7.0/mod.ts"

export interface CliArgs {
	cwd?: string
	port?: number | string
	cache?: boolean | string
	callback?: string | URL
}

const cli_args = cliParse(Deno.args) as CliArgs
cli_args.cwd ??= "./"
cli_args.cwd = cli_args.cwd.startsWith(".") || cli_args.cwd.startsWith("/") || cli_args.cwd === "" ? pathJoin(Deno.cwd(), cli_args.cwd) : cli_args.cwd
cli_args.cache ??= true
cli_args.port = parseInt(cli_args.port ?? 3000)
console.debug("deno esbuild server was invoked with the following cli args:\n", cli_args)
Deno.chdir(cli_args.cwd)

const plugin_names = {
	"deno": denoPlugins,
	"solid": solidPlugin
} as const

const hashString = (str: string): string => {
	str = str.padEnd(13)
	let hash = 0n
	for (let i = 0, len = str.length; i < len; i++) {
		hash = (hash << 5n) - hash + BigInt(str.charCodeAt(i))
	}
	return BigUint64Array.of(hash)[0].toString(36)
}
const JSONstringifyOrdered = (obj: object, space?: string | number) => {
	const all_keys: Set<keyof typeof obj | string> = new Set()
	JSON.stringify(obj, (key, value) => (all_keys.add(key), value))
	return JSON.stringify(obj, Array.from(all_keys).sort(), space)
}
const hashObject: Hasher = (obj: object): string => {
	const obj_json = JSONstringifyOrdered(obj)
	return hashString(obj_json)
}

type Hasher = (config: RequestCompileFileBody) => string
type VirtualFile = {
	/** the resulting compiled javascript text as bytes */
	contents: ESOutputFile["contents"]
	/** `RequestCompileFileBody["path"]`'s last modified time (as a `Date`) */
	mtime: Deno.FileInfo["mtime"]
}
const build_cache: {
	[hash: ReturnType<Hasher>]: VirtualFile
} = {}

export type BuildOptions = Omit<ESBuildOptions, "entryPoints" | "outfile" | "outdir" | "write" | "plugins">

type JSONstringify<T extends Record<string | number, any> | Array<any>> = string

export interface RequestCompileFile extends Request {
	url: "/compile" | "/compile/"
	method: "POST" | "GET"
}

export interface RequestCompileFileInit extends RequestInit {
	method: "POST"
	headers: {
		"accept": "application/json, text/plain, */*",
		"content-type": "application/json",
	}
	body: JSONstringify<RequestCompileFileBody>
}

export interface RequestCompileFileBody {
	/** path: "./path/to/file.ts" */
	path: string
	/** config: esbuild_config_object */
	config?: BuildOptions
	plugins?: (keyof typeof plugin_names)[]
	plugins_config?: { [K in keyof typeof plugin_names]?: Parameters<(typeof plugin_names)[K]>[0] }
}

const requiredBuildOptions: Omit<ESBuildOptions, keyof BuildOptions> = {
	write: false
}

const defaultBuildOptions: BuildOptions = {
	bundle: true,
	minify: false,
	platform: "browser",
	format: "esm",
	target: "esnext",
	// you must mark every bare import as external, so that they can be handled by `denoPlugins` later throught the provided `importMapURL` option
	external: ["solid-js", "solid-js/web"],
	// disable tree-shaking if you encounter issues with proxy objects
	treeShaking: true,
}

const buildServerPattern = new URLPattern({ pathname: "/compile{/:query}?", protocol: "http{s}?" })
const buildServerPOST = async (request: RequestCompileFile): Promise<Response> => {
	if (request.method === "POST") {
		return buildServerObject(await request.json() as RequestCompileFileBody)
	}
	return new Response(
		"invalid method. only \"POST\" is accepted",
		{ status: 405 }
	)
}
const buildServerGET = (request: RequestCompileFile): Promise<Response> => {
	if (request.method === "GET") {
		const
			{ query } = buildServerPattern.exec(request.url)?.pathname.groups as { query: string },
			json_query = decodeURIComponent(query)
		return buildServerObject(JSON.parse(json_query) as RequestCompileFileBody)
	}
	return Promise.resolve(new Response(
		"invalid method. only \"GET\" is accepted",
		{ status: 405 }
	))
}
const buildServerSearchPattern = new URLPattern({ pathname: "/compile{/}?", protocol: "http{s}?", search: "path=:path{&}?{config=:config}?{&}?{plugins=:plugins}?{&}?{plugins_config=:plugins_config}?" })
const buildServerGETSearch = (request: RequestCompileFile): Promise<Response> => {
	if (request.method === "GET") {
		let { path, config = "{}", plugins = "[]", plugins_config = "{}" } = buildServerSearchPattern.exec(request.url)?.search.groups as { [K in keyof RequestCompileFileBody]: string }
		if (config === "") config = "{}"
		if (plugins === "") plugins = "[]"
		if (plugins_config === "") plugins_config = "{}"
		return buildServerObject({
			path: JSON.parse(decodeURIComponent(path)),
			config: JSON.parse(decodeURIComponent(config)),
			plugins: JSON.parse(decodeURIComponent(plugins)),
			plugins_config: JSON.parse(decodeURIComponent(plugins_config)),
		} as RequestCompileFileBody)
	}
	return Promise.resolve(new Response(
		"invalid method. only \"GET\" is accepted",
		{ status: 405 }
	))
}
const buildServerObject = async (build_query: RequestCompileFileBody): Promise<Response> => {
	const
		hash = hashObject(build_query),
		{ path, config, plugins = [], plugins_config = {} } = build_query
	let
		abspath = path, // pathJoin(cli_args.cwd!, path), // for now, abspath breaks some plugins, while relative path works with them all. so we choose the latter
		path_last_modified = new Date()
	try { path_last_modified = (await Deno.stat(abspath))?.mtime ?? path_last_modified }
	catch { }
	if (cli_args.cache && hash in build_cache) {
		const { contents, mtime } = build_cache[hash]
		if (!path_last_modified || !mtime) { }
		else if (path_last_modified.getTime() > mtime!.getTime()) { }
		else {
			console.debug("return cached query:")
			console.group()
			console.debug(build_query)
			console.groupEnd()
			return new Response(contents, {
				status: 200,
				headers: { "content-type": "text/javascript" }
			})
		}
	}
	console.debug("new build query:")
	console.group()
	console.debug(build_query)
	if (plugins.includes("deno")) abspath = path
	const plugins_to_include: Array<ESPlugin> = []
	for (const p_name of plugins) {
		let esplugin: ESPlugin | ESPlugin[] = plugin_names[p_name] instanceof Function ?
			plugin_names[p_name](plugins_config[p_name]) :
			plugin_names[p_name]
		if (!(esplugin instanceof Array)) esplugin = [esplugin]
		plugins_to_include.push(...esplugin)
	}
	const
		t0 = performance.now(),
		entryPoints = [abspath],
		{ outputFiles } = await esbuild({
			...defaultBuildOptions,
			...config,
			...requiredBuildOptions,
			plugins: plugins_to_include,
			entryPoints
		})
	if (outputFiles === undefined || outputFiles.length === 0) return new Response("no javascript output was produced", { status: 404 })
	const output_js = outputFiles[0]
	console.debug("compilation time:", performance.now() - t0, "ms")
	console.debug("binary size:", output_js.contents.byteLength / 1024, "kb")
	console.groupEnd()
	if (cli_args.cache) {
		build_cache[hash] = {
			contents: output_js.contents,
			mtime: path_last_modified
		}
	}
	return new Response(output_js.contents, {
		status: 200,
		headers: { "content-type": "text/javascript" }
	})
}

const cacheInfoServerPattern = new URLPattern({ pathname: "/cache{/}?", protocol: "http{s}?" })
const cacheInfoServer = (): Response => {
	const
		build_cache_text: { [hash: keyof typeof build_cache]: { mtime: Date | null, contents: string } } = {},
		text_decoder = new TextDecoder()
	let cache_size = 0
	for (const [hash, vfile] of Object.entries(build_cache)) {
		cache_size += vfile.contents.byteLength
		build_cache_text[hash] = { mtime: vfile.mtime, contents: text_decoder.decode(vfile.contents) }
	}
	cache_size /= 2 ** 20
	return Response.json({ cache_size: cache_size.toString() + " mb", cache: build_cache_text })
	//, {status: 200,headers: { "content-type": "application/json" }})
}

const cacheDirtyServerPattern = new URLPattern({ pathname: "/dirty{/}?", protocol: "http{s}?" })
const cacheDirtyServer = (): Response => {
	console.log("deleting cache")
	for (const hash in build_cache) {
		delete build_cache[hash]
	}
	return new Response()
}

const abort_controller = new AbortController()
const abortServerPattern = new URLPattern({ pathname: "/abort{/}?", protocol: "http{s}?" })
const abortServer = (request: Request & { url: "/abort" | "/abort/", method: "GET" | "POST" }): Response => {
	if (request.method === "GET" || request.method === "POST") {
		console.log("closing server...")
		abort_controller.abort("user request")
	}
	return new Response()
}

const helloServerPattern = new URLPattern({ pathname: "/hello{/}?", protocol: "http{s}?" })
const helloServer = (request: Request & { url: "/hello" | "/hello/", method: "GET" }, connection_info: ConnInfo): Response => {
	if (request.method === "GET") {
		const ip = connection_info.remoteAddr
		console.log(ip, "says Hi")
		return new Response("welcome to esbuild server", { status: 200 })
	}
	return new Response()
}

const serverRouter = (request: Request, connection_info: ConnInfo): Response | Promise<Response> => {
	const { method, url } = request
	if (buildServerSearchPattern.test(url)) return buildServerGETSearch(request)
	else if (buildServerPattern.test(url)) {
		if (method === "POST") return buildServerPOST(request)
		return buildServerGET(request)
	}
	else if (cacheInfoServerPattern.test(url)) return cacheInfoServer(request)
	else if (cacheDirtyServerPattern.test(url)) return cacheDirtyServer(request)
	else if (helloServerPattern.test(url)) return helloServer(request, connection_info)
	else if (abortServerPattern.test(url)) return abortServer(request)
	return new Response("invalid request", { status: 400 })
}

serve(serverRouter, {
	port: cli_args.port as number,
	signal: abort_controller.signal,
	onListen: ({ port, hostname }) => {
		console.log(`esbuilds server started at:\n\thttp://${hostname}:${port}`)
		if (cli_args.callback) {
			fetch(cli_args.callback, { method: "GET" })
		}
	}
}).then(() => {
	esstop()
	console.log("server closed")
})
