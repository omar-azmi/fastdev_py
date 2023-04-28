from abc import abstractmethod
import os
from pathlib import Path
import asyncio
import mimetypes
from time import perf_counter
from typing import Self
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

# run using cmd `uvicorn fastapi_server:app --reload`

# region GLOBAL VARIABLES AND UTILITY FUNCTIONS

PORT = 8000
cwsd = Path.cwd()  # current server working directory
include_mime_types = {
	# files requiring preprocessing must have the same mime type as their compiled counterparts:
	".ts": "text/javascript",
	".tsx": "text/javascript",
	".jsx": "text/javascript",
	".scss": "text/css",
	".sass": "text/css",
	# additional mime types that are not there by default:
	"": "application/octet-stream",
	".txt": "text/plain",
	".html": "text/html",
	".css": "text/css",
	".js": "text/javascript",
	".png": "image/png",
	".jpg": "image/jpg",
	".svg": "image/svg+xml",
	".wasm": "application/wasm",
	".json": "application/json",
	".xml": "application/xml",
}
for ext, mt in include_mime_types.items():
	mimetypes.add_type(mt, ext)
app = FastAPI()


def qoute(string: str | object) -> str:
	if not isinstance(string, str):
		string = str(string)
	return "\"" + string + "\""

# endregion

# region PREPROCESSOR AND FILE WATCHER CLASSES


class WatchedFile:
	def __init__(self, path: str | Path):
		self.path: Path = path if isinstance(path, Path) else Path(path)
		self.last_modified = self.path.stat().st_mtime

	def has_changed(self) -> bool:
		current_modified_time = self.path.stat().st_mtime
		if current_modified_time != self.last_modified:
			self.last_modified = current_modified_time
			return True
		else:
			return False

	def samefile(self, file_path: str | Path) -> bool:
		return self.path.samefile(file_path)

	def set_dirty(self) -> None:
		# manually set the watched file to "modified" (ie dirty), so that has_changed returns true
		self.last_modified -= 1


class PreprocessorCacheable:
	cache: dict[Path, Self] = dict()

	def __new__(cls, input: Path, *args, **kwargs) -> Self:
		if input in cls.cache:
			return cls.cache[input]
		new_instance = super().__new__(cls)
		cls.cache[input] = new_instance
		cls.__init__(new_instance, input, *args, **kwargs)
		return new_instance

	def __init__(self, input: Path, output: Path | None = None, get_performance: bool = True) -> None:
		self.input = input
		self.input_watcher = WatchedFile(input)
		self.output = output
		self.get_performance = get_performance

	@abstractmethod
	def compile(self) -> tuple[str, Path | None]:
		"""implement a function that compiles `self.input.path` file, and returns the `Path` to the output compiled file.
		also, avoid setting `self.output` here yourself, because that gets done by `self.process`.
		here is a template of what you'd do to run a cli based compiler ("esbuild" in this case):
		```py
		class TS_Preprocessor(PreprocessorCacheable):
			def compile(self) -> str:
				output_file_path = self.input_watcher.path.with_suffix(".js")
				cmd = f"esbuild {qoute(self.input_watcher.path)} --minify --bundle --outfile={qoute(output_file_path)}"
				return (cmd, output_file_path,)
		```
		"""
		Exception("you must subclass PreprocessorCache, and implement your own compile function")
		return (None, None,)

	async def process(self) -> Path | None:
		# check if output path already exists
		# or check if the cached file has not been modified since last time
		# if not, we must compile the input
		if (self.output is None) or (not self.output.is_file()) or self.input_watcher.has_changed():
			t = perf_counter()
			cmd, self.output = self.compile()
			proc = await asyncio.create_subprocess_shell(
				cmd,
				cwd=cwsd,
				shell=True,
				stdout=asyncio.subprocess.PIPE,
				stderr=asyncio.subprocess.PIPE,
			)
			stdout, stderr = await proc.communicate()
			if stderr:
				print(f"[compiler error]\n{stderr.decode()}")
			if self.get_performance:
				print(f"""compiled {qoute(self.output)} in {perf_counter() - t} sec""")
		return self.output

	@classmethod
	def set_all_dirty(cls) -> None:
		# set all watched cached output files as dirty (ie modified and requiring recompilation)
		for instance in cls.cache.values():
			instance.input_watcher.set_dirty()

	@classmethod
	def list_all_output(cls) -> list[Path]:
		# list all cached output files' path generated by the compiler
		return list(cls.cache.keys())

	@classmethod
	def delete_all_output(cls) -> list[Path]:
		# delete all cached outputs generated by the compilers. use this cautiously, as it may unintentionally delete your source files
		deleted_list: list[Path] = []
		for instance in cls.cache.values():
			output_file = instance.output
			if output_file.exists() and output_file.is_file():
				print(f"""deleting {output_file}""")
				deleted_list.append(output_file)
				output_file.unlink()
		cls.cache.clear()
		return deleted_list

# endregion

# region PREPROCESSOR DEFINITIONS


class TS_Preprocessor(PreprocessorCacheable):
	def compile(self) -> str:
		input_file_path = self.input_watcher.path
		output_file_path = input_file_path.with_suffix(".js")
		cmd = f"esbuild {qoute(input_file_path)} --minify --bundle --outfile={qoute(output_file_path)}"
		return (cmd, output_file_path,)

# endregion

# region SERVER GET ROUTING


@app.get("/{file_name:path}.ts")
@app.get("/{file_name:path}.tsx")
async def serve_ts(file_name: str, request: Request):
	file_abspath = cwsd.joinpath(request.url.path.lstrip("/"))
	preprocess = TS_Preprocessor(file_abspath)
	output_file_path = await preprocess.process()
	if output_file_path is None:
		return JSONResponse(status_code=503, content={"error": "failed to transpile and bundle the requested file."})
	return await serve_file(output_file_path)


@app.get("/cache_dirty")
async def cache_dirty():
	"""set all cached preprocessed files to dirty"""
	return TS_Preprocessor.set_all_dirty()


@app.get("/cache_list")
async def cache_list():
	"""list all cached preprocessed files"""
	return JSONResponse(TS_Preprocessor.list_all_output())


@app.get("/cache_delete")
async def cache_delete():
	"""delete all cached preprocessed files"""
	return JSONResponse(TS_Preprocessor.delete_all_output())


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
	return Response(status_code=404)


@app.get("/{path:path}")
async def serve_path(path: str):
	abspath = cwsd.joinpath(path)
	if not abspath.exists():
		return Response(status_code=404)
	elif abspath.is_file():
		return await serve_file(abspath)
	elif abspath.is_dir():
		return await serve_dir(abspath)
	else:
		return JSONResponse(status_code=500, content={"error": f"the following request was uncaught:\n\t{path}"})


async def serve_dir(directory: Path):
	if not directory.is_dir():
		return JSONResponse(status_code=404, content={"error": f"the following directory was not found:\n\t{directory}"})
	directory_index = directory.joinpath("./index.html")
	if directory_index.is_file():
		return await serve_file(directory_index)
	dir_head = directory.relative_to(cwsd)
	dir_links: dict[str, str] = dict()  # key: href_path, value: title
	for subpath in directory.iterdir():
		rel_subpath = subpath.relative_to(directory)
		href = str(rel_subpath)
		title = href + ("" if subpath.is_file() else "/")
		dir_links[href] = title
	dir_links_html_li: list[str] = [f"""
	<li><a href={qoute(href)}>{title}</a></li>
	""" for href, title in dir_links.items()]
	html = f"""
	<html lang="en">
	<head>
		<meta charset="utf-8">
		<title>devserver directory: {qoute(dir_head)}</title>
	</head>
	<body>
		<h1>Directory listing for: {qoute(dir_head)}</h1>
		<hr>
		<ul>
			{"".join(dir_links_html_li)}
		</ul>
		<hr>
	</body>
	</html>
	"""
	return HTMLResponse(content=html)


async def serve_file(file: Path):
	if not file.is_file():
		return JSONResponse(status_code=404, content={"error": f"the following file was not found:\n\t{file}"})
	mime, _ = mimetypes.guess_type(file)
	if mime is None:
		mime = "application/octet-stream"
	return FileResponse(file, media_type=mime)

# endregion

if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=PORT, reload=False)
