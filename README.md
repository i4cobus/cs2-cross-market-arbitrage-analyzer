# CS2_Arb

`CS2_Arb` is a Python project for collecting CS2 market data, normalizing item names across marketplaces, and comparing UU and CSFloat pricing for arbitrage research.

Current implementation includes:

- CSFloat snapshots for lowest ask, highest bid, top bid quantity, 24h sales volume, and 24h average selling price
- UU template search and template-detail snapshot parsing
- Cross-market comparison between UU ask prices and CSFloat ask/bid prices
- Item-name normalization for wear tiers, StatTrak, Souvenir, knives, gloves, and non-floatable items
- CSV snapshot logging for CSFloat runs

The repo is now published as open source for research and learning purposes.

## What Is Finished

- `app/main.py`
  Fetches a CSFloat snapshot for a single item and writes CSV logs.
- `app/csfloat_client.py`
  Handles listing pagination, buy-order lookup, fallback query strategies, and 24h metric aggregation.
- `app/uu_client.py`
  Searches UU templates and parses UU template detail responses into a normalized snapshot structure.
- `app/compare.py`
  Compares UU and CSFloat snapshots and calculates spread against both CSFloat lowest ask and highest bid.
- `app/market_name.py`
  Normalizes Steam / CSFloat market hash names from friendly inputs.

## Project Structure

```text
CS2_Arb/
├─ app/
│  ├─ __init__.py
│  ├─ compare.py
│  ├─ config.py
│  ├─ csfloat_client.py
│  ├─ history.py
│  ├─ logger.py
│  ├─ main.py
│  ├─ market_name.py
│  ├─ quick_probe.py
│  ├─ test.py
│  ├─ uu_client.py
│  └─ wear.py
├─ .env.example
├─ pyproject.toml
└─ README.md
```

## Requirements

- Python `3.11+`
- A CSFloat API key for CSFloat features
- Valid UU request headers for UU features

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

If you do not want editable install:

```bash
pip install httpx python-dotenv
```

## Configuration

Create a `.env` file from `.env.example`.

### Required for CSFloat

```dotenv
CSFLOAT_API_KEY=your_csfloat_api_key
DEFAULT_ITEM=AK-47 | Redline (Field-Tested)
```

### Required for UU

```dotenv
UU_AUTHORIZATION=...
UU_DEVICE_ID=...
UU_DEVICE_UK=...
UU_UK=...
```

### Optional

```dotenv
CNY_USD=0.14
UU_APP_VERSION=5.26.0
UU_SECRET_V=h5_v1
UU_COOKIE=
ANCHOR_BUFFER_PCT=0.00
```

## Usage

### CSFloat snapshot CLI

Fetch one CSFloat snapshot and write logs:

```bash
python3 -m app.main --snapshot "AK-47 | Fire Serpent" --wear mw --category normal
```

Quick probe without writing logs:

```bash
python3 -m app.main --snapshot "Music Kit | Skog, Metal" --category stattrak --probe --debug
```

### UU + CSFloat comparison workflow

There is not yet a dedicated comparison CLI. The finished comparison flow currently lives in the Python modules and in `app/test.py`.

Minimal example:

```python
from app.csfloat_client import fetch_snapshot_by_params
from app.uu_client import search_and_get_snapshot
from app.compare import compare_snapshots

cs_snapshot = fetch_snapshot_by_params(
    base_name="Sport Gloves | Nocts",
    wear_key="ft",
    category_key="normal",
)

uu_snapshot = search_and_get_snapshot("夜行衣", index=0)

result = compare_snapshots(cs_snapshot, uu_snapshot, cny_to_usd=0.14)
print(result)
```

You can also run the existing manual integration harness:

```bash
python3 -m app.test
```

That script is intended for developer verification, not as a polished end-user interface.

## Output

### CSFloat snapshot fields

- `lowest_ask`
- `lowest_ask_id`
- `highest_bid`
- `highest_bid_qty`
- `vol24h`
- `asp24h`
- `used_category`
- `used_wear`
- `source`
- `is_floatable`

### Comparison fields

- `uu_lowest_ask_cny`
- `uu_lowest_ask_usd`
- `cs_lowest_ask_usd`
- `cs_highest_bid_usd`
- `spread_to_cs_lowest_usd`
- `spread_to_cs_lowest_pct`
- `spread_to_cs_bid_usd`
- `spread_to_cs_bid_pct`

## Logging

Running `app.main` writes:

- `logs/csfloat_snapshots.csv` for append-only history
- `logs/csfloat_snapshot_latest.csv` for the latest snapshot only

## Notes

- Wear filters are automatically disabled for non-floatable item families such as music kits, stickers, agents, graffiti, cases, and charms.
- The UU integration depends on authenticated request headers and may break if UU changes its private API behavior.
- The current repo contains comparison logic and integration helpers, but not yet a production-grade scan pipeline or dashboard.

## Development Status

Implemented:

- CSFloat data collection
- UU template lookup
- Cross-market comparison logic
- Market-hash-name normalization
- CSV logging

Not yet implemented:

- Batch scanner / ranked opportunity report
- Unified CLI for UU comparison
- Automated tests
- Historical analytics dashboard

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
