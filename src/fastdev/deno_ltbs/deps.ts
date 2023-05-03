import { Handler } from "https://deno.land/std@0.184.0/http/server.ts"
export { parse as cliParse } from "https://deno.land/std@0.184.0/flags/mod.ts"
export { serve } from "https://deno.land/std@0.184.0/http/server.ts"
export type { ConnInfo, Handler } from "https://deno.land/std@0.184.0/http/server.ts"
export { isAbsolute as pathIsAbsolute, join as pathJoin, relative as pathRelative } from "https://deno.land/std@0.184.0/path/mod.ts"


export type Config = {
	port: number
	cwd: string
	cache: boolean
	callback?: string | URL
}

export const config: Config = {
	port: 3000,
	cwd: Deno.cwd(),
	cache: true,
	callback: undefined
}

export type DefaultJSONValues = "null" | "false" | "0" | "\"\"" | "{}" | "[]"

export const searchParamsToObject = <T extends object>(
	url: string,
	default_values?: Partial<{ [key in keyof T]: DefaultJSONValues }>
): T => {
	default_values ??= {}
	const
		search_params = new URLSearchParams(url),
		obj: Partial<T> = {}
	for (let [key, value] of search_params as Iterable<[keyof T, string]>) {
		value = (value === "" && default_values[key] !== undefined) ? default_values[key] as string : value
		obj[key] = JSON.parse(decodeURIComponent(value))
	}
	return obj as T
}

export const objectToSearchParams = (obj: object): string => {
	const obj_json: Record<string, string> = {}
	for (const [key, value] of Object.entries(obj)) {
		obj_json[key] = JSON.stringify(value)
	}
	return new URLSearchParams(obj_json).toString()
}

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

export type Hasher = <T extends object>(obj: T) => string

export const hashObject: Hasher = (obj: object): string => {
	const obj_json = JSONstringifyOrdered(obj)
	return hashString(obj_json)
}

export type JSONstringify<T extends Record<string | number, any> | Array<any>> = string

type VirtualFile = {
	/** the resulting compiled response file as a bytes buffer */
	contents: Uint8Array
	/** compile requested "path"'s last modified time (as a `Date`) */
	mtime: Deno.FileInfo["mtime"]
}

export type CacheStore = {
	[hash: ReturnType<Hasher>]: VirtualFile
}

export const cacheableQuery_Factory = <QUERY extends { path: string }>(
	handle_query: (query: QUERY) => Promise<Uint8Array | undefined> | Uint8Array | undefined,
	cache_store: CacheStore,
	config_options?: {
		headers?: HeadersInit,
		error_response?: {
			body: string,
			status: number
		}
	},
): ((query: QUERY) => Promise<Response>) => {
	const {
		headers,
		error_response = { body: "no output was produced", status: 404 }
	} = { ...config_options }

	return async (query: QUERY) => {
		const
			hash = hashObject(query),
			{ path } = query
		let
			path_last_modified = new Date(),
			file_bytes: Uint8Array | undefined = undefined
		try { path_last_modified = (await Deno.stat(path))?.mtime ?? path_last_modified }
		catch { }
		if (config.cache && (cache_store[hash]?.mtime?.getTime() ?? -1) >= path_last_modified.getTime()) {
			console.debug("return cached query:"); console.group(); console.debug(query); console.groupEnd()
			file_bytes = cache_store[hash].contents
		} else {
			file_bytes = await handle_query(query)
		}
		if (file_bytes === undefined) return new Response(error_response.body, { status: error_response.status })
		if (config.cache) {
			cache_store[hash] = {
				contents: file_bytes,
				mtime: path_last_modified,
			}
		}
		return new Response(file_bytes, {
			status: 200,
			headers,
		})
	}
}

export interface RequestRoute {
	url_pattern: URLPattern
	methods: ("GET" | "POST")[]
	handler: Handler
}
