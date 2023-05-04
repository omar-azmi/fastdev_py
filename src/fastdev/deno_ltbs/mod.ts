/** TODO: update usage documentation to reflect the current version's syntax */
/** # deno build server
 * ### about
 * this is a deno live-time-build-server (ltbs) that compiles the `GET` requested local filesystem file and
 * `Respond`s with the compiled javascript file as plain text string (with javascript mime type). <br>
 * 
 * ### cli
 * ```cmd
 * deno run -A "./deno_ltbs.ts" --cwd="c:/my/project/folder/" --port="3000" --callback="http://localhost:8000/deno_ltbs/loaded/"
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
import { CacheStore, ConnInfo, RequestRoute, addressToIP, cliParse, config, serve } from "./deps.ts"
import { requestRouteGET as esbuildRequestRouteGET, requestRoutePOST as esbuildRequestRoutePOST, cache as esbuild_cache, esstop } from "./esbuild_builder.ts"
import { requestRouteGET as htmlbuildRequestRouteGET, requestRoutePOST as htmlbuildRequestRoutePOST, cache as htmlbuild_cache } from "./html_builder.ts"


const cli_args = cliParse(Deno.args)
config.cwd = cli_args.cwd ?? Deno.cwd()
if (cli_args.cache) config.cache = cli_args.cache === "false" ? false : true
if (cli_args.port) config.port = parseInt(cli_args.port)
if (cli_args.callback) config.callback = cli_args.callback
console.debug("deno build server was invoked with the following cli config:\n", cli_args)
console.debug("current config is:\n", config)
Deno.chdir(config.cwd!)


const cache_stores: CacheStore[] = [esbuild_cache, htmlbuild_cache]

const cacheSummary: RequestRoute = {
	methods: ["GET", "POST"],
	url_pattern: new URLPattern({
		protocol: "http{s}?",
		pathname: "/cache/info{/}?",
	}),
	handler: (): Response => {
		const cache_vfile_meta: { [hash: string]: { size: number, mtime?: Date | null } } = {}
		let total_cache_size = 0
		for (const cache_store of cache_stores) {
			for (const [hash, vfile] of Object.entries(cache_store)) {
				const byte_size = vfile.contents.byteLength ?? vfile.contents.length
				cache_vfile_meta[hash] = { size: byte_size, mtime: vfile.mtime }
				total_cache_size += byte_size
			}
		}
		total_cache_size /= 2 ** 20
		return Response.json({
			cache_size: total_cache_size.toString() + " mb",
			cache_store: cache_vfile_meta,
		})
	}
}

const cacheClear: RequestRoute = {
	methods: ["GET", "POST"],
	url_pattern: new URLPattern({
		protocol: "http{s}?",
		pathname: "/cache/clear{/}?",
	}),
	handler: (): Response => {
		for (const cache_store of cache_stores) {
			for (const hash in cache_store) {
				delete cache_store[hash]
			}
		}
		return new Response("cache cleared successfully")
	}
}

const sayHello: RequestRoute = {
	methods: ["GET", "POST"],
	url_pattern: new URLPattern({
		protocol: "http{s}?",
		pathname: "/hello{/}?",
	}),
	handler: (request, connection_info): Response => {
		const { localAddr, remoteAddr } = connection_info
		console.log(addressToIP(remoteAddr), "says Hi")
		return new Response(
			`welcome to deno live-time-build-server\nyour IP is: ${addressToIP(remoteAddr)}\nserver's IP is: ${addressToIP(localAddr)}`,
			{ status: 200 }
		)
	}
}

const abort_controller = new AbortController()
const abortServer: RequestRoute = {
	methods: ["GET", "POST"],
	url_pattern: new URLPattern({
		protocol: "http{s}?",
		pathname: "/abort{/}?",
	}),
	handler: (request, connection_info): Response => {
		const { remoteAddr } = connection_info
		console.log(addressToIP(remoteAddr), "requested abort")
		console.log("closing server...")
		abort_controller.abort("user request")
		return new Response()
	}
}

const request_routes: RequestRoute[] = [
	esbuildRequestRouteGET,
	esbuildRequestRoutePOST,
	htmlbuildRequestRouteGET,
	htmlbuildRequestRoutePOST,
	cacheSummary,
	cacheClear,
	sayHello,
	abortServer
]

const serverRouter = (request: Request, connection_info: ConnInfo): Response | Promise<Response> => {
	const { method, url } = request
	for (const route of request_routes) {
		if (route.methods.includes(method) && route.url_pattern.test(url)) {
			return route.handler(request, connection_info)
		}
	}
	return new Response("invalid request", { status: 400 })
}

serve(serverRouter, {
	port: config.port,
	signal: abort_controller.signal,
	onListen: ({ port, hostname }) => {
		console.log(`deno build server started at:\n\thttp://${hostname}:${port}`)
		if (config.callback) {
			fetch(config.callback, { method: "GET" })
		}
	}
}).then(() => {
	esstop()
	console.log("server closed")
})
