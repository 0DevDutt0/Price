"""Turn DataWebot replies into products with sellers, sentiment counts and the two picks."""

from __future__ import annotations

from typing import Any

from . import sentiment
from .extract import parse_number
from .models import Offer, Product

PRIOR_MEAN = 4.0  # rating assumed for a product before its reviews are counted
PRIOR_WEIGHT = 20  # how many reviews that assumed rating is worth


def offer_from_reply(raw: dict[str, Any]) -> Offer | None:
    """Read one seller row. The total is the seller's stated total, else the price plus known shipping."""
    price = parse_number(raw.get("price"))
    if price is None:
        return None
    total = parse_number(raw.get("total_text"))
    if total is None:
        shipping = raw.get("shipping_text") or ""
        extra = 0.0 if "free" in shipping.lower() else parse_number(shipping)
        total = price + extra if extra is not None else price
    return Offer(
        shop=raw.get("shop") or "unknown shop",
        price=price,
        total=total,
        currency=raw.get("currency"),
        url=raw.get("url"),
        shipping=raw.get("shipping_text"),
    )


def count_stars(breakdown: list[dict[str, Any]] | None) -> dict[int, int]:
    """DataWebot's rating_breakdown, a list of {"stars": 1-5, "count": n}, as {stars: count}."""
    counts: dict[int, int] = {}
    for row in breakdown or []:
        stars, count = row.get("stars"), row.get("count")
        if isinstance(stars, int) and isinstance(count, int) and 1 <= stars <= 5:
            counts[stars] = counts.get(stars, 0) + count
    return counts


def product_from_replies(search_item: dict[str, Any], offers_data: dict[str, Any]) -> Product:
    """Combine one search row with its get_product_offers data. Offers data wins where both have a value."""
    info = offers_data.get("product") or {}
    rating = info.get("rating") if info.get("rating") is not None else search_item.get("rating")
    count = info.get("rating_count") if info.get("rating_count") is not None else search_item.get("rating_count")
    review_texts = [r["text"] for r in offers_data.get("reviews") or [] if isinstance(r, dict) and r.get("text")]
    product = Product(
        product_id=str(search_item["product_id"]),
        title=info.get("title") or search_item.get("title") or "untitled",
        rating=float(rating) if rating is not None else None,
        rating_count=int(count) if count is not None else None,
        offers=[offer for offer in map(offer_from_reply, offers_data.get("offers") or []) if offer],
        review_texts=review_texts,
    )
    stars = count_stars(info.get("rating_breakdown"))
    if stars:
        product.good = stars.get(4, 0) + stars.get(5, 0)
        product.bad = stars.get(1, 0) + stars.get(2, 0)
        product.neutral = stars.get(3, 0)
        product.sentiment_source = "stars"
    elif review_texts:
        # No star breakdown: label the few review texts we have with VADER, and say so in the report.
        counts = sentiment.summarize(review_texts)
        product.good, product.bad, product.neutral = counts["good"], counts["bad"], counts["neutral"]
        product.sentiment_source = "sample"
    return product


def least_price(products: list[Product]) -> tuple[Product, Offer] | None:
    """The lowest total across every seller of every product."""
    options = [(product, offer) for product in products for offer in product.offers]
    return min(options, key=lambda option: option[1].total, default=None)


def bayesian_rating(rating: float, count: int) -> float:
    """Pull a rating toward the prior mean when few reviews back it up."""
    return (count * rating + PRIOR_WEIGHT * PRIOR_MEAN) / (count + PRIOR_WEIGHT)


def best_reviewed(products: list[Product]) -> Product | None:
    """The highest adjusted rating. Products without a rating or a review count are left out."""
    rated = [p for p in products if p.rating is not None and p.rating_count is not None]
    return max(rated, key=lambda p: bayesian_rating(p.rating, p.rating_count), default=None)
