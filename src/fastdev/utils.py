import json
from typing import Annotated, Literal, Optional, TypedDict
from urllib.request import Request, urlopen

HTTPHeader = TypedDict("HTTPHeader", {
	"content-type": Optional[Annotated[str, "mimetype"]],
	"accept": Optional[Annotated[str, "accepted mimetype"]],
})
HTTPMethod = Literal["GET", "POST", "PUT", "DELETE"]
HTTPResponse = TypedDict("HTTPResponse", {
	"content": Optional[bytes],
	"status_code": int,
})
HTTPResponseText = TypedDict("HTTPResponseText", {
	"content": Optional[str],
	"status_code": int,
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
	with urlopen(Request(url, content, headers=headers, method=method), timeout=timeout) as response:
		return HTTPResponse(
			content=response.read(),
			status_code=response.getcode(),
		)


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
		if response["content"] is None:
			return None
		return HTTPResponseText(
			content=response["content"].decode("utf-8"),
			status_code=response["status_code"],
		)
	except:
		return None
