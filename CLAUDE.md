# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Academic Data Engineering & Wrangling project (FHNW, course 26FS BAI). Analyzes correlation between Forex exchange rates and news sentiment for EUR/USD, EUR/CHF, GBP/USD over 2024-01-01 to 2025-12-31.

## Environment Setup

- Python 3.12 (pinned via `.python-version`) with virtual environment in `.venv/`
- Activate: `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Key dependencies: `pandas`, `yfinance`, `requests`, `feedparser`, `beautifulsoup4`, `textblob`, `plotly`, `seaborn`, `streamlit>=1.45.0`
- Copy `.env.example` to `.env` and add EODHD API key (also has MetaTrader 5 login fields)
- Streamlit theme config in `.streamlit/config.toml` (dark theme, headless)
- No test framework, linter, or build system is configured

## Running Code

Run data loaders as standalone scripts:
```bash
python src/data_loading/yahoo_loader.py
python src/data_loading/eodhd_loader.py
python src/data_loading/eodhd_news_loader.py
python src/data_loading/webscraping_loader.py
```

Launch notebooks:
```bash
jupyter notebook notebooks/
```

Launch the Streamlit dashboard:
```bash
streamlit run dashboard.py
```

## Architecture

### Data Flow
```
API/Scrape → Raw data (data/raw/) → [Processing TBD] → Processed (data/processed/) → Final (data/final/)
```

### Source Code (`src/data_loading/`)
Each loader is a standalone script (functional style, no classes) with module-level constants for tickers, date ranges, and output paths. All use `if __name__ == "__main__"` entry points.

- **yahoo_loader.py** — yfinance (no auth). Functions: `load_forex_data()`, `save_to_csv()`.
- **eodhd_loader.py** — EODHD Forex API. Functions: `load_api_key()`, `load_forex_data()`, `save_to_csv()`. Requires `EODHD_API_KEY` from `.env`.
- **eodhd_news_loader.py** — EODHD News API with offset-based pagination (`limit=1000` to minimise calls). Functions: `load_api_key()`, `load_news()`. Saves both raw JSON and processed CSV to `data/raw/news/eodhd/`. Uses `pd.json_normalize()` to flatten sentiment dicts.
- **webscraping_loader.py** — RSS feeds (feedparser) + Reddit JSON endpoint. Functions: `scrape_rss_feed()`, `scrape_rss_feeds()`, `scrape_reddit()`. Uses `requests.get()` → `feedparser.parse(response.text)` pattern to avoid SSL issues (validated in `notebooks/04_eda_news_webscraping_fenlin.ipynb`). Saves `rss_feeds_*.csv`, `reddit_forex_*.csv`, combined `all_scraped_news_*.csv` and matching JSON.
- **oil_loader.py** — yfinance (no auth). Loads WTI (`CL=F`) + Brent (`BZ=F`) Daily into `data/raw/oil/yahoo/`. Mirrors `yahoo_loader.py`.

### Helper Scripts (`scripts/`)
Idempotente Reprozessierungs-Scripts, die die Kernlogik relevanter Notebooks 1:1 spiegeln und somit einen Jupyter-Kernel nicht voraussetzen:

- **regenerate_forex_combined.py** — Lädt Yahoo, EODHD und MetaTrader-Daily, produziert `data/processed/forex/forex_alle_quellen_kombiniert.csv` (langformat mit `pair`, `n_sources`, `has_gap`). Spiegelt `datenanalyse_forex.ipynb`.
- **regenerate_webscraping_sentiment.py** — Kombiniert alle `all_scraped_news_*.csv` (ohne `PRE-FIX`), dedupliziert auf `link`, berechnet TextBlob-Polarity auf Titel+Summary, aggregiert auf Tagesmedian. Produziert `data/processed/news/webscraping_articles_sentiment.csv` (Artikel-Level) + `webscraping_sentiment_daily.csv` (Tagesebene). Spiegelt `notebooks/datenverarbeitung/poc_webscraping_sentiment.ipynb` (Sections 1–4 + 7).

### Scaffolded but empty modules
`src/data_cleaning/`, `src/data_transformation/`, `src/pipeline/` — only contain `__init__.py`.

### Notebooks (`notebooks/`)
Organized into subdirectories:
- `notebooks/rohdaten_laden/` — Numbered EDA notebooks (01–05), one per data source (05 = oil/Yahoo)
- `notebooks/datenverarbeitung/` — Data processing/analysis notebooks:
  - `Test_datenanalyse.ipynb` — webscraping news wrangling + MetaTrader EDA + cross-source comparison
  - `datenanalyse_forex.ipynb` — produces `data/processed/forex/forex_alle_quellen_kombiniert.csv` (long-format Yahoo/EODHD/MetaTrader merge with `pair`, `n_sources`, `has_gap`). Used by the dashboard.
  - `datenanalyse_oil.ipynb` — WTI/Brent EDA
  - `news_forex_korrelation.ipynb` — News-vs-Forex correlation, loads raw Yahoo + EODHD per pair
  - `news_forex_korrelation_kombiniert.ipynb` — Same analysis but builds its own combined CSV (`forex_kombiniert_v2.csv`) from raw, then writes a single processed long-format CSV (`forex_verarbeitet_v2.csv`). Includes oil overlay (Schritt 4b) and a sentiment-diagnose section (Schritt 3b)
  - `sentiment_analyse_vergleich.ipynb` — Compares EODHD's pre-computed `polarity` against a TextBlob sentiment computed locally on the article text, per pair. Mirrors the dashboard's `Sentiment-Vergleich` page.
  - `poc_webscraping_sentiment.ipynb` — **Proof of Concept**: Nimmt alle `all_scraped_news_*.csv` (ohne PRE-FIX), dedupliziert auf `link`, berechnet TextBlob-Polarity auf Titel+Summary, aggregiert Tagesmedian, vergleicht mit Yahoo+EODHD-Forex (Überlapp ab Sep 2024). Schreibt die processed-Outputs in `data/processed/news/`. Kernlogik parallel als `scripts/regenerate_webscraping_sentiment.py` verfügbar.

Note: `notebooks/04_eda_news_webscraping_fenlin.ipynb` is an extra variant sitting at the top level of `notebooks/` (not in a subfolder).

German markdown documentation, English code. Use `seaborn-v0_8` plot style.

### Dashboard (`dashboard.py`)
Streamlit app with multiple pages selected from the sidebar (`Übersicht`, `Quellenvergleich`, `Lückenanalyse`, `Preisabweichungen`, `Ölpreise`, `Nachrichten`, `Sentiment-Vergleich`, `Eigene Grafik`, `Master Grafik`, `Master Grafik 2`). The `Sentiment-Vergleich` page runs TextBlob over the EODHD article text and plots it against the pre-computed EODHD `polarity` (cached via `@st.cache_data`). The `Master Grafik` page (="sauberer Weg") lets the user freely combine pairs, sources, oil tickers, and EODHD sentiment with aggregation (D/W/M/Q), aggregation function, optional interpolation, normalization, and a tag filter. Loads `data/processed/forex/forex_alle_quellen_kombiniert.csv`. The `Master Grafik 2` page (="Proof of Concept") mirrors the Master Grafik UI but uses **Webscraping-News + own TextBlob sentiment** instead of EODHD. Forex/Öl are identical (Yahoo + EODHD combined). Sentiment is read from `data/processed/news/webscraping_sentiment_daily.csv` (produced by `scripts/regenerate_webscraping_sentiment.py` or the PoC notebook); the source-filter re-aggregates on-the-fly from `webscraping_articles_sentiment.csv`.

### News-Sentiment handling
- EODHD news per pair is filtered defensively by the canonical FX symbol (`EURUSD.FOREX`, `EURCHF.FOREX`, `GBPUSD.FOREX`) via the `symbols` column — both in the notebook and the dashboard.
- Daily aggregation uses **median** (not mean) of `polarity` in both the notebook (`load_news` in `news_forex_korrelation_kombiniert.ipynb`) and the dashboard's Master Grafik — more robust to outliers.
- Missing days (≈8–10% for EUR_USD/GBP_USD, mostly weekends/holidays) are **kept as NaN** — sentiment is not interpolated. Weekly/monthly resampling handles them automatically.
- **EUR_CHF news coverage from EODHD is essentially absent** (~12 articles total) — sentiment for that pair is not meaningful.

### Data Layout
All raw data lives in `data/raw/` (referenced by notebooks via `../../data/raw/` relative paths). `data/processed/forex/` contains `forex_alle_quellen_kombiniert.csv` (produced by `datenanalyse_forex.ipynb`, **not** by a loader script — must be regenerated when raw data changes) and the `_v2` outputs (`forex_kombiniert_v2.csv`, `forex_verarbeitet_v2.csv`) from `news_forex_korrelation_kombiniert.ipynb`. `data/processed/news/` is scaffolded but currently empty — the planned refactoring target for processed news CSVs. Oil prices live under `data/raw/oil/yahoo/`.

Within `raw/`:
- `forex/yahoo/` and `forex/eodhd/` — CSV files: `{PAIR}_{START}_to_{END}.csv`
- `forex/metatrader/` — MetaTrader 5 exports: tab-separated CSVs with `<DATE>`, `<OPEN>`, etc. headers. Currently EURUSD Daily and M15 (15-minute) data.
- `news/eodhd/` — JSON + CSV per currency pair
- `news/webscraping/` — Scraped RSS + Reddit CSV with date stamp

## Conventions

- **Language**: Code and variable names in English; comments, notebooks, and documentation in German
- **Naming**: Currency pairs use underscore format (`EUR_USD`), files use `{PAIR}_data_{START}_to_{END}.csv`
- **Error messages**: Prefixed with `FEHLER:` (German for "ERROR")
- **API rate limiting**: 1–2 second delays between requests; EODHD Free Plan has 20 calls/day (News = 5 calls per ticker)

## Important Constraints

- **Do not execute API calls** without user confirmation — Free Plan has strict daily limits
- **Do not overwrite notebooks wholesale** — they contain existing results. Make targeted changes to individual cells only.
- **Do not modify `.env`** — contains real API key
- **Sentiment NaN values**: Some EODHD news articles have `sentiment: None`. Preserve these as NaN — do not replace with empty dicts or drop rows.

## Planned Refactoring

See `CLAUDE_KONTEXT.md` for full details and ready-to-use code snippets.

**Goal**: Separate raw data preservation from processing in all loaders.

**Current state**:
- `eodhd_news_loader.py` saves both JSON + CSV but processes inline (no separate `save_raw`/`load_raw`/`process_news`/`save_processed` functions)
- `webscraping_loader.py` only saves CSV — no raw JSON preservation at all
- `webscraping_loader.py` uses direct `feedparser.parse(url)` which has SSL issues — needs fix to fetch with `requests` first

**Target**: All loaders follow `API → Raw JSON → Load JSON → Process → Processed CSV` with explicit `save_raw()`, `load_raw()`, `process_*()`, `save_processed()` functions. Processed output goes to `data/processed/news/` (not `data/raw/`). Notebooks 03 and 04 need matching updates to split loading/saving cells.

## Known Issues

- **feedparser SSL**: Must fetch RSS content with `requests` first, then pass to `feedparser.parse()`. The current `webscraping_loader.py` uses direct URL parsing — this needs fixing.
- **Investing.com**: Returns HTTP 403 — scraping blocked, documented as known limitation
- **RSS/Reddit**: Only provide current data, no historical coverage for the study period
- **EODHD News**: Some articles have `None` sentiment (preserved as NaN, not dropped)
