"""
regenerate_webscraping_sentiment.py - PoC-Pipeline fuer Webscraping-News.

Spiegelt die Kernlogik aus notebooks/datenverarbeitung/poc_webscraping_sentiment.ipynb
wider (Abschnitte 1-4 + 7): alle Scrape-Schnappschuesse einlesen, deduplizieren,
TextBlob-Sentiment berechnen, Tagesmedian aggregieren und nach
data/processed/news/ schreiben.

Verwendung (vom Projekt-Root):
    python scripts/regenerate_webscraping_sentiment.py
"""

import glob
import os

import numpy as np
import pandas as pd
from textblob import TextBlob


WEB_DIR = os.path.join("data", "raw", "news", "webscraping")
PROCESSED_NEWS = os.path.join("data", "processed", "news")


def load_all_scrapes() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(WEB_DIR, "all_scraped_news_*.csv")))
    files = [f for f in files if "PRE-FIX" not in f]
    if not files:
        raise FileNotFoundError(f"Keine Scrape-Dateien in {WEB_DIR}")
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df["scrape_file"] = os.path.basename(f)
        dfs.append(df)
        print(f"  {os.path.basename(f):40s} {len(df):5d} Zeilen")
    out = pd.concat(dfs, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce", utc=True)
    out["date_only"] = pd.to_datetime(out["date_only"], errors="coerce")
    return out


def compute_sentiment(row: pd.Series) -> pd.Series:
    title = str(row.get("title") or "")
    summary = str(row.get("summary") or "")
    text = (title + ". " + summary).strip()
    if not text or text == ".":
        return pd.Series({"polarity_tb": np.nan, "subjectivity_tb": np.nan})
    blob = TextBlob(text)
    return pd.Series({
        "polarity_tb": blob.sentiment.polarity,
        "subjectivity_tb": blob.sentiment.subjectivity,
    })


def main() -> None:
    print("Lade alle Webscraping-Schnappschuesse ...")
    df_all = load_all_scrapes()
    print(f"  -> {len(df_all)} Eintraege total (vor Deduplikation)\n")

    print("Deduplikation nach 'link':")
    dupe_link = df_all.duplicated(subset="link").sum()
    dupe_title = df_all.duplicated(subset="title").sum()
    print(f"  Duplikate (link): {dupe_link}")
    print(f"  Duplikate (title): {dupe_title}")
    df_unique = df_all.drop_duplicates(subset="link", keep="first").reset_index(drop=True)
    print(f"  -> {len(df_unique)} unique Artikel\n")

    print("Datenqualitaet:")
    print(f"  Leere Titel:        {(df_unique['title'].fillna('').str.strip() == '').sum()}")
    print(f"  Leere Links:        {(df_unique['link'].fillna('').str.strip() == '').sum()}")
    print(f"  Ungueltiges Datum:  {df_unique['date'].isna().sum()}")
    print(f"  Quellen:            {df_unique['source'].nunique()}")
    print(f"  Zeitraum:           {df_unique['date'].min()} bis {df_unique['date'].max()}\n")

    print("Berechne TextBlob-Sentiment ...")
    sent = df_unique.apply(compute_sentiment, axis=1)
    df_unique = pd.concat([df_unique, sent], axis=1)
    print(f"  Neutrale Artikel (polarity==0): "
          f"{(df_unique['polarity_tb'] == 0).sum()} "
          f"({(df_unique['polarity_tb'] == 0).mean()*100:.1f}%)")
    print(f"  Mittel: {df_unique['polarity_tb'].mean():.4f}, "
          f"Median: {df_unique['polarity_tb'].median():.4f}\n")

    print("Aggregiere auf Tagesbasis (Median der Polarity) ...")
    df_sent = df_unique.dropna(subset=["date", "polarity_tb"]).copy()
    df_sent["date_norm"] = df_sent["date"].dt.tz_convert(None).dt.normalize()
    daily = (
        df_sent.groupby("date_norm")
        .agg(polarity_median=("polarity_tb", "median"),
             polarity_mean=("polarity_tb", "mean"),
             n_articles=("polarity_tb", "size"))
        .sort_index()
    )
    daily.index.name = "date"
    print(f"  {len(daily)} Tage aggregiert, "
          f"{daily.index.min().date()} bis {daily.index.max().date()}\n")

    os.makedirs(PROCESSED_NEWS, exist_ok=True)

    cols_out = ["date", "date_only", "source", "title", "summary", "link",
                 "polarity_tb", "subjectivity_tb", "scrape_file"]
    cols_out = [c for c in cols_out if c in df_unique.columns]
    out_articles = os.path.join(PROCESSED_NEWS, "webscraping_articles_sentiment.csv")
    df_unique[cols_out].to_csv(out_articles, index=False)
    print(f"Gespeichert: {out_articles} ({len(df_unique)} Artikel)")

    out_daily = os.path.join(PROCESSED_NEWS, "webscraping_sentiment_daily.csv")
    daily.to_csv(out_daily)
    print(f"Gespeichert: {out_daily} ({len(daily)} Tage)")


if __name__ == "__main__":
    main()
