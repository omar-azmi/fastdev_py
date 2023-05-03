from typing import Annotated
import uvicorn
from fastapi import FastAPI
from . import config


def main(*, host: str = "localhost", port: int = config.Port, esbuild_config: Annotated[dict, "Partial", config.ESBuildConfig] = dict()):
	if host.lower().rstrip("/").endswith("localhost"):
		host = "0.0.0.0"
	config.Port = port
	config.ESBuildConfig.update(esbuild_config)
	app = FastAPI()
	from .__init__ import apply_route_fs, apply_route_html_ts, apply_route_ts
	apply_route_html_ts(app)
	apply_route_ts(app)
	apply_route_fs(app)
	uvicorn.run(app, host=host, port=config.Port, reload=False)


if __name__ == "__main__":
	main()
