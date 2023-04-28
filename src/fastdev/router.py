from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from .config import CWSD
from .fs_serving import serve_dir, serve_file
from .ts_serving import serve_ts

app = FastAPI()


@app.get("/{file_name:path}.ts")
@app.get("/{file_name:path}.tsx")
async def route_ts(file_name: str, request: Request):
	return serve_ts(request.url.path.lstrip("/"))


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
	return Response(status_code=404)


@app.get("/{path:path}")
async def route_path(path: str):
	abspath = CWSD.joinpath(path)
	if not abspath.exists():
		return Response(status_code=404)
	elif abspath.is_file():
		return await serve_file(abspath)
	elif abspath.is_dir():
		return await serve_dir(abspath)
	else:
		return JSONResponse(status_code=500, content={"error": f"the following request was uncaught:\n\t{path}"})
