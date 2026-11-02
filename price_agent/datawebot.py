"""A small client for the datawebot MCP server: JSON-RPC over HTTP, as its setup guide describes."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

SERVER = "https://mcp.datawebot.com"
ENDPOINT = f"{SERVER}/mcp"
CREDENTIALS_PATH = Path.home() / ".datawebot" / "credentials"
KEY_ENV_VAR = "DATAWEBOT_API_KEY"  # takes precedence over the saved credentials file
USER_AGENT = "price-agent/0.1"
TIMEOUT_SECONDS = 60

# Error names from the datawebot setup guide. The guide gives HTTP 401 for login_required and 402 for
# insufficient_credits, and no status for rate_limited. So the name is also looked for in the reply text.
NAMED_ERRORS = ("login_required", "rate_limited", "insufficient_credits")
STATUS_ERRORS = {401: "login_required", 402: "insufficient_credits", 429: "rate_limited"}  # 429 is an assumption
MESSAGES = {
    "login_required": "The key is missing or has expired. Sign in to datawebot again.",
    "rate_limited": "This account is rate limited on datawebot, so try again tomorrow. "
    "The daily search allowance may be used up.",
    "insufficient_credits": "This account has too few datawebot credits. This agent does not use Jobs.",
}


class DataWebotError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code  # short machine-readable reason, e.g. login_required or rate_limited


def load_api_key(env: Mapping[str, str] | None = None, path: Path = CREDENTIALS_PATH) -> str:
    """Return the key from the environment, or from the profile saved by datawebot's sign-in."""
    key = (os.environ if env is None else env).get(KEY_ENV_VAR)
    if key:
        return key.strip()
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        return saved["profiles"][SERVER]["api_key"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise DataWebotError(
            "no_key", f"No datawebot key in {KEY_ENV_VAR} or {path}. Sign in to datawebot first."
        ) from error


class DataWebotClient:
    def __init__(self, api_key: str, http: httpx.Client | None = None):
        self._http = http or httpx.Client(timeout=TIMEOUT_SECONDS)
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": USER_AGENT,
        }

    def __enter__(self) -> DataWebotClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def search_products(self, query: str, country: str = "US", limit: int = 10) -> dict[str, Any]:
        return self.call_tool("search_products", {"query": query, "country": country, "limit": limit})

    def get_product_offers(self, product_id: str, query: str, country: str = "US") -> dict[str, Any]:
        # The guide asks for the same query and country as the search that produced product_id.
        return self.call_tool("get_product_offers", {"product_id": product_id, "query": query, "country": country})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
        try:
            response = self._http.post(ENDPOINT, json=body, headers=self._headers)
        except httpx.HTTPError as error:
            raise DataWebotError("network_error", f"could not reach datawebot ({type(error).__name__})") from error
        if response.status_code != 200:
            raise _status_error(response.status_code, response.text)
        try:
            envelope = response.json()
        except ValueError as error:
            raise DataWebotError("bad_reply", f"{name} returned a reply that is not JSON") from error
        return _payload(envelope, name)


def _named_error(text: str) -> str | None:
    return next((code for code in NAMED_ERRORS if code in text), None)


def _status_error(status: int, body: str) -> DataWebotError:
    code = _named_error(body) or STATUS_ERRORS.get(status) or f"http_{status}"
    return DataWebotError(code, MESSAGES.get(code, f"The request to datawebot returned HTTP {status}."))


def _reply_error(default_code: str, name: str, detail: str) -> DataWebotError:
    code = _named_error(detail) or default_code
    return DataWebotError(code, MESSAGES.get(code, f"{name}: {detail}"))


def _payload(envelope: Any, name: str) -> dict[str, Any]:
    """Unwrap a tools/call reply: the tool's JSON is the text of the first content item."""
    if not isinstance(envelope, dict):
        raise DataWebotError("bad_reply", f"{name} returned an unexpected reply")
    if "error" in envelope:
        error = envelope["error"]
        message = error.get("message", "unknown error") if isinstance(error, dict) else str(error)
        raise _reply_error("rpc_error", name, message)
    result = envelope.get("result") or {}
    content = result.get("content") or []
    text = content[0].get("text") if content and isinstance(content[0], dict) else None
    if not isinstance(text, str):
        raise DataWebotError("bad_reply", f"{name} returned no text")
    if result.get("isError"):
        raise _reply_error("tool_error", name, text[:300])
    try:
        payload = json.loads(text)
    except ValueError as error:
        raise DataWebotError("bad_reply", f"{name} returned text that is not JSON") from error
    if not isinstance(payload, dict):
        raise DataWebotError("bad_reply", f"{name} returned JSON that is not an object")
    return payload
