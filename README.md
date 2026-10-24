# Price research agent

Compares sellers, prices and review sentiment for one product. It uses DataWebot's
`search_products` and `get_product_offers` tools. It does not use Jobs, which cost credits.

## Sample run

Real output from 2026-10-24, with `python -m price_agent "Apple AirPods Pro 2" --limit 2`:

```
Results for "Apple AirPods Pro 2" in US.
These are DataWebot snapshots, not live prices. Each price shows when it was retrieved.
Sentiment is VADER on the few review texts DataWebot returns, unless it also returns a star breakdown for that product (shown per product).

Apple AirPods Pro with MagSafe Case
  Lowest seller: 35.00 USD at bkstr.com (retrieved 2026-10-24 12:30 UTC)
  https://www.bkstr.com/tcatknoxvillestore/product/airpods-pro--2nd-generation--with-magsafe-case--usb-c--364639-1
  Rating 4.3 from 14913 reviews
  Star breakdown: good 12185, neutral 434, bad 2294

Apple AirPods Pro (2nd Generation) with MagSafe Case (usbc), White
  Lowest seller: 139.99 USD at Walmart - Cellfeee (retrieved 2026-10-24 12:30 UTC)
  https://www.walmart.com/ip/Apple-AirPods-Pro-2nd-Gen-with-MagSafe-USB-C-Charging-Case/15509659574?wmlspartner=wlpa&selectedSellerId=3652&veh=seo_fpl&cn=google
  No star breakdown or review text to score.

Least price: 35.00 USD at bkstr.com for Apple AirPods Pro with MagSafe Case (retrieved 2026-10-24 12:30 UTC)
Best reviewed: Apple AirPods Pro with MagSafe Case (rating 4.3 from 14913 reviews, adjusted 4.30; retrieved 2026-10-24 12:30 UTC)
Searches left today: 31
```

The second product has no rating or reviews in this reply, so the agent reports that it has nothing to score.

## Setup

Install the requirements into a virtual environment:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

The agent needs a DataWebot key. Either set `DATAWEBOT_API_KEY`, or sign in to DataWebot so the key is saved to
`%USERPROFILE%\.datawebot\credentials`. Never commit the key or that folder. DataWebot's setup guide says keys
last 30 days. When the agent reports `login_required`, sign in again.

## Usage

```
python -m price_agent "Apple AirPods Pro 2"
python -m price_agent "Sony WH-1000XM5" --country US --limit 3
```

- `--country` takes a two-letter market code. The default is `US`.
- `--limit` is how many search results to open for sellers. The default is 3.

## What the numbers mean

- **Prices are snapshots.** Each price shows `meta.as_of`, the time DataWebot retrieved it. Check it before you
  rely on a price. DataWebot's search results describe prices as best-effort and possibly out of date.
- **Least price** is the lowest seller total across all products. The total is the seller's stated total with
  shipping, or the price plus known shipping when only the shipping is stated. Unknown shipping counts as zero.
- **Best reviewed** is the highest rating adjusted for review count: `(n × rating + 20 × 4.0) / (n + 20)`.
  Products without a rating or review count are left out.
- **Sentiment** is VADER on the few review texts DataWebot returns, unless the product also has a star
  breakdown. DataWebot's `get_product_offers` description mentions an overall rating and breakdown, and the live
  replies in our runs included a star-count breakdown for some products. The public setup guide doesn't describe
  its format, so the agent uses it when present and says which source it used.
  Good means 4 or 5 stars and bad means 1 or 2 stars.
- **Daily allowance.** DataWebot's public documentation says each account has a daily allowance, without a
  size. The agent doesn't assume one. Each search and each offers call reduces `meta.searches_left_today`,
  which the report prints. In our runs each call reduced it by exactly one.
- **Errors.** `login_required` means sign in again. `rate_limited` means the daily allowance is used up or
  DataWebot is limiting the account, so try later. The agent stops on these and on network errors.
  `insufficient_credits` only applies to Jobs, which this agent does not use.

## Tests

```
python -m pytest
```

The tests use mocked HTTP and fake clients, so they use no daily allowance.

## Layout

| File | Role |
|---|---|
| `price_agent/datawebot.py` | JSON-RPC client for `https://mcp.datawebot.com/mcp`, key loading, error codes |
| `price_agent/agent.py` | One research pass: search, then offers for the top results |
| `price_agent/pick.py` | Number parsing, sellers and totals, sentiment counts, the two picks |
| `price_agent/cli.py` | Command line and report formatting |
| `price_agent/models.py` | Offer and product data classes |
| `price_agent/sentiment.py` | VADER labels for review text |

## Not included

- **Reading product pages directly.** This repo doesn't read shop pages. DataWebot is the only data source.
- **Jobs.** They cost credits. The agent doesn't submit them.
- **Product links as input.** Only search terms are accepted for now.
