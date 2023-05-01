import mimetypes
from pathlib import Path

Port: int = 8000
ModDir: Path = Path(__file__).absolute().parent  # this module's root directory
SWD: Path = Path.cwd()  # current working directory is where the server was invoked
ESBuildConfig = {
	"path": "./path/to/script.ts",
	"config": {"minify": False},
	"plugins": ["solid"],
	"plugins_config": dict(),
}
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
