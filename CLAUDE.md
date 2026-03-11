# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Academic Data Engineering & Wrangling project (FHNW, course 26FS BAI). Analyzes correlation between Forex exchange rates and news sentiment for EUR/USD, EUR/CHF, GBP/USD over 2024-01-01 to 2025-12-31.

## Environment Setup

- Python 3.12.6 with virtual environment in `.venv/`
- Activate: `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Copy `.env.example` to `.env` and add EODHD API key

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

No test framework, linter, or build system is configured.

## Architecture

### Data Flow
```
API/Scrape → Raw data (data/raw/) → [Processing TBD] → Processed (data/processed/) → Final (data/final/)
```

The `data_cleaning/`, `data_transformation/`, and `pipeline/` modules under `src/` are scaffolded but not yet implemented.

### Source Code (`src/data_loading/`)
Each data source has its own loader module with standalone execution via `if __name__ == "__main__"`:
- **yahoo_loader.py** — yfinance, no auth needed
- **eodhd_loader.py** — EODHD Forex API, requires `EODHD_API_KEY` from `.env`
- **eodhd_news_loader.py** — EODHD News API with pagination (offset-based, limit=300). Saves both raw JSON and processed CSV.
- **webscraping_loader.py** — RSS feeds (feedparser) + Reddit JSON endpoint. Currently saves only CSV, no raw JSON preservation.

Loaders are functional (no classes), use module-level constants for configuration (tickers, date ranges, output paths).

### Notebooks (`notebooks/`)
Numbered EDA notebooks (01–04), one per data source. German markdown documentation, English code. Use `seaborn-v0_8` plot style.

### Data Layout (`data/raw/`)
- `forex/yahoo/` and `forex/eodhd/` — CSV files named `{PAIR}_{START}_to_{END}.csv`
- `news/eodhd/` — News CSV + JSON per currency pair
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

## Planned Refactoring (see `CLAUDE_KONTEXT.md` for full details)

The main pending task is separating raw data preservation from processing:
- Current state: `eodhd_news_loader.py` already saves raw JSON + processed CSV; `webscraping_loader.py` only saves CSV
- Target workflow: All loaders should follow `API → Raw JSON → Load JSON → Process → Processed CSV`
- Loaders need `save_raw()`, `load_raw()`, `process_*()`, `save_processed()` functions
- Processed output goes to `data/processed/news/` (not `data/raw/`)
- Notebooks 03 and 04 need matching updates to split loading/saving cells

## Known Issues

- **feedparser SSL**: Must fetch RSS content with `requests` first, then pass to `feedparser.parse()` (direct URL parsing fails due to SSL cert issues). Note: `webscraping_loader.py` currently uses direct `feedparser.parse(url)` — this is the part that needs the SSL fix.
- **Investing.com**: Returns HTTP 403 — scraping blocked, documented as known limitation
- **RSS/Reddit**: Only provide current data, no historical coverage for the study period
- **EODHD News**: Some articles have `None` sentiment (preserved as NaN, not dropped)
