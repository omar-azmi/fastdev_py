import { BuildOptions as ESBuildConfig, OutputFile as ESOutputFile, Plugin as ESPlugin, build as esbuild, stop as esstop } from "https://deno.land/x/esbuild@v0.17.18/mod.js"
import { denoPlugins } from "https://deno.land/x/esbuild_deno_loader@0.7.0/mod.ts"
import { solidPlugin } from "https://esm.sh/esbuild-plugin-solid?external=esbuild"
import { CacheStore, DefaultJSONValues, Handler, RequestRoute, cacheableQuery_Factory, pathIsAbsolute, pathRelative, searchParamsToObject } from "./deps.ts"


export interface BuildQuery {
	/** path: "./path/to/file.ts" must be relative to current working directory */
	path: string
	/** config: esbuild_config_object */
	config?: BuildConfig
	/** names of the plugins to include */
	plugins?: (keyof typeof plugin_names)[]
	/** configurations of the plugins that are included */
	plugins_config?: { [K in keyof typeof plugin_names]?: Parameters<(typeof plugin_names)[K]>[0] }
}

export type BuildConfig = Omit<ESBuildConfig, "entryPoints" | "outfile" | "outdir" | "write" | "plugins">

const
	plugin_names = {
		"deno": denoPlugins,
		"solid": solidPlugin
	} as const,
	defaultBuildConfig: BuildConfig = {
		bundle: true,
		minify: false,
		platform: "browser",
		format: "esm",
		target: "esnext",
		// you must mark every bare import as external, so that they can be handled by `denoPlugins` later throught the provided `importMapURL` option
		external: ["solid-js", "solid-js/web"],
		// disable tree-shaking if you encounter issues with proxy objects
		treeShaking: true,
	},
	requiredBuildConfig: Omit<ESBuildConfig, keyof BuildConfig> = {
		write: false
	},
	defaultSearchParams: { [key in keyof BuildQuery]: DefaultJSONValues } = {
		path: "\"\"",
		config: "{}",
		plugins: "[]",
		plugins_config: "{}",
	}

const buildQuery = async (query: BuildQuery): Promise<Uint8Array | undefined> => {
	console.debug("new build query:")
	console.group()
	console.debug(query)
	const
		{ path, config, plugins = [], plugins_config = {} } = query,
		plugins_to_include: Array<ESPlugin> = []
	for (const p_name of plugins) {
		let esplugin: ESPlugin | ESPlugin[] = plugin_names[p_name] instanceof Function ?
			plugin_names[p_name](plugins_config[p_name]) :
			plugin_names[p_name]
		if (!(esplugin instanceof Array)) esplugin = [esplugin]
		plugins_to_include.push(...esplugin)
	}
	const
		t0 = performance.now(),
		entryPoints = [pathIsAbsolute(path) ? pathRelative("./", path) : path],
		{ outputFiles } = await esbuild({
			...defaultBuildConfig,
			...config,
			...requiredBuildConfig,
			plugins: plugins_to_include,
			entryPoints,
		})
	if (outputFiles === undefined || outputFiles.length === 0) return undefined
	const output_js = outputFiles[0]
	console.debug("compilation time:", performance.now() - t0, "ms")
	console.debug("binary size:", output_js.contents.byteLength / 1024, "kb")
	console.groupEnd()
	return output_js.contents
}

export const cache: CacheStore<Uint8Array> = {}

const cacheableBuildQuery = cacheableQuery_Factory(buildQuery, cache, {
	headers: {
		"content-type": "text/javascript"
	},
	error_response: {
		body: "no javascript output was produced",
		status: 404,
	}
})

const handleGETBuildQuery: Handler = (request) => {
	const query = searchParamsToObject<BuildQuery>(request.url, defaultSearchParams)
	return cacheableBuildQuery(query)
}

const handlePOSTBuildQuery: Handler = async (request) => {
	const query = await request.json() as BuildQuery
	return cacheableBuildQuery(query)
}

/** url search params must match `objectToSearchParams<BuildQuery>` */
export const requestRouteGET: RequestRoute = {
	methods: ["GET"],
	handler: handleGETBuildQuery,
	url_pattern: new URLPattern({
		protocol: "http{s}?",
		pathname: "/esbuild{/}?",
		search: undefined
	})
}

/** `Request.body` must be `JSON.stringify(query)` or `Request.json(query)`, where `let query: BuildQuery` */
export const requestRoutePOST: RequestRoute = {
	methods: ["POST"],
	handler: handlePOSTBuildQuery,
	url_pattern: new URLPattern({
		protocol: "http{s}?",
		pathname: "/esbuild{/}?"
	})
}

export {
	esbuild,
	esstop
}

export type {
	ESOutputFile
}

