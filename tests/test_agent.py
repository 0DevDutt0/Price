import pytest

from price_agent.agent import research
from price_agent.datawebot import DataWebotError


def search_item(product_id, has_offers=True):
    return {"product_id": product_id, "title": f"Product {product_id}", "has_offers": has_offers, "rating": 4.0, "rating_count": 10}


def offers_reply(product_id, searches_left):
    return {
        "data": {
            "product": {"title": f"Product {product_id}", "rating": 4.5, "rating_count": 100},
            "offers": [{"shop": "shop.example", "price": 20, "total_text": "$20.00", "currency": "USD"}],
            "reviews": [],
        },
        "meta": {"searches_left_today": searches_left, "as_of": f"time-{product_id}"},
    }


class FakeClient:
    def __init__(self, results, searches_left=30, offer_errors=None):
        self.results = results
        self.searches_left = searches_left
        self.offer_errors = offer_errors or {}
        self.offer_calls = []

    def search_products(self, query, country="US", limit=10):
        return {"data": {"results": self.results}, "meta": {"searches_left_today": self.searches_left, "as_of": "t0"}}

    def get_product_offers(self, product_id, query, country="US"):
        self.offer_calls.append(product_id)
        if product_id in self.offer_errors:
            raise self.offer_errors[product_id]
        self.searches_left -= 1
        return offers_reply(product_id, self.searches_left)


def test_only_listed_results_are_opened_and_the_limit_caps_them():
    client = FakeClient([search_item("a"), search_item("b", has_offers=False), search_item("c"), search_item("d")])
    report = research(client, "kettle", limit=2)
    assert client.offer_calls == ["a", "c"]
    assert [p.product_id for p in report.products] == ["a", "c"]
    assert report.without_offers == 1


def test_searches_left_comes_from_the_latest_reply():
    client = FakeClient([search_item("a")], searches_left=30)
    report = research(client, "kettle", limit=1)
    assert report.searches_left == 29


def test_each_product_keeps_the_retrieval_time_of_its_offers_reply():
    report = research(FakeClient([search_item("a"), search_item("b")]), "kettle", limit=2)
    assert [p.as_of for p in report.products] == ["time-a", "time-b"]


def test_the_search_time_is_kept_on_the_report():
    report = research(FakeClient([search_item("a")]), "kettle", limit=1)
    assert report.searched_at == "t0"


def test_a_product_error_is_recorded_and_the_run_continues():
    client = FakeClient(
        [search_item("a"), search_item("b")],
        offer_errors={"a": DataWebotError("product_not_found", "gone")},
    )
    report = research(client, "kettle", limit=2)
    assert [p.product_id for p in report.products] == ["b"]
    assert len(report.skipped) == 1
    assert "gone" in report.skipped[0]


@pytest.mark.parametrize("code", ["rate_limited", "login_required"])
def test_account_wide_errors_stop_the_run(code):
    client = FakeClient([search_item("a"), search_item("b")], offer_errors={"a": DataWebotError(code, "stop")})
    with pytest.raises(DataWebotError):
        research(client, "kettle", limit=2)
    assert client.offer_calls == ["a"]
