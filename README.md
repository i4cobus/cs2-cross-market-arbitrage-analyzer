# CS2 Cross-Market Pricing Intelligence System

This project is a Python data application that collects marketplace data, normalizes item identities across platforms, builds structured analytical datasets, engineers business indicators, ranks opportunities, runs SQL analytics, and exposes an LLM-ready natural-language analysis interface.

The domain is CS2 marketplace pricing, but the engineering focus is broader: API ingestion, data cleaning, feature engineering, recommendation ranking, SQL analytics, data quality checks, and LLM-style question answering over structured data.

## Recruiter Summary

- Built an end-to-end Python data pipeline that ingests data from CSFloat and YouPin APIs.
- Normalized cross-market item names using Steam `market_hash_name` conventions.
- Generated structured datasets for cross-market pricing, liquidity, spread, demand, and risk analysis.
- Engineered business indicators including profit margin, instant-exit margin, liquidity score, demand score, supply score, risk score, and opportunity score.
- Built an explainable recommendation layer that ranks market opportunities and provides human-readable reasons.
- Added SQL analytics over generated datasets using in-memory SQLite.
- Added an LLM-ready analyst that maps natural-language questions to vetted SQL analytics and returns grounded summaries.
- Added automated unit tests for parsers, feature engineering, recommendation ranking, SQL analytics, and natural-language routing.

## Architecture

```text
data/watchlist.csv
  -> CSFloat API client
  -> YouPin API client
  -> market_hash_name normalization
  -> data/opportunity_snapshots.csv
  -> feature engineering
  -> data/opportunity_features.csv
  -> recommendation ranking
  -> data/recommendations.csv
  -> SQL analytics
  -> LLM-ready natural-language analyst
```

## Skills Demonstrated

- Python programming
- API integration
- Data pipeline engineering
- CSV dataset construction
- Feature engineering
- Recommendation and ranking logic
- SQL analytics
- Data quality governance
- Unit testing
- Git-oriented project organization
- LLM-ready retrieval and analysis workflow

## Project Structure

```text
cs2-cross-market-arbitrage-analyzer/
├─ app/
│  ├─ analytics.py
│  ├─ compare.py
│  ├─ config.py
│  ├─ csfloat_client.py
│  ├─ dataset_builder.py
│  ├─ features.py
│  ├─ history.py
│  ├─ llm_analyst.py
│  ├─ manual_integration.py
│  ├─ market_name.py
│  ├─ recommender.py
│  ├─ uu_client.py
│  └─ wear.py
├─ data/
│  ├─ watchlist.csv
│  ├─ opportunity_snapshots.csv
│  ├─ opportunity_features.csv
│  └─ recommendations.csv
├─ sql/
│  ├─ data_quality_report.sql
│  ├─ label_distribution.sql
│  ├─ liquidity_analysis.sql
│  └─ top_opportunities.sql
├─ tests/
│  ├─ test_analytics.py
│  ├─ test_dataset_builder.py
│  ├─ test_features.py
│  ├─ test_llm_analyst.py
│  ├─ test_market_name.py
│  ├─ test_recommender.py
│  └─ test_uu_client.py
├─ .env.example
├─ pyproject.toml
└─ README.md
```

## End-To-End Demo

Build the snapshot dataset:

```bash
python3 -m app.dataset_builder --overwrite
```

Compute business indicators:

```bash
python3 -m app.features --top 10
```

Build ranked recommendations:

```bash
python3 -m app.recommender --min-label watchlist --top 10
```

Run SQL analytics:

```bash
python3 -m app.analytics --query sql/top_opportunities.sql --limit 10
python3 -m app.analytics --query sql/data_quality_report.sql
python3 -m app.analytics --query sql/label_distribution.sql
python3 -m app.analytics --query sql/liquidity_analysis.sql
```

Ask natural-language analytics questions:

```bash
python3 -m app.llm_analyst "Which items are strong candidates and why?"
python3 -m app.llm_analyst "Summarize data quality"
python3 -m app.llm_analyst "Show label distribution"
python3 -m app.llm_analyst "Which items have strong liquidity?"
```

Example analyst output:

```text
Question: Summarize data quality
Intent: data_quality
SQL used: sql/data_quality_report.sql

Dataset quality summary: 76 rows, 100.0% match rate, 100.0% OK rows, 0 missing UU asks, 0 missing UU bids, 1 missing CS bids, and 37 rows with negative instant-exit margin.
```

## Business Indicators

`profit_margin_pct`

```text
(cs_lowest_ask_usd - uu_lowest_ask_usd) / uu_lowest_ask_usd
```

Measures theoretical spread against the CSFloat lowest ask.

`instant_exit_margin_pct`

```text
(cs_highest_bid_usd - uu_lowest_ask_usd) / uu_lowest_ask_usd
```

Measures stricter executable spread against the CSFloat highest bid.

`cs_liquidity_score`

```text
0.65 * log_score(cs_vol24h, 50)
+ 0.35 * log_score(cs_bid_depth, 20)
```

Estimates exit liquidity using CSFloat 24h volume and bid depth.

`uu_supply_score`

```text
0.70 * log_score(uu_listings, 100)
+ 0.30 * log_score(uu_bid_depth, 50)
```

Estimates source-side supply and YouPin buy-order activity.

`demand_score`

```text
0.75 * log_score(cs_vol24h, 50)
+ 0.25 * log_score(uu_bid_depth, 50)
```

Combines recent CSFloat sales volume and YouPin bid depth.

`risk_score`

Penalizes missing margin, negative margin, thin margin, low liquidity, low supply, and weak data quality.

`opportunity_score`

```text
0.35 * profit_score
+ 0.25 * cs_liquidity_score
+ 0.20 * demand_score
+ 0.10 * uu_supply_score
+ 0.10 * data_quality_score
- 0.20 * risk_score
```

Final explainable ranking score.

## Recommendation Layer

The recommender reads `data/opportunity_features.csv`, filters opportunities by label, ranks them, and writes `data/recommendations.csv`.

Recommendation labels:

- `strong_candidate`
- `watchlist`
- `low_priority`
- `avoid`
- `insufficient_data`

Each recommendation includes a reason string such as:

```text
high instant-exit margin; strong CSFloat liquidity; strong demand signal; controlled risk
```

## SQL Analytics

The analytics layer loads generated CSV datasets into in-memory SQLite tables:

- `features`
- `recommendations`

Included queries:

- `sql/top_opportunities.sql`
- `sql/data_quality_report.sql`
- `sql/label_distribution.sql`
- `sql/liquidity_analysis.sql`

This demonstrates relational analytics over generated data without requiring an external database service.

## LLM-Ready Analyst

`app/llm_analyst.py` is a safe retrieval layer for natural-language data analysis.

It does not invent answers. It:

1. Classifies the user question.
2. Selects a vetted SQL query.
3. Runs SQL over generated datasets.
4. Summarizes the returned rows.

Supported intents:

- `top_opportunities`
- `data_quality`
- `label_distribution`
- `liquidity`

This can later be connected to an external LLM summarizer, but the current implementation is deterministic, testable, and grounded in retrieved data.

## Dataset Outputs

`data/opportunity_snapshots.csv`

Raw cross-market snapshot dataset.

Important columns:

- `market_hash_name`
- `cs_lowest_ask_usd`
- `cs_highest_bid_usd`
- `cs_vol24h`
- `cs_asp24h`
- `uu_lowest_ask_usd`
- `uu_highest_bid_usd`
- `uu_bid_depth`
- `uu_listings`
- `spread_to_cs_bid_pct`
- `data_quality_flag`

`data/opportunity_features.csv`

Feature-engineered dataset with business indicators.

Important columns:

- `profit_margin_pct`
- `instant_exit_margin_pct`
- `cs_liquidity_score`
- `uu_supply_score`
- `demand_score`
- `risk_score`
- `opportunity_score`
- `recommendation_label`

`data/recommendations.csv`

Ranked and explainable recommendations.

Important columns:

- `rank`
- `market_hash_name`
- `recommendation_label`
- `opportunity_score`
- `instant_exit_margin_pct`
- `risk_score`
- `recommendation_reason`

## Testing

Run all tests:

```bash
python3 -m unittest discover -s tests -v
```

Current coverage includes:

- Watchlist CSV parsing
- Market-name normalization
- YouPin sell-listing parsing
- YouPin purchase-order parsing
- API payload construction
- Business indicator scoring
- Recommendation ranking
- SQL analytics
- LLM-ready natural-language routing

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Python version:

```text
Python 3.11+
```

## Configuration

Create a `.env` file from `.env.example`.

Required for CSFloat:

```dotenv
CSFLOAT_API_KEY=your_csfloat_api_key
```

Required for YouPin:

```dotenv
UU_AUTHORIZATION=...
UU_DEVICE_ID=...
UU_DEVICE_UK=...
UU_UK=...
```

Optional:

```dotenv
CNY_USD=0.14
UU_APP_VERSION=5.26.0
UU_SECRET_V=h5_v1
UU_COOKIE=
```

## Design Notes

- Exact cross-market matching uses normalized Steam `market_hash_name`.
- YouPin search is treated as a fuzzy candidate generator, not a trusted exact match.
- YouPin current sell listings are used for `lowest_ask`.
- YouPin current purchase orders are used for `highest_bid`.
- CSFloat sales history is used for 24h volume and average sale price.
- YouPin historical trading volume is not available in the current integration.
- The LLM analyst is deterministic by design and can be safely extended with an external LLM summarizer later.

## Limitations

- This is a research and portfolio project, not financial advice or a production trading system.
- Marketplace APIs can change without notice.
- YouPin authentication headers are required for live collection.
- Currency conversion currently uses a configured static `CNY_USD` rate.
- Generated recommendations should be interpreted as analytical signals, not guaranteed arbitrage.

## Future Work

- Add a single `app.pipeline` command that runs dataset building, feature engineering, recommendation ranking, and analytics.
- Add optional external LLM summarization using retrieved SQL results.
- Add richer data quality reports and anomaly detection.
- Add historical trend analysis from repeated scans.
- Add dashboard or notebook visualizations.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
