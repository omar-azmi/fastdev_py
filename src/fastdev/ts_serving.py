from asyncio import Future
from pathlib import Path
from subprocess import Popen
from urllib.parse import urljoin
from fastapi.responses import PlainTextResponse, Response
from .config import SWD, ESBuildConfig, ModDir, Port
from .utils import post_data, qoute

BUILD_SERVER_PORT = 3000  # the port on which `deno_ltbs.ts` listens for build requests
build_server_loaded_promise = Future()
build_server_path = ModDir.joinpath("./deno_ltbs/mod.ts")
build_server_callback_path = "/deno_ltbs_loaded"
build_server_callback = f"http://localhost:{Port}{build_server_callback_path}"
build_server_url = f"http://localhost:{BUILD_SERVER_PORT}"
build_server_process = Popen(f"deno run -A {qoute(build_server_path)} --port={BUILD_SERVER_PORT} --callback={qoute(build_server_callback)}", cwd=SWD)


async def serve_ts(file: Path):
	await build_server_loaded_promise
	file_abspath = file.absolute().relative_to(SWD).as_posix()
	output_js_response = post_data(
		urljoin(build_server_url, "esbuild"),
		{**ESBuildConfig, "path": str(file_abspath)},
		timeout=50_000,
		headers={"content-type": "application/json"},
	)
	if output_js_response is None:
		return PlainTextResponse(
			f"failed to transpile and bundle the requested file:\n\t{file}",
			status_code=503
		)
	return Response(
		output_js_response["content"],
		status_code=output_js_response["status_code"],
		media_type="text/javascript"
	)


async def serve_html_ts(file: Path):
	await build_server_loaded_promise
	file_abspath = file.absolute().relative_to(SWD).as_posix()
	output_html_response = post_data(
		urljoin(build_server_url, "html"),
		{"path": str(file_abspath)},
		timeout=50_000,
		headers={"content-type": "application/json"},
	)
	if output_html_response is None:
		return PlainTextResponse(
			f"failed to render the requested file:\n\t{file}",
			status_code=503
		)
	return Response(
		output_html_response["content"],
		status_code=output_html_response["status_code"],
		media_type="text/html"
	)
