# Price research agent

Compares sellers, prices and review sentiment for one product. The main data source is
DataWebot's `search_products` and `get_product_offers`. The core path is free: it uses only the
daily search allowance, not the paid Jobs credits.

## Setup

Use the venv in `E:\Price\Price` (or create your own) and install the requirements:

```
E:\Price\Price\Scripts\python.exe -m pip install -r requirements-dev.txt
```

DataWebot sign-in saves a key to `%USERPROFILE%\.datawebot\credentials`. To use another key, set
`DATAWEBOT_API_KEY`. Keys last 30 days according to DataWebot's setup guide, so sign in again when
the agent reports `login_required`. Never commit the key or the credentials file.

## Usage

```
python -m price_agent "Apple AirPods Pro 2"
python -m price_agent "Sony WH-1000XM5" --country US --limit 3
```

- `--limit` is how many search results to open for sellers. Each one costs one daily unit, plus the
  search itself. The default is 3, so one run uses up to 4 units of the 50-unit daily allowance.
- The output lists each product's lowest seller total (price plus shipping when the seller states
  it), its rating, and good, neutral and bad counts. It ends with two picks:
  - **Least price:** the lowest seller total across all products.
  - **Best reviewed:** the highest rating adjusted for review count, `(n × rating + 20 × 4.0) / (n + 20)`.
    Products without a rating or a review count are left out.
- Sentiment comes from DataWebot's star breakdown when it is present (4 and 5 stars count as good,
  1 and 2 as bad). Otherwise the few review texts are labelled with VADER, and the report says it is a
  sample.

Prices are best-effort and may be out of date.

## Tests

```
python -m pytest
```

The tests use mocked HTTP and fake clients, so they use no daily units.

## Layout

| File | Role |
|---|---|
| `price_agent/datawebot.py` | JSON-RPC client for `https://mcp.datawebot.com/mcp`, key loading, error codes |
| `price_agent/agent.py` | One research pass: search, then offers for the top results |
| `price_agent/pick.py` | Sellers, totals, sentiment counts and the two picks |
| `price_agent/cli.py` | Command line and report formatting |
| `price_agent/extract.py`, `models.py`, `sentiment.py` | Direct page reading (JSON-LD and Open Graph), data classes, VADER labels |

## Not built yet

- Product links as input. The plan is to read the page title for free first, then search by that title.
- Direct page reading as a fallback when DataWebot returns nothing. `extract.py` is written but not yet
  wired into the CLI, and robots.txt checks are not written.
- Jobs (scraping). They cost credits and are avoided in the core.
