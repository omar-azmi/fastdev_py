from pathlib import Path
from fastapi.responses import (
	FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse,
)
from .config import SWD
from .utils import qoute


async def serve_file(file: Path):
	if not file.is_file():
		return PlainTextResponse(f"the following file was not found:\n\t{file}", status_code=404)
	""" fastapi takes care of custom mime types when they're added to the built-in `mintypes` library
	mime, _ = mimetypes.guess_type(file)
	if mime is None:
		mime = "application/octet-stream"
	return FileResponse(file, media_type=mime)
	"""
	return FileResponse(file)


async def serve_dir(directory: Path):
	if not directory.is_dir():
		return PlainTextResponse(
			f"the following directory was not found:\n\t{directory}",
			status_code=404
		)
	directory_index = directory.joinpath("./index.html")
	if directory_index.is_file():
		index_html_url = "/" + str(directory_index.relative_to(SWD).as_posix())
		print(f"index.html found. redirecting to:\n\t{index_html_url}")
		return RedirectResponse(index_html_url)
	dir_head = directory.relative_to(SWD)
	dir_links: dict[str, str] = dict()  # key: href_path, value: title
	dir_links["./.."] = ".."
	for subpath in directory.iterdir():
		rel_subpath = subpath.relative_to(directory)
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
