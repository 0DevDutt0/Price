import pytest

from price_agent import pick
from price_agent.models import Offer, Product


def raw_offer(shop, price, total_text=None, shipping_text=None, currency="USD", url=None):
    return {
        "shop": shop,
        "price": price,
        "total_text": total_text,
        "shipping_text": shipping_text,
        "currency": currency,
        "url": url,
    }


def product(title, rating, count, offers=()):
    return Product(product_id=title, title=title, rating=rating, rating_count=count, offers=list(offers))


def test_total_uses_the_sellers_stated_total():
    offer = pick.offer_from_reply(raw_offer("QVC", 344.99, "$356.71", "+ $11.72"))
    assert offer.total == pytest.approx(356.71)


def test_total_adds_known_shipping_when_no_total_is_stated():
    offer = pick.offer_from_reply(raw_offer("QVC", 344.99, None, "+ $11.72"))
    assert offer.total == pytest.approx(356.71)


def test_free_shipping_adds_nothing():
    offer = pick.offer_from_reply(raw_offer("HSN", 309.99, None, "Free"))
    assert offer.total == pytest.approx(309.99)


def test_unknown_shipping_keeps_the_price():
    offer = pick.offer_from_reply(raw_offer("eBay", 100, None, None))
    assert offer.total == pytest.approx(100.0)
    assert offer.shipping is None


def test_offer_without_a_price_is_dropped():
    assert pick.offer_from_reply(raw_offer("eBay", None)) is None


def test_least_price_compares_totals_not_list_prices():
    with_shipping = Offer(shop="A", price=100, total=130, currency="USD")
    all_in = Offer(shop="B", price=110, total=110, currency="USD")
    found = pick.least_price([product("P1", 4.0, 10, [with_shipping]), product("P2", 4.0, 10, [all_in])])
    assert found[1].shop == "B"


def test_least_price_is_none_without_offers():
    assert pick.least_price([product("P1", 4.0, 10)]) is None


def test_best_reviewed_adjusts_for_review_count():
    few = product("few", 5.0, 2)  # (2 * 5 + 20 * 4) / 22 = 4.09
    many = product("many", 4.5, 1000)  # (1000 * 4.5 + 80) / 1020 = 4.49
    assert pick.best_reviewed([few, many]).title == "many"


def test_best_reviewed_leaves_out_products_without_a_review_count():
    assert pick.best_reviewed([product("no count", 5.0, None)]) is None


def test_star_breakdown_gives_good_neutral_and_bad():
    search_item = {"product_id": "1", "title": "Kettle", "rating": 3.0, "rating_count": 15000}
    offers_data = {
        "product": {
            "title": "Kettle",
            "rating": 4.3,
            "rating_count": 14913,
            "rating_breakdown": [
                {"stars": 1, "count": 2016},
                {"stars": 2, "count": 278},
                {"stars": 3, "count": 434},
                {"stars": 4, "count": 773},
                {"stars": 5, "count": 11412},
            ],
        },
        "offers": [raw_offer("bkstr.com", 35, "$35.00", None)],
        "reviews": [],
    }
    found = pick.product_from_replies(search_item, offers_data)
    assert (found.good, found.neutral, found.bad) == (12185, 434, 2294)
    assert found.sentiment_source == "stars"
    assert found.rating == pytest.approx(4.3)  # offers data wins over the search row
    assert found.rating_count == 14913


def test_without_a_breakdown_review_text_is_labelled_as_a_sample():
    search_item = {"product_id": "1", "title": "Kettle"}
    offers_data = {
        "product": {},
        "offers": [],
        "reviews": [
            {"text": "Absolutely love these, works great"},
            {"text": "Terrible, broke after a day"},
            {"text": "It is a box"},
        ],
    }
    found = pick.product_from_replies(search_item, offers_data)
    assert found.sentiment_source == "sample"
    assert found.good == 1
    assert found.bad == 1
    assert found.neutral == 1


def test_without_any_breakdown_or_text_nothing_is_scored():
    found = pick.product_from_replies({"product_id": "1", "title": "Kettle"}, {"product": {}, "offers": [], "reviews": []})
    assert found.sentiment_source is None
    assert found.good is None
