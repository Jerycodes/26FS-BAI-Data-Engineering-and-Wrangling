# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Academic Data Engineering & Wrangling project (FHNW, course 26FS BAI). Analyzes correlation between Forex exchange rates and news sentiment for EUR/USD, EUR/CHF, GBP/USD over 2022-01-03 to 2026-04-21 (1117 Handelstage je Paar).

## Environment Setup

- Python 3.12 (pinned via `.python-version`) with virtual environment in `.venv/`
- Activate: `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Key dependencies: `pandas`, `yfinance`, `requests`, `feedparser`, `beautifulsoup4`, `textblob`, `plotly`, `seaborn`, `statsmodels` (Granger-Test), `streamlit>=1.45.0`
- Build-Tooling (`python-docx` für `scripts/build_report_docx.py`, `nbformat` für `scripts/generate_lead_lag_notebook.py`) ist seit Juni 2026 in `requirements.txt` enthalten.
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
Idempotente Reprozessierungs- und Build-Scripts, die einen Jupyter-Kernel nicht voraussetzen:

- **regenerate_forex_combined.py** — Lädt Yahoo, EODHD und MetaTrader-Daily, produziert `data/processed/forex/forex_alle_quellen_kombiniert.csv` (langformat mit `pair`, `n_sources`, `has_gap`). **Qualitätsprüfung — Datums-Ausrichtung:** richtet jede Nicht-Yahoo-Quelle datengetrieben an Yahoo aus (Versatz in [-2,+2] Kalendertagen, der die Tagesrendite-Korrelation maximiert; nur angewandt bei Gewinn ≥ `MIN_CORR_GAIN`), BEVOR gemittelt wird. Grund: EODHD (und bei EUR/USD MetaTrader) waren bei EUR/USD & GBP/USD um 1 Tag versetzt (Yahoo 23:00/00:00-UTC-Mix vs. EODHD-Sonntagslabel). Siehe `[[forex_source_misalignment]]` und DOKUMENTATION.docx Kap. 5.5/6.2. **Kanonischer Produzent der CSV** (das ältere `datenanalyse_forex.ipynb` hat den Ausrichtungsschritt nicht). **Achtung:** Der Merge folgt dem Yahoo-Handelskalender (Left-Join auf Yahoo-Index); EODHD-Wochenendwerte bleiben nur in den Rohdaten — so auch im Bericht Kap. 5.2 dokumentiert.
- **regenerate_webscraping_sentiment.py** — Kombiniert alle `all_scraped_news_*.csv` (ohne `PRE-FIX`), dedupliziert auf `link`, berechnet TextBlob-Polarity auf Titel+Summary, aggregiert auf Tagesmedian. Produziert `data/processed/news/webscraping_articles_sentiment.csv` (Artikel-Level) + `webscraping_sentiment_daily.csv` (Tagesebene). Spiegelt `notebooks/datenverarbeitung/poc_webscraping_sentiment.ipynb` (Sections 1–4 + 7).
- **generate_lead_lag_notebook.py** — Baut `notebooks/datenverarbeitung/sentiment_kurs_lead_lag_analyse.ipynb` deterministisch neu auf (jeder Run überschreibt manuelle Änderungen am Notebook). Lags zählen **Kalendertage** (Reindex auf `freq="D"`), nicht Handelstage. Enthält jetzt auch: Wochen-Überlagerung + Folgewochen-Auswertung (Sektion 5.4, speichert `fig_weekly_*`/`fig_forward_weeks` nach `docs/figures/`) und einen aktiven **Granger-Test** (Sektion 6, beide Paare/Richtungen, braucht `statsmodels`). Hinweis: Die `fig_weekly_*` aus `build_report_figures.py` halten die Sentiment-Achse in beiden Panels identisch skaliert (Review-Feedback Juni 2026).
- **regenerate_lead_lag_results.py** — Erzeugt `data/processed/news/lead_lag_results.csv`, `granger_results.csv` (p-Werte beider Richtungen, Quelle der Bericht-Tabelle 9) **und** `stationarity_results.csv` (ADF-Tests auf Kursniveau/Rendite/Sentiment, zitiert in Bericht Kap. 9.4) **headless** (ohne Jupyter-Kernel), 1:1-Logik des Lead/Lag-Notebooks; nutzt `close_mean` über die ausgerichteten Quellen. **Reihenfolge beachten:** erst `regenerate_webscraping_sentiment.py`, dann dieses Script (liest `webscraping_sentiment_daily.csv`). Hintergrund Kernel-Hang: nbclient/nbconvert scheitert im Sandbox-Modus an blockierten ZMQ-Sockets; unsandboxed läuft das Notebook in ~2 Min durch.
- **build_report_figures.py** — Erzeugt 9 Bericht-Abbildungen nach `docs/figures/` (EDA-Renditeverteilung+Boxplot, Lead/Lag-Kurve mit Konfidenzband je Lag — **Kalendertag-Logik identisch zu regenerate_lead_lag_results.py**, Sentiment-Methodenvergleich, Wochen-Überlagerung EUR/GBP mit Zoom-Panel und Neutral-Punkten, Folgewochen, Quellenvergleich mit Wertbeschriftung, Öl, Abdeckungs-Heatmap `fig_coverage`; die 10. Bericht-Abbildung ist das Pipeline-Diagramm aus `docs/architektur/`). Druckt zusätzlich die im Bericht zitierten Zahlen (Ausreisser-Statistik z-Score/IQR, Zeithorizont-Korrelationen Tag/Woche/Monat/Quartal, Niveau-/Folgewochen-Korrelationen, neutrale Wochen) und druckt die im Bericht zitierten Zahlen (u.a. Granger-Eingangsdaten, Niveau-/Folgewochen-Korrelationen). **Farbpalette: farbenblind-sicher (Okabe-Ito: Blau `#0072B2`, Orange `#E69F00`, Vermillion `#D55E00`), kein Rot/Grün** — W8-Vorgabe.
- **build_report_docx.py** — Erzeugt den abgabefertigen `DOKUMENTATION.docx` **direkt** mit `python-docx` (kein Markdown). Enthält den Berichtstext als strukturierten Code + Helfer für farbige Tabellen (Hauptpfad/PoC), Seitenumbrüche, Word-Inhaltsverzeichnis, **Abbildungs-/Tabellenverzeichnis** und Bild-Einbettung. Bettet die Abbildungen aus `docs/figures/` ein (also vorher `build_report_figures.py` laufen lassen). Stil-Vorgaben des Users beachten (siehe Abschnitt „Documentation & Architektur-Artefakte" und Gedächtnis `[[report_style_rules]]`).

### Scaffolded but empty modules
`src/data_cleaning/`, `src/data_transformation/`, `src/pipeline/` — only contain `__init__.py`.

### Notebooks (`notebooks/`)
Organized into subdirectories:
- `notebooks/rohdaten_laden/` — Numbered EDA notebooks (01–05), one per data source (05 = oil/Yahoo)
- `notebooks/datenverarbeitung/` — Data processing/analysis notebooks:
  - `Test_datenanalyse.ipynb` (liegt in `notebooks/_archiv/`) — frühe Sammelfläche, Inhalt in Final-Notebooks aufgeteilt (siehe `notebooks/_archiv/README.md`)
  - `datenanalyse_forex.ipynb` — frühe Version des Yahoo/EODHD/MetaTrader-Merges, **ohne den Datums-Ausrichtungsschritt**. Kanonischer Produzent von `forex_alle_quellen_kombiniert.csv` ist `scripts/regenerate_forex_combined.py` (mit Ausrichtung); das Notebook nicht erneut laufen lassen, sonst überschreibt es die ausgerichtete CSV mit der unkorrigierten Variante.
  - `datenanalyse_oil.ipynb` — WTI/Brent EDA
  - `news_forex_korrelation.ipynb` — News-vs-Forex correlation, loads raw Yahoo + EODHD per pair
  - `news_forex_korrelation_kombiniert.ipynb` — Same analysis but builds its own combined CSV (`forex_kombiniert_v2.csv`) from raw, then writes a single processed long-format CSV (`forex_verarbeitet_v2.csv`). Includes oil overlay (Schritt 4b) and a sentiment-diagnose section (Schritt 3b)
  - `sentiment_analyse_vergleich.ipynb` — Compares EODHD's pre-computed `polarity` against a TextBlob sentiment computed locally on the article text, per pair. Mirrors the dashboard's `Sentiment-Vergleich` page.
  - `poc_webscraping_sentiment.ipynb` — **Proof of Concept**: Nimmt alle `all_scraped_news_*.csv` (ohne PRE-FIX), dedupliziert auf `link`, berechnet TextBlob-Polarity auf Titel+Summary, aggregiert Tagesmedian, vergleicht mit Yahoo+EODHD-Forex (Überlapp ab Sep 2024). Schreibt die processed-Outputs in `data/processed/news/`. Kernlogik parallel als `scripts/regenerate_webscraping_sentiment.py` verfügbar.
  - `sentiment_kurs_lead_lag_analyse.ipynb` — **Zentrales Analyse-Notebook** zur Projektfrage "Hat das Sentiment einen Einfluss auf Wechselkurse, und mit welcher zeitlichen Verzögerung?". Wird deterministisch von `scripts/generate_lead_lag_notebook.py` erzeugt — manuelle Änderungen am Notebook werden beim Re-Generieren überschrieben. Schreibt `data/processed/news/lead_lag_results.csv`.

Auf Top-Level liegen keine Notebooks mehr: `04_eda_news_webscraping.ipynb` (Duplikat), `04_eda_news_webscraping_fenlin.ipynb` (SSL-Fix-Validierung) und `05_merge_und_korrelation.ipynb` (früher Stand) wurden im Juni 2026 nach `notebooks/_archiv/` verschoben (Begründungen in `notebooks/_archiv/README.md`).

German markdown documentation, English code. Use `seaborn-v0_8` plot style.

### Dashboard (`dashboard.py`)
Streamlit app with multiple pages selected from the sidebar (`Übersicht`, `Quellenvergleich`, `Lückenanalyse`, `Preisabweichungen`, `Ölpreise`, `Nachrichten`, `Sentiment-Vergleich`, `Lead/Lag-Analyse`, `Eigene Grafik`, `Master Grafik`, `Master Grafik 2`, `Workflow`). The `Lead/Lag-Analyse` page computes the lead/lag curve on the fly (mirrors `scripts/regenerate_lead_lag_results.py`, cached), shows a per-lag confidence band, the summary table from `lead_lag_results.csv`, and the static Granger p-values from the report. Colors use a shared Okabe-Ito constant (`OKABE_ITO`/`PAIR_COLORS` at the top of `dashboard.py`) — no red/green semantics anywhere. The `Workflow` page renders the project pipeline as an inline Graphviz digraph (`st.graphviz_chart`); `docs/architektur/pipeline.gv` is a report-adapted variant (vertical layout, no green). The `Sentiment-Vergleich` page runs TextBlob over the EODHD article text and plots it against the pre-computed EODHD `polarity` (cached via `@st.cache_data`). The `Master Grafik` page (="sauberer Weg") lets the user freely combine pairs, sources, oil tickers, and EODHD sentiment with aggregation (D/W/M/Q), aggregation function, optional interpolation, normalization, and a tag filter. Loads `data/processed/forex/forex_alle_quellen_kombiniert.csv`. The `Master Grafik 2` page (="Proof of Concept") mirrors the Master Grafik UI but uses **Webscraping-News + own TextBlob sentiment** instead of EODHD. Forex/Öl are identical (Yahoo + EODHD combined). Sentiment is read from `data/processed/news/webscraping_sentiment_daily.csv` (produced by `scripts/regenerate_webscraping_sentiment.py` or the PoC notebook); the source-filter re-aggregates on-the-fly from `webscraping_articles_sentiment.csv`.

### News-Sentiment handling
- EODHD news per pair is filtered defensively by the canonical FX symbol (`EURUSD.FOREX`, `EURCHF.FOREX`, `GBPUSD.FOREX`) via the `symbols` column — both in the notebook and the dashboard.
- Daily aggregation uses **median** (not mean) of `polarity` in both the notebook (`load_news` in `news_forex_korrelation_kombiniert.ipynb`) and the dashboard's Master Grafik — more robust to outliers.
- Missing days (≈8–10% for EUR_USD/GBP_USD, mostly weekends/holidays) are **kept as NaN** — sentiment is not interpolated. Weekly/monthly resampling handles them automatically.
- **EUR_CHF news coverage from EODHD is essentially absent** (~12 articles total) — sentiment for that pair is not meaningful.

### Data Layout
All raw data lives in `data/raw/` (referenced by notebooks via `../../data/raw/` relative paths). `data/processed/forex/` contains `forex_alle_quellen_kombiniert.csv` (produced by `scripts/regenerate_forex_combined.py` — **nicht** von einem Loader-Script und nicht vom älteren `datenanalyse_forex.ipynb` ohne Ausrichtung; muss bei Änderung der Rohdaten regeneriert werden). Die `_v2`-Outputs (`forex_kombiniert_v2.csv`, `forex_verarbeitet_v2.csv`) aus `news_forex_korrelation_kombiniert.ipynb` werden ggf. dort ebenfalls abgelegt. Oil prices live under `data/raw/oil/yahoo/`.

`data/processed/news/` enthält aktuell:
- `webscraping_articles_sentiment.csv` — Artikel-Level TextBlob-Sentiment (deduped) aus PoC.
- `webscraping_sentiment_daily.csv` — Tages-Aggregation (Median) für Dashboard `Master Grafik 2`.
- `lead_lag_results.csv` — Ergebnisse aus dem Lead/Lag-Notebook bzw. `regenerate_lead_lag_results.py`.
- `granger_results.csv` — Granger-p-Werte beider Richtungen (Quelle der Bericht-Tabelle 9), erzeugt von `regenerate_lead_lag_results.py`.
- `stationarity_results.csv` — ADF-Stationaritätstests (Kursniveau nicht stationär, Rendite/Sentiment stationär; Bericht Kap. 9.4), erzeugt von `regenerate_lead_lag_results.py`.

Within `raw/`:
- `forex/yahoo/` and `forex/eodhd/` — CSV files: `{PAIR}_{START}_to_{END}.csv`
- `forex/metatrader/` — MetaTrader 5 exports: tab-separated CSVs with `<DATE>`, `<OPEN>`, etc. headers. Currently EURUSD Daily and M15 (15-minute) data.
- `news/eodhd/` — JSON + CSV per currency pair
- `news/webscraping/` — Scraped RSS + Reddit CSV with date stamp

`data_archive/` spiegelt einen früheren `raw/`+`processed/`-Snapshot (Forex / News / Oil). Nicht überschreiben, sondern als Backup-Referenz behandeln.

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

## Documentation & Architektur-Artefakte

- **`DOKUMENTATION.docx`** — Abgabefertiger Haupt-Bericht. Wird **direkt** mit `python scripts/build_report_docx.py` erzeugt (python-docx, KEIN Markdown-Zwischenschritt). Inhalt liegt als strukturierter Python-Code im Builder; dort editieren, NICHT die .docx direkt. **Build-Reihenfolge:** zuerst `build_report_figures.py` (erzeugt 9 Abbildungen in `docs/figures/`; Pipeline-Diagramm kommt aus `docs/architektur/`), dann `build_report_docx.py`. Aufbau: Titelseite (Namen: Jeremy Nathan, Stirling Mulholland, Fenlin Chirakkal), Inhaltsverzeichnis (Word-TOC-Feld), Abbildungs-/Tabellenverzeichnis, Kap. 1 Einleitung (mit Pipeline-Diagramm + Hauptpfad/PoC), 2 Eingesetzte Werkzeuge, 3 Datengrundlage, 4 Laden (exakte Symbole), 5 Bereinigung/Qualitätsprüfung (5.1 EDA, 5.2 Fehlende Werte, 5.3 Duplikate, 5.4 Ausreisser, 5.5 Datierungsfehler), 6 Harmonisierung, 7 Aufbereitung, 8 Sentiment, 9 Analyse/Ergebnisse (inkl. 9.4 Granger mit Limitations-Absatz, 9.6 mit Auswahleffekt-Hinweis), 10 Diskussion, Anhang A Glossar / B Theorie+Quellen (inkl. Ausreisser-Verfahren, Cheng et al. 2024, Okabe-Ito) / C Reproduzierbarkeit / D Dashboard / E Ergänzende Abbildungen (Öl). 10 Abbildungen + 11 Tabellen, alle beschriftet (Anhang E: Öl, Abdeckungs-Heatmap, Artikel-pro-Tag-Tabelle). Layout: Blocksatz, Ränder 2 cm, Abbildungsbreiten 12.5 bis 17 cm. **Stil-Vorgaben des Users (zwingend):** echte Umlaute (ä/ö/ü, Schweizer „ss" statt „ß"), KEINE En-/Em-Dashes (–/—), KEINE Markdown-`**`, KEINE „usw/etc" bei Fakten (Symbole/Filter exakt nennen), keine Sätze wie „der Dozent/die Vorlesung", Theorie nur im Anhang mit Quelle, Hauptpfad vs. Proof-of-Concept farblich getrennt (blau=genutzt, orange=PoC), Abbildungen farbenblind-sicher (kein Rot/Grün). Word-TOC-Feld aktualisiert sich beim Öffnen (updateFields ist gesetzt; Word fragt einmal nach Bestätigung). Die frühere `DOKUMENTATION.md` + `build_documentation_docx.py` sind entfernt (überholt). Siehe Gedächtnis `[[report_style_rules]]`.
- **`docs/architektur/`** — Pipeline-Diagramm: `pipeline.gv` (Graphviz-Quelle), `pipeline.png`, `pipeline.svg`. PNG ist im Bericht (Kap. 1.4) eingebettet.
- **`docs/figures/`** — Vom `build_report_figures.py` erzeugte Bericht-Abbildungen (`fig_*.png`). Werden in `DOKUMENTATION.docx` eingebettet.
- **`slides/`** — Unterrichtsslides, konsistent benannt `W01_einfuehrung_datenqualitaet.pdf` bis `W09_pipelines_automation.pdf` plus `Semesterplan.pdf` (lokal, gitignored). Referenz bei methodischen Entscheidungen; W02=Bereinigung/Ausreisser, W04=Harmonisierung (Cheng et al. 2024), W08=Visualisierung (Okabe-Ito).
- **`FS26_DWaE_Berwertungskriterien.pdf`** (Repo-Root) — Offizielles Bewertungsraster des Kurses. Bei inhaltlichen Entscheidungen zum Bericht dagegen prüfen (siehe Gedächtnis `[[grading_criteria]]`).

## Planned Refactoring

See `CLAUDE_KONTEXT.md` for full details and ready-to-use code snippets. **Achtung:** `CLAUDE_KONTEXT.md` ist teilweise veraltet (nennt z.B. den Zeitraum 2024-01-01 bis 2025-12-31 statt 2022-01-03 bis 2026-04-21) — bei Widersprüchen gilt diese Datei (CLAUDE.md).

**Goal**: Separate raw data preservation from processing in all loaders.

**Current state**:
- `webscraping_loader.py` nutzt mittlerweile `requests.get()` → `feedparser.parse(response.text)` (SSL-Fix erledigt), schreibt aber weiterhin nur CSV — keine Roh-JSON-Persistenz.
- `eodhd_news_loader.py` saves both JSON + CSV but processes inline (no separate `save_raw`/`load_raw`/`process_news`/`save_processed` functions)

**Target**: All loaders follow `API → Raw JSON → Load JSON → Process → Processed CSV` with explicit `save_raw()`, `load_raw()`, `process_*()`, `save_processed()` functions. Processed output goes to `data/processed/news/` (not `data/raw/`). Notebooks 03 and 04 need matching updates to split loading/saving cells.

## Known Issues

- **Investing.com**: Returns HTTP 403 — scraping blocked, documented as known limitation
- **RSS/Reddit**: Only provide current data, no historical coverage for the study period
- **EODHD News**: Some articles have `None` sentiment (preserved as NaN, not dropped)
- **feedparser SSL** (erledigt): `webscraping_loader.py` holt RSS-Inhalte erst mit `requests` (certifi) und gibt den Text an `feedparser.parse()` — der Fix ist im Modul-Docstring dokumentiert.
