def qoute(string: str | object) -> str:
	if not isinstance(string, str):
		string = str(string)
	return "\"" + string + "\""
