import pytest

from price_agent.agent import Report
from price_agent.cli import NOTICE, format_report, main
from price_agent.models import Offer, Product


def test_report_shows_snapshot_times_sentiment_and_both_picks():
    kettle = Product(
        product_id="1",
        title="Test Kettle",
        rating=4.5,
        rating_count=120,
        offers=[Offer(shop="shop.example", price=20, total=25, currency="USD", url="https://shop.example/kettle")],
        good=100,
        neutral=10,
        bad=10,
        sentiment_source="stars",
        as_of="2026-10-24T12:09:34.967Z",
    )
    text = format_report(Report(query="kettle", country="US", products=[kettle], searches_left=12))
    assert NOTICE in text
    assert "Lowest seller: 25.00 USD at shop.example (retrieved 2026-10-24 12:09 UTC)" in text
    assert "Star breakdown: good 100, neutral 10, bad 10" in text
    assert "Least price: 25.00 USD at shop.example for Test Kettle (retrieved 2026-10-24 12:09 UTC)" in text
    assert "Best reviewed: Test Kettle" in text
    assert "Searches left today: 12" in text


def test_sample_sentiment_is_labelled_as_vader():
    kettle = Product(
        product_id="1",
        title="Kettle",
        review_texts=["a", "b"],
        good=1,
        neutral=0,
        bad=1,
        sentiment_source="sample",
    )
    text = format_report(Report(query="kettle", country="US", products=[kettle]))
    assert "VADER on 2 review text(s): good 1, neutral 0, bad 1" in text


def test_missing_retrieval_time_is_said_plainly():
    kettle = Product(product_id="1", title="Kettle", offers=[Offer(shop="s", price=5, total=5, currency="USD")])
    text = format_report(Report(query="kettle", country="US", products=[kettle]))
    assert "(retrieved time not reported)" in text


def test_report_with_no_products_says_so():
    text = format_report(Report(query="kettle", country="US"))
    assert "No product with seller offers was found" in text


def test_invalid_country_is_rejected(capsys):
    with pytest.raises(SystemExit):
        main(["kettle", "--country", "USA"])
    assert "two-letter code" in capsys.readouterr().err
