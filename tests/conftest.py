import httpx
import pytest


@pytest.fixture(autouse=True)
def block_real_http(monkeypatch):
    """Tests must use mocks. A request that reaches a real network transport fails the test."""

    def refuse(self, request):
        raise RuntimeError(f"a test tried a real HTTP request to {request.url.host}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)
