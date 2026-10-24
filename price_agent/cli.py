"""Command line entry point: python -m price_agent "<product>" [--country US] [--limit 3]."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

from . import pick
from .agent import Report, research
from .datawebot import DataWebotClient, DataWebotError, load_api_key
from .models import Offer, Product

NOTICE = (
    "These are datawebot snapshots, not live prices. Each price shows when it was retrieved.\n"
    "Sentiment is VADER on the few review texts datawebot returns, unless it also returns a star breakdown "
    "for that product (shown per product)."
)


def format_report(report: Report) -> str:
    header = f'Results for "{report.query}" in {report.country}, search retrieved {_when(report.searched_at)}.'
    lines = [header, NOTICE, ""]
    if not report.products:
        lines.append("No product with seller offers was found for this search.")
    for product in report.products:
        lines.extend(_product_lines(product))
        lines.append("")
    least = report.least_price()
    if least:
        product, offer = least
        lines.append(
            f"Least price: {_money(offer.total, offer.currency)} at {offer.shop} for {product.title} "
            f"(retrieved {_when(product.as_of)})"
        )
    best = report.best_reviewed()
    if best:
        adjusted = pick.bayesian_rating(best.rating, best.rating_count)
        lines.append(
            f"Best reviewed: {best.title} (rating {best.rating:.1f} from {best.rating_count} reviews, "
            f"adjusted {adjusted:.2f}; retrieved {_when(best.as_of)})"
        )
    if report.without_offers:
        lines.append(f"{report.without_offers} search result(s) had no seller offers and were skipped.")
    for message in report.skipped:
        lines.append(f"Skipped: {message}")
    if report.searches_left is not None:
        lines.append(f"Searches left today: {report.searches_left}")
    return "\n".join(lines)


def _product_lines(product: Product) -> list[str]:
    lines = [product.title]
    offer = product.cheapest()
    if offer:
        lines.append(
            f"  Lowest seller: {_money(offer.total, offer.currency)} at {offer.shop} "
            f"(retrieved {_when(product.as_of)})"
        )
        if offer.url:
            lines.append(f"  {offer.url}")
    else:
        lines.append("  No seller price found.")
    if product.rating is not None:
        lines.append(f"  Rating {product.rating:.1f} from {product.rating_count or 'unknown'} reviews")
    lines.append(_sentiment_line(product))
    return lines


def _sentiment_line(product: Product) -> str:
    if product.sentiment_source == "stars":
        return f"  Star breakdown: good {product.good}, neutral {product.neutral}, bad {product.bad}"
    if product.sentiment_source == "sample":
        return (
            f"  VADER on {len(product.review_texts)} review text(s): "
            f"good {product.good}, neutral {product.neutral}, bad {product.bad}"
        )
    return "  No star breakdown or review text to score."


def _money(amount: float, currency: str | None) -> str:
    return f"{amount:.2f} {currency}" if currency else f"{amount:.2f}"


def _when(as_of: str | None) -> str:
    """Format datawebot's meta.as_of (ISO 8601, UTC) for people to read."""
    if not as_of:
        return "time not reported"
    try:
        moment = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    except ValueError:
        return as_of
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def main(argv: list[str] | None = None) -> int:
    # Product titles can hold characters the Windows console cannot print; replace them instead of crashing.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        prog="python -m price_agent",
        description="Compare sellers, prices and review sentiment for one product, using datawebot.",
    )
    parser.add_argument("query", help='What to look for, for example "Sony WH-1000XM5".')
    parser.add_argument("--country", default="US", help="Two-letter market code (default: US).")
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Search results to open for sellers (default: 3). Each one is an extra call against today's search allowance.",
    )
    args = parser.parse_args(argv)
    query = args.query.strip()
    country = args.country.upper()
    if not 2 <= len(query) <= 200:
        parser.error("the query must be 2 to 200 characters")
    if not re.fullmatch(r"[A-Z]{2}", country):
        parser.error("--country must be a two-letter code such as US")
    if not 1 <= args.limit <= 10:
        parser.error("--limit must be between 1 and 10")
    try:
        with DataWebotClient(load_api_key()) as client:
            report = research(client, query, country=country, limit=args.limit)
    except DataWebotError as error:
        print(f"Error ({error.code}): {error}", file=sys.stderr)
        return 1
    print(format_report(report))
    return 0
