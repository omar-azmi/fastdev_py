from pathlib import Path
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from .config import CWSD, mimetypes
from .utils import qoute


async def serve_file(file: Path):
	if not file.is_file():
		return PlainTextResponse(status_code=404, content=f"the following file was not found:\n\t{file}")
	""" fastapi takes care of custom mime types when they're added to the built-in `mintypes` library
	mime, _ = mimetypes.guess_type(file)
	if mime is None:
		mime = "application/octet-stream"
	return FileResponse(file, media_type=mime)
	"""
	return FileResponse(file)


async def serve_dir(directory: Path):
	if not directory.is_dir():
		return PlainTextResponse(status_code=404, content=f"the following directory was not found:\n\t{directory}")
	directory_index = directory.joinpath("./index.html")
	if directory_index.is_file():
		return await serve_file(directory_index)
	dir_head = directory.relative_to(CWSD)
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
