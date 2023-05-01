from asyncio import Future
from subprocess import Popen
from urllib.parse import urljoin
from fastapi.responses import PlainTextResponse, Response
from .config import SWD, ESBuildConfig, ModDir, Port
from .utils import post_data, qoute

BUILD_SERVER_PORT = 3000  # the port on which `deno_lts_esbuild.ts` listens for build requests
build_server_loaded_promise = Future()
build_server_path = ModDir.joinpath("./builders/deno_lts_esbuild.ts")
build_server_callback_path = "/build_server_loaded"
build_server_callback = f"http://localhost:{Port}{build_server_callback_path}"
build_server_url = f"http://localhost:{BUILD_SERVER_PORT}"
build_server_process = Popen(f"deno run -A {qoute(build_server_path)} --port={BUILD_SERVER_PORT} --callback={qoute(build_server_callback)}", cwd=SWD)


async def serve_ts(url_path: str):
	await build_server_loaded_promise
	# file_abspath = SWD.joinpath(url_path)
	output_js_response = post_data(
		urljoin(build_server_url, "compile"),
		{**ESBuildConfig, "path": url_path},
		timeout=50_000,
		headers={"content-type": "application/json"},
	)
	if output_js_response is None:
		return PlainTextResponse(
			f"failed to transpile and bundle the requested file:\n\t{url_path}",
			status_code=503
		)
	return Response(
		output_js_response["content"],
		status_code=output_js_response["status_code"],
		media_type="text/javascript"
	)
