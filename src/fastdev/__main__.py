from typing import Annotated
import uvicorn
from . import config


def main(*, host: str = "localhost", port: int = config.Port, esbuild_config: Annotated[dict, "Partial", config.ESBuildConfig] = dict()):
	if host.lower().rstrip("/").endswith("localhost"):
		host = "0.0.0.0"
	config.Port = port
	config.ESBuildConfig.update(esbuild_config)
	from .router import app
	uvicorn.run(app, host=host, port=config.Port, reload=False)


if __name__ == "__main__":
	main()
