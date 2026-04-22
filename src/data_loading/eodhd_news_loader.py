"""
eodhd_news_loader.py - Finanznachrichten von EODHD News API laden.

API: https://eodhd.com/api/news?s=EURUSD.FOREX&from=2024-01-01&to=2025-12-31&fmt=json
Hinweis: Jeder Request verbraucht 5 API-Calls.
"""

import requests
import pandas as pd
import json
import os
from dotenv import load_dotenv


def load_api_key():
    load_dotenv()
    api_key = os.getenv("EODHD_API_KEY")
    if not api_key or api_key == "dein_api_key_hier":
        raise ValueError("Kein gültiger EODHD_API_KEY in .env gefunden!")
    return api_key


def load_news(ticker, start_date, end_date, api_key, limit=1000):
    all_articles = []
    offset = 0
    
    while True:
        params = {
            "s": ticker,
            "from": start_date,
            "to": end_date,
            "limit": limit,
            "offset": offset,
            "api_token": api_key,
            "fmt": "json"
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


if __name__ == "__main__":
    api_key = load_api_key()
    
    CURRENCY_PAIRS = {
        "EURUSD.FOREX": "EUR_USD",
        "EURCHF.FOREX": "EUR_CHF",
        "GBPUSD.FOREX": "GBP_USD",
    }
    
    START_DATE = "2022-01-01"
    END_DATE = "2026-04-22"
    OUTPUT_DIR = "data/raw/news/eodhd"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for ticker, name in CURRENCY_PAIRS.items():
        print(f"\nLade {name} ({ticker})...")
        articles = load_news(ticker, START_DATE, END_DATE, api_key)
        
        if articles:
            # Rohdaten als JSON speichern
            json_filename = f"{name}_news_{START_DATE}_to_{END_DATE}.json"
            json_path = os.path.join(OUTPUT_DIR, json_filename)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
            print(f"  JSON gespeichert: {len(articles)} Artikel -> {json_filename}")

            # Verarbeitete Daten als CSV speichern
            df = pd.DataFrame(articles)
            df["date"] = pd.to_datetime(df["date"])

            if "sentiment" in df.columns:
                sentiment_df = pd.json_normalize(df["sentiment"])
                df = pd.concat([df.drop(columns=["sentiment"]), sentiment_df], axis=1)

            # Zeilenumbrüche in Textfeldern entfernen (CSV-Lesbarkeit)
            for col in ["title", "content"]:
                if col in df.columns:
                    df[col] = df[col].str.replace(r"\s+", " ", regex=True).str.strip()

            csv_filename = f"{name}_news_{START_DATE}_to_{END_DATE}.csv"
            df.to_csv(os.path.join(OUTPUT_DIR, csv_filename), index=False)
            print(f"  CSV gespeichert: {len(df)} Artikel -> {csv_filename}")
    
    print("\nFertig!")
