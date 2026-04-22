"""
webscraping_loader.py - Nachrichten von RSS Feeds und Reddit laden.

Hinweis zum SSL-Fix: `feedparser.parse(url)` nutzt intern Python's ssl/urllib und
schlaegt auf manchen macOS-Installationen mit `CERTIFICATE_VERIFY_FAILED` fehl
(keine Artikel). Wir holen den Feed daher vorher mit `requests` (nutzt certifi)
und geben den Text an `feedparser.parse()`. Diese Methode wurde in
`notebooks/04_eda_news_webscraping_fenlin.ipynb` validiert.

Investing.com wird nicht mehr versucht (liefert konsistent HTTP 403).
"""

import requests
from bs4 import BeautifulSoup
import feedparser
import pandas as pd
import os
import time
from datetime import datetime


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

RSS_FEEDS = {
    'ForexLive': 'https://www.forexlive.com/feed',
    'DailyFX': 'https://www.dailyfx.com/feeds/market-news',
    'FXStreet_News': 'https://www.fxstreet.com/rss/news',
    'Yahoo_Finance': 'https://finance.yahoo.com/news/rssindex',
    'Google_News_Forex': 'https://news.google.com/rss/search?q=forex+EUR+USD&hl=en&gl=US&ceid=US:en',
}

SUBREDDITS = {
    'Forex': ['hot', 'new'],
    'investing': ['hot'],
    'economics': ['hot'],
}


def scrape_rss_feed(feed_name: str, feed_url: str) -> list[dict]:
    """Lädt einen RSS Feed via requests (SSL-Fix) und parst ihn mit feedparser."""
    print(f"Lade RSS: {feed_name}...")
    try:
        response = requests.get(feed_url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"  WARNUNG: HTTP {response.status_code}")
            return []

        feed = feedparser.parse(response.text)
        articles = []
        for entry in feed.entries:
            summary = entry.get('summary', entry.get('description', ''))
            if summary:
                summary = BeautifulSoup(summary, 'html.parser').get_text(strip=True)
            articles.append({
                'source': feed_name,
                'title': entry.get('title', ''),
                'link': entry.get('link', ''),
                'published': entry.get('published', entry.get('updated', '')),
                'summary': summary,
            })
        print(f"  -> {len(articles)} Artikel")
        return articles
    except Exception as e:
        print(f"  FEHLER: {e}")
        return []


def scrape_rss_feeds() -> list[dict]:
    """Lädt alle konfigurierten RSS Feeds."""
    articles = []
    for name, url in RSS_FEEDS.items():
        articles.extend(scrape_rss_feed(name, url))
        time.sleep(1)
    return articles


def scrape_reddit(subreddit: str, sort: str = 'hot', limit: int = 100) -> list[dict]:
    """Lädt Posts von einem Subreddit via JSON API."""
    print(f"Lade Reddit r/{subreddit} ({sort})...")
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
                'source': f'Reddit_r/{subreddit}',
                'title': p.get('title', ''),
                'link': f'https://www.reddit.com{p.get("permalink", "")}',
                'published': datetime.fromtimestamp(p.get('created_utc', 0)).isoformat(),
                'summary': p.get('selftext', '')[:500],
            })
        print(f"  -> {len(posts)} Posts")
        return posts
    except Exception as e:
        print(f"  FEHLER: {e}")
        return []


def clean_text_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Entfernt Zeilenumbrüche/übermäßige Whitespaces in Textspalten."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = df[col].str.replace(r'\s+', ' ', regex=True).str.strip()
    return df


if __name__ == "__main__":
    rss_articles = scrape_rss_feeds()

    reddit_posts: list[dict] = []
    for subreddit, sorts in SUBREDDITS.items():
        for sort in sorts:
            reddit_posts.extend(scrape_reddit(subreddit, sort=sort))
            time.sleep(2)

    output_dir = "data/raw/news/webscraping"
    os.makedirs(output_dir, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')

    # RSS einzeln speichern (Struktur wie Fenlins Notebook)
    if rss_articles:
        df_rss = pd.DataFrame(rss_articles)
        df_rss['date'] = pd.to_datetime(df_rss['published'], errors='coerce', utc=True)
        df_rss['date_only'] = df_rss['date'].dt.date
        path = os.path.join(output_dir, f"rss_feeds_{today}.csv")
        clean_text_columns(df_rss, ['title', 'summary']).to_csv(path, index=False)
        print(f"\nGespeichert: {path} ({len(df_rss)} Artikel)")
    else:
        df_rss = pd.DataFrame()

    # Reddit einzeln speichern + Duplikate (gleicher Link in hot+new) entfernen
    if reddit_posts:
        df_reddit = pd.DataFrame(reddit_posts)
        df_reddit['date'] = pd.to_datetime(df_reddit['published'], errors='coerce', utc=True)
        df_reddit['date_only'] = df_reddit['date'].dt.date
        before = len(df_reddit)
        df_reddit = df_reddit.drop_duplicates(subset='link')
        path = os.path.join(output_dir, f"reddit_forex_{today}.csv")
        clean_text_columns(df_reddit, ['title', 'summary']).to_csv(path, index=False)
        print(f"Gespeichert: {path} ({len(df_reddit)} Posts, {before - len(df_reddit)} Duplikate entfernt)")
    else:
        df_reddit = pd.DataFrame()

    # Alles zusammen
    common_cols = ['source', 'title', 'link', 'published', 'summary', 'date', 'date_only']
    frames = [df for df in [df_rss, df_reddit] if not df.empty]
    if frames:
        df_all = pd.concat([df[common_cols] for df in frames], ignore_index=True)
        path_csv = os.path.join(output_dir, f"all_scraped_news_{today}.csv")
        clean_text_columns(df_all, ['title', 'summary']).to_csv(path_csv, index=False)
        print(f"\nGesamt gespeichert: {path_csv} ({len(df_all)} Eintraege)")

        path_json = os.path.join(output_dir, f"all_scraped_news_{today}.json")
        df_all.to_json(path_json, orient='records', date_format='iso', force_ascii=False)
        print(f"JSON gespeichert: {path_json}")
    else:
        print("Keine Daten geladen.")
