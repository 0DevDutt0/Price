import pytest

from price_agent.extract import extract_listing, parse_number

PRODUCT_PAGE = """<html><head><script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Product", "name": "Test Kettle",
 "offers": {"@type": "Offer", "price": "49.90", "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"},
 "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.5", "reviewCount": "120"}}
</script></head><body></body></html>"""


def test_product_page_is_read_from_json_ld():
    listing = extract_listing("https://shop.example.com/kettle", PRODUCT_PAGE)
    assert listing.status == "ok"
    assert listing.name == "Test Kettle"
    assert listing.price == pytest.approx(49.9)
    assert listing.currency == "USD"
    assert listing.availability == "InStock"
    assert listing.rating == pytest.approx(4.5)
    assert listing.rating_count == 120
    assert listing.shop == "shop.example.com"


def test_page_without_a_product_is_marked():
    listing = extract_listing("https://shop.example.com/", "<html><body>hello</body></html>")
    assert listing.status == "no_product"


@pytest.mark.parametrize(
    "value, expected",
    [("1.299,00", 1299.0), ("1,299.00", 1299.0), ("12,50", 12.5), ("US$ 49.90", 49.9), (True, None), ("", None)],
)
def test_parse_number_reads_both_separator_styles(value, expected):
    assert parse_number(value) == (pytest.approx(expected) if expected is not None else None)
