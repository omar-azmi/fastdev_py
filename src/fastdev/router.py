from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from .config import SWD
from .fs_serving import serve_dir, serve_file
from .ts_serving import serve_ts, build_server_callback_path, build_server_loaded_promise

app = FastAPI()


@app.get(build_server_callback_path)
@app.post(build_server_callback_path)
async def enable_ts_build_server():
	if not build_server_loaded_promise.done():
		build_server_loaded_promise.set_result(None)
	return Response(status_code=200)


@app.get("/{file_name:path}.ts")
@app.get("/{file_name:path}.tsx")
async def route_ts(file_name: str, request: Request):
	return await serve_ts(request.url.path.lstrip("/"))


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
	return Response(status_code=404)


@app.get("/{path:path}")
async def route_path(path: str):
	abspath = SWD.joinpath(path)
	if not abspath.exists():
		return Response(status_code=404)
	elif abspath.is_file():
		return await serve_file(abspath)
	elif abspath.is_dir():
		return await serve_dir(abspath)
	else:
		return PlainTextResponse(
			f"the following request was uncaught by main router:\n\t{path}",
			status_code=500
		)
