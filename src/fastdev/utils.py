import json
from typing import Annotated, TypedDict, Optional, Literal
from urllib.request import Request as urlRequest, urlopen
from asyncio import gather, Future, run as async_run

HTTPHeader = TypedDict("HTTPHeader", {
	"content-type": Optional[Annotated[str, "mimetype"]],
	"accept": Optional[Annotated[str, "accepted mimetype"]],
})
HTTPMethod = Literal["GET", "POST", "PUT", "DELETE"]
HTTPResponse = TypedDict("HTTPResponse", {
	"status_code": int,
	"content": Optional[bytes],
})
HTTPResponseText = TypedDict("HTTPResponseText", {
	"status_code": int,
	"content": Optional[str],
})


def qoute(string: str | object) -> str:
	if not isinstance(string, str):
		string = str(string)
	return "\"" + string + "\""


def fetch(
	url: str,
	content: bytes,
	timeout=10_000,
	*,
	method: HTTPMethod = "GET",
	headers: HTTPHeader = dict()
) -> HTTPResponse:
	with urlopen(urlRequest(url, content, headers=headers, method=method), timeout=timeout) as response:
		return {
			"status_code": response.getcode(),
			"content": response.read(),
		}


def post_data(
	url: str,
	data: dict | list,
	timeout=10_000,
	*,
	method: HTTPMethod = "POST",
	headers: HTTPHeader = {"content-type": "application/json"}
) -> HTTPResponseText | None:
	try:
		response = fetch(url, json.dumps(data).encode("utf-8"), timeout, method=method, headers=headers)
		if response["content"] is not None:
			response["content"] = response["content"].decode("utf-8")
		return response
	except:
		return None
