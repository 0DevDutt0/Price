"""Read a product page's structured data (JSON-LD and Open Graph) into a Listing."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit

import extruct

from .models import Listing

PRODUCT_TYPES = {"Product", "ProductGroup", "IndividualProduct", "ProductModel"}
MAX_REVIEWS = 200


def extract_listing(url: str, html: str, source: str = "http") -> Listing:
    """Build a Listing from one page. Anything the page does not publish stays None."""
    listing = Listing(url=url, source=source, shop=_shop_name(url))
    try:
        data = extruct.extract(html, base_url=url, syntaxes=["json-ld", "opengraph"], uniform=False)
    except Exception as error:  # extruct can fail on badly broken markup; report it instead of crashing
        listing.status = "no_product"
        listing.notes.append(f"could not parse the page ({type(error).__name__})")
        return listing

    nodes = [node for block in data.get("json-ld", []) for node in _walk(block)]
    og = _open_graph(data.get("opengraph", []))
    product = next((n for n in nodes if (_types(n) & PRODUCT_TYPES) and (n.get("name") or n.get("offers"))), None)
    if product is None and og.get("og:type") != "product":
        listing.status = "no_product"
        return listing

    listing.name = (product or {}).get("name") or og.get("og:title")
    listing.price, listing.currency, listing.availability = _price(product or {}, og, listing)
    listing.rating, listing.rating_count = _rating(nodes)
    listing.review_texts = _review_texts(nodes)
    listing.status = "ok" if listing.price is not None else "no_price"
    if listing.status == "no_price":
        listing.notes.append("no price found in the page's structured data")
    return listing


def parse_number(value: Any) -> float | None:
    """Read a price or rating such as 1299, "1,299.00", "1.299,00" or "US$ 49.90"."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = re.sub(r"[^0-9.,-]", "", value)
    if not re.search(r"\d", text):
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):  # 1.299,00: dots group thousands, the comma is the decimal mark
            text = text.replace(".", "").replace(",", ".")
        else:  # 1,299.00
            text = text.replace(",", "")
    elif "," in text:  # 12,50 is a decimal comma; 1,299 is a thousands separator
        text = text.replace(",", ".") if re.search(r",\d{1,2}$", text) else text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _price(product: dict, og: dict, listing: Listing) -> tuple[float | None, str | None, str | None]:
    og_currency = og.get("product:price:currency") or og.get("og:price:currency")

    direct = [o for o in _as_list(product.get("offers")) if isinstance(o, dict) and _offer_price(o) is not None]
    if direct:
        offer = min(direct, key=_offer_price)
        return _offer_price(offer), offer.get("priceCurrency") or og_currency, _short(offer.get("availability"))

    variants = [
        o
        for v in _as_list(product.get("hasVariant"))
        if isinstance(v, dict)
        for o in _as_list(v.get("offers"))
        if isinstance(o, dict) and _offer_price(o) is not None
    ]
    if variants:
        offer = min(variants, key=_offer_price)
        listing.notes.append("price is the lowest variant price, not the price of one specific variant")
        return _offer_price(offer), offer.get("priceCurrency") or og_currency, _short(offer.get("availability"))

    amount = parse_number(og.get("product:price:amount") or og.get("og:price:amount"))
    if amount is not None:
        listing.notes.append("price read from Open Graph tags")
        return amount, og_currency, None
    return None, None, None


def _offer_price(offer: dict) -> float | None:
    raw = offer.get("price") if offer.get("price") is not None else offer.get("lowPrice")
    return parse_number(raw)


def _rating(nodes: list[dict]) -> tuple[float | None, int | None]:
    best: tuple[int, float, int | None] | None = None
    for node in nodes:
        if "AggregateRating" not in _types(node):
            continue
        value = parse_number(node.get("ratingValue"))
        if value is None:
            continue
        scale = parse_number(node.get("bestRating")) or 5.0
        raw_count = node.get("reviewCount") if node.get("reviewCount") is not None else node.get("ratingCount")
        count = _integer(raw_count)
        candidate = (count or 0, round(value * 5.0 / scale, 2), count)
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        return None, None
    return best[1], best[2]


def _review_texts(nodes: list[dict]) -> list[str]:
    texts: list[str] = []
    for node in nodes:
        if "Review" not in _types(node):
            continue
        body = node.get("reviewBody") or node.get("description")
        if not isinstance(body, str):
            continue
        body = " ".join(body.split())
        if body and body not in texts:
            texts.append(body)
        if len(texts) >= MAX_REVIEWS:
            break
    return texts


def _open_graph(items: list[dict]) -> dict[str, str]:
    properties: dict[str, str] = {}
    for item in items:
        for name, value in item.get("properties", []):
            properties.setdefault(name, value)
    return properties


def _walk(node: Any) -> Iterator[dict]:
    if isinstance(node, dict):
        yield node
        for child in node.values():
            yield from _walk(child)
    elif isinstance(node, list):
        for child in node:
            yield from _walk(child)


def _types(node: dict) -> set[str]:
    raw = node.get("@type", [])
    if isinstance(raw, str):
        raw = [raw]
    return {t.rsplit("/", 1)[-1].rsplit("#", 1)[-1] for t in raw if isinstance(t, str)}


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _short(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value.rsplit("/", 1)[-1]
    return None


def _integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    digits = re.sub(r"\D", "", str(value))
    return int(digits) if digits else None


def _shop_name(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host
