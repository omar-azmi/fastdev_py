import { CacheStore, DefaultJSONValues, Handler, RequestRoute, cacheableQuery_Factory, config, pathIsAbsolute, pathJoin, pathRelative, searchParamsToObject } from "./deps.ts"


export interface BuildQuery {
	/** path: "./path/to/index.html.ts" must be relative to current working directory */
	path: string
}

const absolute_path_prefixes = ["http://", "https://", "file://"]

const buildQuery = async (query: BuildQuery): Promise<string | undefined> => {
	console.debug("new build query:")
	console.group()
	console.debug(query)
	const
		{ path } = query,
		t0 = performance.now(),
		abspath = absolute_path_prefixes.reduce(
			(is_prefix, prefix) => is_prefix || path.startsWith(prefix),
			false,
		) ? path : "file://" + (pathIsAbsolute(path) ? path : pathJoin(config.cwd!, path))
	const { default: output_html } = await import(abspath) as { default: string }
	console.debug("compilation time:", performance.now() - t0, "ms")
	console.debug("binary size:", output_html.length / 1024, "kb")
	console.groupEnd()
	return output_html
}

export const cache: CacheStore<string> = {}

const cacheableBuildQuery = cacheableQuery_Factory(buildQuery, cache, {
	headers: {
		"content-type": "text/html"
	},
	error_response: {
		body: "no html output was produced",
		status: 404,
	}
})

const defaultSearchParams: { [key in keyof BuildQuery]: DefaultJSONValues } = {
	path: "\"\"",
}

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
		pathname: "/html{/}?",
		search: undefined
	})
}

/** `Request.body` must be `JSON.stringify(query)` or `Request.json(query)`, where `let query: BuildQuery` */
export const requestRoutePOST: RequestRoute = {
	methods: ["POST"],
	handler: handlePOSTBuildQuery,
	url_pattern: new URLPattern({
		protocol: "http{s}?",
		pathname: "/html{/}?"
	})
}
