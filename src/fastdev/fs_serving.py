from pathlib import Path
from typing import Optional
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from .config import SWD
from .utils import qoute


async def serve_file(file: Path, media_type: Optional[str] = None) -> FileResponse:
	""" server a file. the file path must either be absolute or relative to server's working directory (`SWD`)

	:param file: path to the file to serve. file path must either be absolute or relative to `SWD`
	:type file: Path
	:param media_type: \
		include an optional self defined mime type in header. \
		if `None` is supplied, then fastapi will guess it using `mimetypes.guess_type(file)`. \
		you can define your own standard library mime types before invoking fastapi, using: \
		```py \
		import mimetypes \
		mimetypes.add_type("application/mymime", ".ext") \
		```
		defaults to None
	:type media_type: Optional[str], optional
	:return: an http response containing the file, or a 404 error with `PlainTextResponse` if the file is not found 
	:rtype: FileResponse
	"""
	if not file.is_file():
		return PlainTextResponse(f"the following file was not found:\n\t{file}", status_code=404)
	return FileResponse(file, media_type=media_type)


async def serve_dir(directory: Path, base_dir: Path = SWD) -> HTMLResponse:
	""" server a directory listing as html.

	:param directory: path to the directory to list. it can either be absolute or relative to `SWD`
	:type directory: Path
	:param base_dir: \
		the heading in the html will present the `directory`'s path relative to your supplied `base_dir`. \
		make sure that `base_dir` is always an absolute path, and not a relative path to `SWD`. \
		note that `base_dir` does not alter the interpretation `directory`, \
		since `directory` will always either be absolute or rlative to `SWD`. \
		defaults to SWD
	:type base_dir: base_dir, optional
	:return: \
		an html response containing the directory listing and hyperlinks to its subcontent. \
		a 404 error with `PlainTextResponse` will be returned if the provided `directory` is not found
	:rtype: HTMLResponse
	"""
	directory = directory.absolute()
	if not directory.is_dir():
		return PlainTextResponse(
			f"the following directory was not found:\n\t{directory}",
			status_code=404
		)
	dir_head = directory.relative_to(base_dir).as_posix()
	dir_links: dict[str, str] = dict()  # key: href_path, value: title
	dir_links["./.."] = ".."
	for subpath in directory.iterdir():
		rel_subpath = subpath.relative_to(directory).as_posix()
		prefix = "./"
		suffix = "" if subpath.is_file() else "/"
		href = prefix + str(rel_subpath) + suffix
		title = str(rel_subpath) + suffix
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
	return HTMLResponse(html)
