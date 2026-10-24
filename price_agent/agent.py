"""One research pass: search DataWebot, open sellers for the top results, then pick."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import pick
from .datawebot import DataWebotClient, DataWebotError
from .models import Offer, Product

# These errors would hit every later call too, so the run stops instead of carrying on.
STOP_CODES = {"login_required", "rate_limited", "insufficient_credits", "network_error"}


@dataclass
class Report:
    query: str
    country: str
    products: list[Product] = field(default_factory=list)
    without_offers: int = 0  # search results DataWebot could not give sellers for
    skipped: list[str] = field(default_factory=list)  # products whose offers call failed
    searches_left: int | None = None
    as_of: str | None = None

    def least_price(self) -> tuple[Product, Offer] | None:
        return pick.least_price(self.products)

    def best_reviewed(self) -> Product | None:
        return pick.best_reviewed(self.products)


def research(client: DataWebotClient, query: str, country: str = "US", limit: int = 3) -> Report:
    """Each opened result costs one unit of the daily allowance, so limit is the budget for sellers."""
    search = client.search_products(query, country=country, limit=limit)
    report = Report(query=query, country=country)
    _note_meta(report, search)
    results = (search.get("data") or {}).get("results") or []
    listed = [item for item in results if item.get("has_offers")]
    report.without_offers = len(results) - len(listed)
    for item in listed[:limit]:
        try:
            offers = client.get_product_offers(str(item["product_id"]), query=query, country=country)
        except DataWebotError as error:
            if error.code in STOP_CODES:
                raise
            report.skipped.append(f"{item.get('title', 'untitled')}: {error}")
            continue
        _note_meta(report, offers)
        report.products.append(pick.product_from_replies(item, offers.get("data") or {}))
    return report


def _note_meta(report: Report, reply: dict[str, Any]) -> None:
    meta = reply.get("meta") or {}
    report.searches_left = meta.get("searches_left_today", report.searches_left)
    report.as_of = meta.get("as_of", report.as_of)
