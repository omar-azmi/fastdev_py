from functools import partial
from pathlib import Path
from typing import Type, TypeVar
from fastapi import APIRouter, FastAPI, Response
from fastapi.responses import PlainTextResponse, RedirectResponse
from .config import SWD
from .fs_serving import serve_dir, serve_file
from .ts_serving import (
	build_server_callback_path, build_server_loaded_promise, serve_html_ts,
	serve_ts,
)

APP_OR_ROUTER = TypeVar("APP_OR_ROUTER", FastAPI, APIRouter)


async def enable_ts_build_server():
	if not build_server_loaded_promise.done():
		build_server_loaded_promise.set_result(None)
	return Response(status_code=200)


async def route_ts(
	file_path: str,
	base_dir: Path = SWD,
	ext: str = ".ts"
) -> Response:
	""" route to a compiled version of a typescript file

	:param file_path: path to typescript file. must exclude extension
	:type file_path: str
	:param base_dir: \
		filesystem path to mount onto your `base_url`. \
		the path MUST be absolute (use `base_dir.absolute()`) \
		defaults to SWD (server's root working directory)
	:type base_dir: Path, optional
	:param ext: \
		typescript file extension. \
		defaults to "ts"
	:type ext: str, optional
	:return: compiled typescript file (as bytes buffer)
	:rtype: Response
	"""
	abspath = base_dir.joinpath(file_path + ext)
	return await serve_ts(abspath)


def apply_route_ts(
	fastapi_app: Type[APP_OR_ROUTER],
	base_url: str = "/",
	base_dir: Path = SWD,
	exts: list[str] = [".ts", ".tsx", ".jsx"]
) -> APP_OR_ROUTER:
	""" apply typescript routing to your provided FastAPI app. <br>
	it's best if you apply this routing first, before applying any other routing <br>
	so that it captures all typescript files first and foremost.

	:param fastapi_app: your FastAPI app to apply the routing to
	:type fastapi_app: FastAPI | APIRouter
	:param base_url: \
		base url of the path that will be mounted. \
		must always begin with a slash "/" and also end with one. \
		defaults to "/"
	:type base_url: str, optional
	:param base_dir: \
		filesystem path to mount onto your `base_url`. \
		defaults to SWD (server's root working directory)
	:type base_dir: Path, optional
	:param exts: \
		name the extensions that your typescript files end with. \
		defaults to [".ts", ".tsx", ".jsx"]
	:type exts: list[str], optional
	:return: the provided `fastapi_app` gets returned back
	:rtype: FastAPI | APIRouter
	"""
	fastapi_app.add_api_route(
		build_server_callback_path,
		enable_ts_build_server,
		methods=["GET", "POST"]
	)
	for ext in exts:
		fastapi_app.add_api_route(
			base_url + "{file_path:path}" + ext,
			partial(route_ts, base_dir=base_dir.absolute(), ext=ext),
			methods=["GET"]
		)
	return fastapi_app


async def route_html_ts(
	file_path: str,
	base_dir: Path = SWD,
	ext: str = ".html.js"
) -> Response:
	""" route to a javascript's code's default output string

	:param file_path: path to javascript-like file (js, ts, etc...). must exclude extension
	:type file_path: str
	:param base_dir: \
		filesystem path to mount onto your `base_url`. \
		the path MUST be absolute (use `base_dir.absolute()`) \
		defaults to SWD (server's root working directory)
	:type base_dir: Path, optional
	:param ext: \
		javascript, or typescript file extension. \
		defaults to ".html.js"
	:type ext: str, optional
	:return: executes javascript file and returns its `export default` string output as an html
	:rtype: Response
	"""
	abspath = base_dir.joinpath(file_path + ext)
	return await serve_html_ts(abspath)


def apply_route_html_ts(
	fastapi_app: Type[APP_OR_ROUTER],
	base_url: str = "/",
	base_dir: Path = SWD,
	exts: list[str] = [".html.js", ".html.ts", ".html.tsx", ".html.jsx"]
) -> APP_OR_ROUTER:
	""" apply javascript generated html routing to your provided FastAPI app. <br>
	it's best if you apply this routing before `apply_route_ts` <br>
	so that it captures all ".html.(js|ts|tsx|jsx)" files first and foremost.

	:param fastapi_app: your FastAPI app to apply the routing to
	:type fastapi_app: FastAPI | APIRouter
	:param base_url: \
		base url of the path that will be mounted. \
		must always begin with a slash "/" and also end with one. \
		defaults to "/"
	:type base_url: str, optional
	:param base_dir: \
		filesystem path to mount onto your `base_url`. \
		defaults to SWD (server's root working directory)
	:type base_dir: Path, optional
	:param exts: \
		javascript, or typescript file extension. \
		defaults to [".html.js", ".html.ts", ".html.tsx", ".html.jsx"]
	:type exts: list[str], optional
	:return: the provided `fastapi_app` gets returned back
	:rtype: FastAPI | APIRouter
	"""
	fastapi_app.add_api_route(
		build_server_callback_path,
		enable_ts_build_server,
		methods=["GET", "POST"]
	)
	for ext in exts:
		fastapi_app.add_api_route(
			base_url + "{file_path:path}" + ext,
			partial(route_html_ts, base_dir=base_dir.absolute(), ext=ext),
			methods=["GET"]
		)
	return fastapi_app


async def route_fs(path: str, base_dir: Path = SWD):
	""" route across a filesystem `path`, relative to `base_dir`.
	note that `base_dir` must be an absolute path.
	if a directory path is requested, then a listing of the directory's contents will be seved.
	if there's "index.html" in the requested directory, then you'll be redirected towards it.
	else if a file's path is requested, then that file will be served.

	:param path: path to serve, relative to `base_dir`
	:type path: str
	:param base_dir: \
		root directory of this router. \
		when `path == "/"` or `path == ""`, this filesystem directory will be served. \
		note that it must be an absolute path. \
		defaults to SWD (server's root working directory)
	:type base_dir: Path, optional
	:return: file or directory listing
	:rtype: FileResponse | HTMLResponse | PlainTextResponse
	"""
	abspath = base_dir.joinpath(path)
	if not abspath.exists():
		return Response(status_code=404)
	elif abspath.is_file():
		return await serve_file(abspath)
	elif abspath.is_dir():
		if path.endswith("/") or base_dir.samefile(abspath):
			# check if "./index.html" is available in the requested path directory, and redirect to it if it does exist
			if abspath.joinpath("./index.html").is_file():
				print("index.html found in requested directory. redirecting to it.")
				return RedirectResponse("./index.html")
			return await serve_dir(abspath, base_dir)
		return RedirectResponse("./" + path.split("/")[-1] + "/")
	else:
		return PlainTextResponse(
			f"the following request was uncaught by path router:\n\tpath:\t{path}\n\tbase_dir:\t{base_dir}",
			status_code=500
		)


def apply_route_fs(
	fastapi_app: Type[APP_OR_ROUTER],
	base_url: str = "/",
	base_dir: Path = SWD
) -> APP_OR_ROUTER:
	""" apply filesystem path routing to your provided FastAPI app. <br>
	you would probably want to apply this route lastly, since it captures all paths.

	:param fastapi_app: your FastAPI app to apply the routing to
	:type fastapi_app: FastAPI | APIRouter
	:param base_url: \
		base url of the path that will be mounted. \
		must always begin with a slash "/" and also end with one. \
		defaults to "/"
	:type base_url: str, optional
	:param base_dir: \
		filesystem path to mount onto your `base_url`. \
		defaults to SWD (server's root working directory)
	:type base_dir: Path, optional
	:return: the provided `fastapi_app` gets returned back
	:rtype: FastAPI | APIRouter
	"""
	fastapi_app.get(base_url + "{path:path}")(partial(route_fs, base_dir=base_dir.absolute()))
	return fastapi_app
