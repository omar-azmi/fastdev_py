from asyncio import Future
from subprocess import Popen
from urllib.parse import urljoin
import requests
from fastapi.responses import JSONResponse
from .config import CWSD, PORT, PROJ_DIR
from .utils import qoute

BUILD_SERVER_PORT = 3000  # the port on which `deno_lts_esbuild.ts` listens for build requests
build_server_loaded_promise = Future()
build_server_path = PROJ_DIR.joinpath("./src/fastdev/builders/deno_lts_esbuild.ts")
build_server_callback = f"http://localhost:{PORT}/build_server_loaded"
build_server_url = f"http://localhost:{BUILD_SERVER_PORT}"
build_server_process = Popen(f"deno run -A {qoute(build_server_path)} --port={BUILD_SERVER_PORT} --callback={qoute(build_server_callback)}", cwd=CWSD)


async def serve_ts(url_path: str):
	await build_server_loaded_promise
	file_abspath = CWSD.joinpath(url_path)
	output_js_response = await requests.post(urljoin(build_server_url, "compile"), {
		"path": file_abspath,
		"config": {"minify": False},
		"plugins": ["deno"],
		"plugins_config": dict(),
	})
	if output_js_response is None:
		return JSONResponse(status_code=503, content={"error": "failed to transpile and bundle the requested file."})
	output_js_response.headers["content-type"] = "text/javascript"
	return await output_js_response
