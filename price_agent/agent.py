"""One research pass: search datawebot, open sellers for the top results, then pick."""

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
    searched_at: str | None = None  # meta.as_of from the search reply
    without_offers: int = 0  # search results datawebot could not give sellers for
    skipped: list[str] = field(default_factory=list)  # products whose offers call failed
    searches_left: int | None = None  # meta.searches_left_today from the latest reply

    def least_price(self) -> tuple[Product, Offer] | None:
        return pick.least_price(self.products)

    def best_reviewed(self) -> Product | None:
        return pick.best_reviewed(self.products)


def research(client: DataWebotClient, query: str, country: str = "US", limit: int = 3) -> Report:
    """Each opened result is one more call against today's search allowance, so limit caps the seller lookups."""
    search = client.search_products(query, country=country, limit=limit)
    report = Report(query=query, country=country, searched_at=(search.get("meta") or {}).get("as_of"))
    _note_searches_left(report, search)
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
        _note_searches_left(report, offers)
        as_of = (offers.get("meta") or {}).get("as_of")
        report.products.append(pick.product_from_replies(item, offers.get("data") or {}, as_of=as_of))
    return report


def _note_searches_left(report: Report, reply: dict[str, Any]) -> None:
    meta = reply.get("meta") or {}
    report.searches_left = meta.get("searches_left_today", report.searches_left)
