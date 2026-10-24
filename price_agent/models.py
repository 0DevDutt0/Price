"""Data classes for datawebot search and offers results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Offer:
    """One seller's offer for a product, from datawebot's get_product_offers."""

    shop: str
    price: float
    total: float  # the seller's total with shipping when it is stated, otherwise the price
    currency: str | None = None
    url: str | None = None
    shipping: str | None = None  # the seller's shipping text as given, e.g. "Free" or "+ $11.72"


@dataclass
class Product:
    """A product from a datawebot search, with its sellers and review sentiment."""

    product_id: str
    title: str
    rating: float | None = None  # 0-5 scale
    rating_count: int | None = None
    offers: list[Offer] = field(default_factory=list)
    review_texts: list[str] = field(default_factory=list)
    good: int | None = None
    bad: int | None = None
    neutral: int | None = None
    sentiment_source: str | None = None  # "stars" = datawebot's star breakdown, "sample" = VADER on review texts
    as_of: str | None = None  # when datawebot retrieved these offers (meta.as_of); prices are snapshots, not live

    def cheapest(self) -> Offer | None:
        return min(self.offers, key=lambda offer: offer.total, default=None)
