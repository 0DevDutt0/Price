import json

import httpx
import pytest

from price_agent.datawebot import DataWebotClient, DataWebotError, load_api_key


def _reply(payload):
    return {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": json.dumps(payload)}], "isError": False}}


def _client(handler, key="dwb_test"):
    return DataWebotClient(key, http=httpx.Client(transport=httpx.MockTransport(handler)))


def _saved_credentials(tmp_path, key):
    path = tmp_path / "credentials"
    path.write_text(json.dumps({"version": 1, "profiles": {"https://mcp.datawebot.com": {"api_key": key}}}))
    return path


def test_environment_key_takes_precedence_over_saved_file(tmp_path):
    path = _saved_credentials(tmp_path, "dwb_file")
    assert load_api_key({"DATAWEBOT_API_KEY": " dwb_env "}, path) == "dwb_env"


def test_saved_profile_is_used_without_environment_key(tmp_path):
    assert load_api_key({}, _saved_credentials(tmp_path, "dwb_file")) == "dwb_file"


def test_missing_key_is_reported(tmp_path):
    with pytest.raises(DataWebotError) as info:
        load_api_key({}, tmp_path / "missing")
    assert info.value.code == "no_key"


def test_search_sends_bearer_key_and_returns_payload():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_reply({"data": {"results": []}, "meta": {"searches_left_today": 5}}))

    with _client(handler) as client:
        payload = client.search_products("Sony WH-1000XM5", country="US", limit=2)

    assert seen["auth"] == "Bearer dwb_test"
    assert seen["body"]["params"] == {
        "name": "search_products",
        "arguments": {"query": "Sony WH-1000XM5", "country": "US", "limit": 2},
    }
    assert payload["meta"]["searches_left_today"] == 5


def test_offers_call_passes_product_id_query_and_country():
    seen = {}

    def handler(request):
        seen["arguments"] = json.loads(request.content)["params"]["arguments"]
        return httpx.Response(200, json=_reply({"data": {"offers": []}}))

    with _client(handler) as client:
        client.get_product_offers("123", query="Sony WH-1000XM5", country="US")

    assert seen["arguments"] == {"product_id": "123", "query": "Sony WH-1000XM5", "country": "US"}


@pytest.mark.parametrize(
    "status, code",
    [(401, "login_required"), (402, "insufficient_credits"), (429, "rate_limited"), (500, "http_500")],
)
def test_http_status_maps_to_error_code(status, code):
    with _client(lambda request: httpx.Response(status, text="no")) as client:
        with pytest.raises(DataWebotError) as info:
            client.search_products("abc")
    assert info.value.code == code


def test_json_rpc_error_is_reported():
    handler = lambda request: httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Unknown tool"}})
    with _client(handler) as client:
        with pytest.raises(DataWebotError) as info:
            client.search_products("abc")
    assert info.value.code == "rpc_error"
    assert "Unknown tool" in str(info.value)


def test_tool_error_flag_is_reported():
    reply = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "bad query"}], "isError": True}}
    with _client(lambda request: httpx.Response(200, json=reply)) as client:
        with pytest.raises(DataWebotError) as info:
            client.search_products("abc")
    assert info.value.code == "tool_error"


def test_reply_text_that_is_not_json_is_reported():
    reply = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "<html>"}], "isError": False}}
    with _client(lambda request: httpx.Response(200, json=reply)) as client:
        with pytest.raises(DataWebotError) as info:
            client.search_products("abc")
    assert info.value.code == "bad_reply"


def test_network_failure_is_reported():
    def handler(request):
        raise httpx.ConnectError("offline")

    with _client(handler) as client:
        with pytest.raises(DataWebotError) as info:
            client.search_products("abc")
    assert info.value.code == "network_error"


def test_rate_limited_is_recognised_by_name_even_without_a_429_status():
    with _client(lambda request: httpx.Response(500, text='{"error": "rate_limited"}')) as client:
        with pytest.raises(DataWebotError) as info:
            client.search_products("abc")
    assert info.value.code == "rate_limited"


def test_rate_limited_inside_a_tool_error_is_recognised():
    reply = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "rate_limited: try tomorrow"}], "isError": True}}
    with _client(lambda request: httpx.Response(200, json=reply)) as client:
        with pytest.raises(DataWebotError) as info:
            client.search_products("abc")
    assert info.value.code == "rate_limited"


def test_login_required_inside_a_json_rpc_error_is_recognised():
    handler = lambda request: httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "login_required"}})
    with _client(handler) as client:
        with pytest.raises(DataWebotError) as info:
            client.search_products("abc")
    assert info.value.code == "login_required"
