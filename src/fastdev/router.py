from typing import Type, TypeVar
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, RedirectResponse
from .config import SWD
from .fs_serving import serve_dir, serve_file
from .ts_serving import (
	build_server_callback_path, build_server_loaded_promise, serve_ts,
)

APP_OR_ROUTER = TypeVar("APP_OR_ROUTER", FastAPI, APIRouter)


async def enable_ts_build_server():
	if not build_server_loaded_promise.done():
		build_server_loaded_promise.set_result(None)
	return Response(status_code=200)


async def route_ts(file_name: str, request: Request):
	return await serve_ts(request.url.path.lstrip("/"))


def apply_route_ts(fastapi_app: Type[APP_OR_ROUTER], ts_ext: list[str] = [".ts", ".tsx"]) -> APP_OR_ROUTER:
	""" apply typescript routing to your provided FastAPI app. <br>
	it's best if you apply this routing first, before applying any other routing <br>
	so that it captures all typescript files first and foremost.
	<hr>
	:param fastapi_app: your FastAPI app to apply the routing to
	:type fastapi_app: FastAPI | APIRouter
	:param ts_ext: name the extensions that your typescript files end with, defaults to [".ts", ".tsx"]
	:type ts_ext: list[str], optional
	:return: the provided `fastapi_app` gets returned back
	:rtype: FastAPI | APIRouter
	"""
	fastapi_app.add_api_route(
		build_server_callback_path,
		enable_ts_build_server,
		methods=["GET", "POST"]
	)
	for ext in ts_ext:
		fastapi_app.add_api_route(
			"/{file_name:path}" + ext,
			route_ts,
			methods=["GET"]
		)
	return fastapi_app


async def route_path(path: str):
	abspath = SWD.joinpath(path)
	if not abspath.exists():
		return Response(status_code=404)
	elif abspath.is_file():
		return await serve_file(abspath)
	elif abspath.is_dir():
		if path.endswith("/") or SWD.samefile(abspath):
			return await serve_dir(abspath)
		return RedirectResponse(path + "/")
	else:
		return PlainTextResponse(
			f"the following request was uncaught by main router:\n\t{path}",
			status_code=500
		)


def apply_route_path(fastapi_app: Type[APP_OR_ROUTER]) -> APP_OR_ROUTER:
	""" apply filesystem path routing to your provided FastAPI app. <br>
	you would probably want to apply this route lastly, since it captures all paths.
	<hr>
	:param fastapi_app: your FastAPI app to apply the routing to
	:type fastapi_app: FastAPI | APIRouter
	:return: the provided `fastapi_app` gets returned back
	:rtype: FastAPI | APIRouter
	"""
	fastapi_app.get("/{path:path}")(route_path)
	return fastapi_app
