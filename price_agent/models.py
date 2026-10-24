"""The data the agent collects for one product link."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Listing:
    url: str
    status: str = "pending"  # ok, no_price, no_product, robots_disallowed, fetch_failed, invalid_url
    source: str = ""  # cache, http or browser
    name: str | None = None
    shop: str | None = None
    currency: str | None = None
    price: float | None = None
    availability: str | None = None
    rating: float | None = None  # always on a 0-5 scale
    rating_count: int | None = None
    review_texts: list[str] = field(default_factory=list)
    good: int | None = None  # None means the page exposed no review text to score
    bad: int | None = None
    neutral: int | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class Offer:
    """One seller's offer for a product, from DataWebot's get_product_offers."""

    shop: str
    price: float
    total: float  # the seller's total with shipping when it is stated, otherwise the price
    currency: str | None = None
    url: str | None = None
    shipping: str | None = None  # the seller's shipping text as given, e.g. "Free" or "+ $11.72"


@dataclass
class Product:
    """A product from a DataWebot search, with its sellers and review sentiment."""

    product_id: str
    title: str
    rating: float | None = None  # 0-5 scale
    rating_count: int | None = None
    offers: list[Offer] = field(default_factory=list)
    review_texts: list[str] = field(default_factory=list)
    good: int | None = None
    bad: int | None = None
    neutral: int | None = None
    sentiment_source: str | None = None  # "stars" = DataWebot's star breakdown, "sample" = VADER on review texts

    def cheapest(self) -> Offer | None:
        return min(self.offers, key=lambda offer: offer.total, default=None)
