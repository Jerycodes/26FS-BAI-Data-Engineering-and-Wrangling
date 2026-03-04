# Projektkontext für Claude

## Projekt-Übersicht

**Kurs:** 26FS BAI - Data Engineering and Wrangling (FHNW)
**Dozent:** Yannick Suter
**Student:** Jeremy Nathan (+ Teampartner)
**Repository:** git@github.com:Jerycodes/26FS-BAI-Data-Engineering-and-Wrangling.git
**Lokaler Pfad:** /Users/jeremynathan/Documents/GitHub/datawrangling
**Python:** 3.12.6 (in .venv)
**Sprache:** Code-Kommentare und Notebooks auf Deutsch, Code auf Englisch

## Projektthema

Analyse der Korrelation zwischen Forex-Währungskursen und Nachrichtenstimmung (Sentiment-Analyse). Mehrere Datenquellen werden geladen, verglichen, bereinigt und in einer Pipeline zusammengeführt.

**Währungspaare:** EUR/USD, EUR/CHF, GBP/USD
**Zeitraum:** 2024-01-01 bis 2025-12-31

---

## Ordnerstruktur

```
datawrangling/
├── .env                          # API-Keys (NICHT im Git)
├── .env.example                  # Vorlage für Teammitglieder
├── .gitignore
├── requirements.txt
├── README.md
├── LICENSE
├── data/
│   ├── raw/                      # Rohdaten (unverändert)
│   │   ├── forex/
│   │   │   ├── yahoo/            # CSV: EUR_USD, EUR_CHF, GBP_USD
│   │   │   ├── eodhd/            # CSV: EUR_USD, EUR_CHF, GBP_USD
│   │   │   └── metatrader/       # (leer, geplant)
│   │   └── news/
│   │       ├── eodhd/            # CSV + teilweise JSON: News pro Währungspaar
│   │       └── webscraping/      # CSV + JSON: RSS Feeds, Reddit
│   ├── processed/                # Bereinigte/verarbeitete Daten
│   │   ├── forex/
│   │   └── news/
│   └── final/                    # Zusammengefuehrte, analysefertige Daten
├── notebooks/
│   ├── 01_eda_forex_yahoo.ipynb      # Yahoo Finance Forex EDA
│   ├── 02_eda_forex_eodhd.ipynb      # EODHD Forex EDA
│   ├── 03_eda_news_eodhd.ipynb       # EODHD News API EDA (mit Sentiment)
│   └── 04_eda_news_webscraping.ipynb # Web Scraping (RSS, Reddit, Investing.com)
├── src/
│   ├── __init__.py
│   ├── data_loading/
│   │   ├── __init__.py
│   │   ├── yahoo_loader.py           # Yahoo Finance Forex Loader
│   │   ├── eodhd_loader.py           # EODHD Forex Loader
│   │   ├── eodhd_news_loader.py      # EODHD News Loader
│   │   └── webscraping_loader.py     # RSS + Reddit Loader
│   ├── data_cleaning/
│   │   └── __init__.py
│   ├── data_transformation/
│   │   └── __init__.py
│   └── pipeline/
│       └── __init__.py
├── reports/
└── docs/
```

---

## Datenquellen - Status

### 1. Yahoo Finance (Forex) - ERLEDIGT
- **Notebook:** 01_eda_forex_yahoo.ipynb
- **Loader:** src/data_loading/yahoo_loader.py
- **API:** yfinance Library (kein Key nötig)
- **Ticker:** EURUSD=X, EURCHF=X, GBPUSD=X
- **Rohdaten:** data/raw/forex/yahoo/*.csv

### 2. EODHD API (Forex) - ERLEDIGT
- **Notebook:** 02_eda_forex_eodhd.ipynb
- **Loader:** src/data_loading/eodhd_loader.py
- **API:** https://eodhd.com/api/eod/{SYMBOL}.FOREX
- **Authentifizierung:** API-Key in .env (EODHD_API_KEY)
- **Ticker:** EURUSD.FOREX, EURCHF.FOREX, GBPUSD.FOREX
- **Rohdaten:** data/raw/forex/eodhd/*.csv

### 3. EODHD News API - ERLEDIGT
- **Notebook:** 03_eda_news_eodhd.ipynb
- **Loader:** src/data_loading/eodhd_news_loader.py
- **API:** https://eodhd.com/api/news?s=EURUSD.FOREX&fmt=json
- **Kosten:** 5 API-Calls pro Request (Free Plan = 20/Tag)
- **Datenfelder:** date, title, content, link, symbols, tags, sentiment (polarity, neg, neu, pos)
- **Besonderheit:** Einige Artikel haben kein Sentiment (NaN) - bewusst so beibehalten
- **Rohdaten:** data/raw/news/eodhd/*.csv (und teilweise .json)

### 4. Web Scraping (RSS + Reddit + Investing.com) - ERLEDIGT
- **Notebook:** 04_eda_news_webscraping.ipynb
- **Loader:** src/data_loading/webscraping_loader.py
- **Quellen:**
  - RSS Feeds: ForexLive, DailyFX, FXStreet, Yahoo Finance, Google News Forex
  - Reddit: r/Forex, r/investing, r/economics (JSON API)
  - Investing.com: HTTP 403 (Anti-Scraping) - dokumentiert
- **SSL-Fix:** feedparser hat SSL-Probleme -> Workaround: requests laden, dann feedparser parsen
- **Limitation:** RSS/Reddit liefern nur aktuelle Daten, keine historischen von 2024-2025
- **Rohdaten:** data/raw/news/webscraping/*.csv und .json

---

## OFFENE AUFGABE: Refactoring Raw -> Processed Workflow

### Problem
Aktuell werden die News-Daten von der API geladen, sofort in pandas verarbeitet (Sentiment extrahiert, Spalten umgewandelt) und dann als CSV gespeichert. Die originalen API-Rohdaten (JSON) gehen dabei teilweise verloren.

### Gewünschter Workflow
```
API/Scrape -> Raw JSON speichern -> Raw JSON laden -> Verarbeiten -> Processed CSV speichern
```

### Was geändert werden muss

#### Notebook 03 (EODHD News):
1. **Abschnitt 3 (Laden):** Aufteilen in zwei Zellen:
   - Zelle 1: API aufrufen -> Rohdaten als JSON speichern in data/raw/news/eodhd/
   - Zelle 2: JSON laden -> DataFrame erstellen -> Sentiment extrahieren -> news_data Dict befüllen
2. **Abschnitt 7 (Speichern):** Ändern von Rohdaten speichern zu Verarbeitete Daten speichern -> nach data/processed/news/

#### Notebook 04 (Web Scraping):
1. Gleiches Prinzip: Erst Raw JSON speichern, dann von JSON laden und verarbeiten
2. Verarbeitete Daten nach data/processed/news/

#### Loader aktualisieren:
- src/data_loading/eodhd_news_loader.py: Neue Funktionen save_raw(), load_raw(), process_news(), save_processed()
- src/data_loading/webscraping_loader.py: Gleiche Struktur mit save_raw(), load_raw(), process_scraped(), save_processed()

#### Wichtig bei Sentiment-Extraktion (Notebook 03):
Einige Artikel haben sentiment: None statt einem Dict. Der Code muss das behandeln:
```python
sentiment_df = df['sentiment'].apply(
    lambda x: pd.Series(x) if isinstance(x, dict) else pd.Series(dtype=float)
)
```
NaN-Werte sollen erhalten bleiben (nicht durch leere Dicts ersetzt werden).

#### Neuer Code für Notebook 03 - Zelle 1 (Laden und Raw speichern):
```python
# Nachrichten laden und als Rohdaten (JSON) speichern
RAW_DIR = '../data/raw/news/eodhd'
os.makedirs(RAW_DIR, exist_ok=True)

raw_files = {}

for eodhd_symbol, pair_name in CURRENCY_PAIRS.items():
    print(f'\nLade Nachrichten für {pair_name} ({eodhd_symbol})...')
    
    articles = load_news(eodhd_symbol, START_DATE, END_DATE, api_key)
    
    if articles:
        safe_name = pair_name.replace('/', '_')
        raw_path = os.path.join(RAW_DIR, f'{safe_name}_news_{START_DATE}_to_{END_DATE}.json')
        with open(raw_path, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        
        raw_files[pair_name] = raw_path
        print(f'  Gesamt: {len(articles)} Artikel')
        print(f'  Rohdaten gespeichert: {raw_path}')
    else:
        print(f'  Keine Artikel gefunden.')

print('\nAlle Rohdaten gespeichert!')
```

#### Neuer Code für Notebook 03 - Zelle 2 (Von Raw laden und verarbeiten):
```python
# Rohdaten laden und in DataFrames umwandeln
news_data = {}

for pair_name, raw_path in raw_files.items():
    print(f'\nLade Rohdaten: {raw_path}')
    
    with open(raw_path, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    df = pd.DataFrame(articles)
    df['date'] = pd.to_datetime(df['date'])
    df['date_only'] = df['date'].dt.date
    
    if 'sentiment' in df.columns:
        sentiment_df = df['sentiment'].apply(
            lambda x: pd.Series(x) if isinstance(x, dict) else pd.Series(dtype=float)
        )
        df = pd.concat([df.drop(columns=['sentiment']), sentiment_df], axis=1)
    
    news_data[pair_name] = df
    print(f'  {len(df)} Artikel geladen und verarbeitet')
    
    if 'polarity' in df.columns:
        missing = df['polarity'].isna().sum()
        print(f'  Davon ohne Sentiment: {missing} ({missing/len(df)*100:.1f}%)')

print('\nAlle Daten verarbeitet!')
```

#### Neuer Code für Notebook 03 - Abschnitt 7 (Processed speichern):
```python
# Verarbeitete Daten als CSV speichern
PROCESSED_DIR = '../data/processed/news'
os.makedirs(PROCESSED_DIR, exist_ok=True)

for pair_name, df in news_data.items():
    safe_name = pair_name.replace('/', '_')
    csv_path = os.path.join(PROCESSED_DIR, f'{safe_name}_news_processed.csv')
    df.to_csv(csv_path, index=False)
    print(f'Gespeichert: {csv_path} ({len(df)} Artikel)')

print('\nVerarbeitete Daten gespeichert!')
```

#### Neuer Code für eodhd_news_loader.py:
```python
"""
eodhd_news_loader.py - Finanznachrichten von EODHD News API laden.
Workflow: API -> Raw JSON speichern -> Laden -> Verarbeiten -> Processed CSV
"""

import requests
import pandas as pd
import os
import json
from dotenv import load_dotenv


def load_api_key():
    load_dotenv()
    api_key = os.getenv("EODHD_API_KEY")
    if not api_key or api_key == "dein_api_key_hier":
        raise ValueError("Kein gültiger EODHD_API_KEY in .env gefunden!")
    return api_key


def load_news(ticker, start_date, end_date, api_key, limit=300):
    all_articles = []
    offset = 0
    while True:
        params = {
            "s": ticker, "from": start_date, "to": end_date,
            "limit": limit, "offset": offset,
            "api_token": api_key, "fmt": "json"
        }
        response = requests.get("https://eodhd.com/api/news", params=params)
        if response.status_code != 200:
            print(f"  FEHLER: HTTP {response.status_code}")
            break
        articles = response.json()
        if not articles:
            break
        all_articles.extend(articles)
        print(f"  Offset {offset}: {len(articles)} Artikel")
        if len(articles) < limit:
            break
        offset += limit
    return all_articles


def save_raw(articles, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"  Rohdaten gespeichert: {output_path}")


def load_raw(raw_path):
    with open(raw_path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_news(articles):
    df = pd.DataFrame(articles)
    df["date"] = pd.to_datetime(df["date"])
    df["date_only"] = df["date"].dt.date
    if "sentiment" in df.columns:
        sentiment_df = df["sentiment"].apply(
            lambda x: pd.Series(x) if isinstance(x, dict) else pd.Series(dtype=float)
        )
        df = pd.concat([df.drop(columns=["sentiment"]), sentiment_df], axis=1)
    return df


def save_processed(df, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"  Verarbeitet gespeichert: {output_path}")


if __name__ == "__main__":
    api_key = load_api_key()
    CURRENCY_PAIRS = {
        "EURUSD.FOREX": "EUR_USD",
        "EURCHF.FOREX": "EUR_CHF",
        "GBPUSD.FOREX": "GBP_USD",
    }
    START_DATE = "2024-01-01"
    END_DATE = "2025-12-31"
    RAW_DIR = "data/raw/news/eodhd"
    PROCESSED_DIR = "data/processed/news"

    for ticker, name in CURRENCY_PAIRS.items():
        print(f"\nLade {name} ({ticker})...")
        articles = load_news(ticker, START_DATE, END_DATE, api_key)
        if articles:
            raw_path = os.path.join(RAW_DIR, f"{name}_news_{START_DATE}_to_{END_DATE}.json")
            save_raw(articles, raw_path)
            raw_articles = load_raw(raw_path)
            df = process_news(raw_articles)
            processed_path = os.path.join(PROCESSED_DIR, f"{name}_news_processed.csv")
            save_processed(df, processed_path)
            print(f"  {len(df)} Artikel verarbeitet")
    print("\nFertig!")
```

#### Neuer Code für webscraping_loader.py:
```python
"""
webscraping_loader.py - Nachrichten von RSS Feeds und Reddit laden.
Workflow: Scrape -> Raw JSON speichern -> Laden -> Verarbeiten -> Processed CSV
"""

import requests
from bs4 import BeautifulSoup
import feedparser
import pandas as pd
import os
import json
import time
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}


def scrape_rss_feeds():
    feeds = {
        'ForexLive': 'https://www.forexlive.com/feed',
        'DailyFX': 'https://www.dailyfx.com/feeds/market-news',
        'FXStreet_News': 'https://www.fxstreet.com/rss/news',
        'Yahoo_Finance': 'https://finance.yahoo.com/news/rssindex',
        'Google_News_Forex': 'https://news.google.com/rss/search?q=forex+EUR+USD&hl=en&gl=US&ceid=US:en',
    }
    articles = []
    for name, url in feeds.items():
        print(f"Lade RSS: {name}...")
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code != 200:
                print(f"  HTTP {response.status_code}")
                continue
            feed = feedparser.parse(response.text)
            for entry in feed.entries:
                summary = entry.get('summary', '')
                if summary:
                    summary = BeautifulSoup(summary, 'html.parser').get_text(strip=True)
                articles.append({
                    'source': name, 'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'published': entry.get('published', ''),
                    'summary': summary,
                })
            print(f"  -> {len(feed.entries)} Artikel")
        except Exception as e:
            print(f"  FEHLER: {e}")
        time.sleep(1)
    return articles


def scrape_reddit(subreddit, sort='hot', limit=100):
    print(f"Lade Reddit r/{subreddit}...")
    headers = {'User-Agent': 'DataWrangling-FHNW/1.0'}
    url = f'https://www.reddit.com/r/{subreddit}/{sort}.json'
    try:
        resp = requests.get(url, headers=headers, params={'limit': limit}, timeout=10)
        if resp.status_code != 200:
            print(f"  FEHLER: HTTP {resp.status_code}")
            return []
        posts = []
        for post in resp.json().get('data', {}).get('children', []):
            p = post['data']
            posts.append({
                'source': f'Reddit_r/{subreddit}', 'title': p.get('title', ''),
                'link': f'https://www.reddit.com{p.get("permalink", "")}',
                'published': datetime.fromtimestamp(p.get('created_utc', 0)).isoformat(),
                'summary': p.get('selftext', '')[:500],
                'score': p.get('score', 0),
                'num_comments': p.get('num_comments', 0),
                'upvote_ratio': p.get('upvote_ratio', 0),
            })
        print(f"  -> {len(posts)} Posts")
        return posts
    except Exception as e:
        print(f"  FEHLER: {e}")
        return []


def save_raw(data, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Rohdaten gespeichert: {output_path}")


def load_raw(raw_path):
    with open(raw_path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_scraped(articles):
    df = pd.DataFrame(articles)
    df['date'] = pd.to_datetime(df['published'], errors='coerce', utc=True)
    df['date_only'] = df['date'].dt.date
    return df


def save_processed(df, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Verarbeitet gespeichert: {output_path}")


if __name__ == "__main__":
    today = datetime.now().strftime('%Y-%m-%d')
    RAW_DIR = "data/raw/news/webscraping"
    PROCESSED_DIR = "data/processed/news"
    all_articles = []
    all_articles.extend(scrape_rss_feeds())
    for sub in ['Forex', 'investing', 'economics']:
        all_articles.extend(scrape_reddit(sub))
        time.sleep(2)
    if all_articles:
        raw_path = os.path.join(RAW_DIR, f"all_scraped_news_{today}.json")
        save_raw(all_articles, raw_path)
        raw_data = load_raw(raw_path)
        df = process_scraped(raw_data)
        processed_path = os.path.join(PROCESSED_DIR, f"scraped_news_processed_{today}.csv")
        save_processed(df, processed_path)
        print(f"\n{len(df)} Einträge verarbeitet")
```

---

## NAECHSTE SCHRITTE (nach Refactoring)

| # | Aufgabe | Priorität |
|---|---------|-----------|
| 1 | Refactoring: Raw JSON -> Processed CSV Workflow | Hoch |
| 2 | Vergleichs-Notebook Yahoo vs. EODHD Forex | Hoch |
| 3 | GDELT als historische News-Quelle (optional) | Mittel |
| 4 | Datenbereinigung und Harmonisierung | Hoch |
| 5 | Sentiment-Analyse (VADER / FinBERT) auf News | Mittel |
| 6 | Forex + Sentiment zusammenführen | Mittel |
| 7 | Korrelationsanalyse + Visualisierung | Mittel |
| 8 | Pipeline automatisieren | Mittel |
| 9 | Projektbericht schreiben | Hoch |

---

## Technische Details

### Virtuelle Umgebung
```bash
source .venv/bin/activate
```

### Installierte Pakete (requirements.txt)
yfinance, requests, python-dotenv, pandas, numpy, textblob, matplotlib, seaborn, plotly, jupyter, notebook, beautifulsoup4, feedparser

### API-Key
In .env (nicht im Git):
```
EODHD_API_KEY=<echter_key>
```

### Git Commits bisher
1. Projektstruktur erstellt
2. Yahoo Finance: Notebook EDA, Loader-Skript und Rohdaten
3. EODHD: Notebook EDA, Loader-Skript und Rohdaten
4. News-Daten: Notebook EDA, Loader-Skript und Rohdaten
5. Web Scraping: RSS Feeds, Reddit, JSON-Export

### Bekannte Probleme
- feedparser hat SSL-Zertifikat-Problem -> Fix: erst mit requests laden, dann feedparser.parse(response.text)
- Investing.com blockiert Scraping (HTTP 403) -> dokumentiert als Erkenntnis
- RSS/Reddit liefern nur aktuelle Daten, keine historischen -> EODHD ist die historische Hauptquelle
- EODHD Free Plan: 20 API-Calls/Tag, News-Request = 5 Calls pro Ticker

---

## Wichtige Hinweise für Claude

1. **Keine API-Calls ausführen** ohne Jeremys Bestätigung (Free Plan hat Limits)
2. **Notebooks nicht überschreiben** - Jeremy hat bereits Ergebnisse darin. Änderungen gezielt in einzelnen Zellen vornehmen.
3. **.env Datei nicht anfassen** - enthält echten API-Key
4. **Immer committen** nach Änderungen: git add . && git commit -m "..." && git push
5. **Alte CSV-Rohdaten** in data/raw/news/ müssen nach dem Refactoring aufgeräumt werden (gehören dann nach data/processed/)
6. **Notebook 04 RSS-Feed-Funktion** benötigt den SSL-Fix (requests laden, dann feedparser parsen)
7. **Sentinel für fehlende Sentiments:** NaN-Werte bewusst beibehalten, nicht durch leere Dicts ersetzen
