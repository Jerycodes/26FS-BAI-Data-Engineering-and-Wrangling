"""
webscraping_loader.py - Nachrichten von RSS Feeds, Investing.com und Reddit laden.
"""

import requests
from bs4 import BeautifulSoup
import feedparser
import pandas as pd
import os
import time
from datetime import datetime


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}


def scrape_rss_feeds():
    feeds = {
        'MarketWatch_Forex': 'https://feeds.marketwatch.com/marketwatch/topstories/',
        'Investing_Forex': 'https://www.investing.com/rss/news_14.rss',
        'FXStreet': 'https://www.fxstreet.com/rss',
        'CNBC_Finance': 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664',
    }
    
    articles = []
    for name, url in feeds.items():
        print(f"Lade RSS: {name}...")
        try:
            feed = feedparser.parse(url)
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
            })
        print(f"  -> {len(posts)} Posts")
        return posts
    except Exception as e:
        print(f"  FEHLER: {e}")
        return []


if __name__ == "__main__":
    all_articles = []
    
    all_articles.extend(scrape_rss_feeds())
    
    for sub in ['Forex', 'investing', 'economics']:
        all_articles.extend(scrape_reddit(sub))
        time.sleep(2)
    
    if all_articles:
        df = pd.DataFrame(all_articles)
        df['date'] = pd.to_datetime(df['published'], errors='coerce', utc=True)
        
        output_dir = "data/raw/news/webscraping"
        os.makedirs(output_dir, exist_ok=True)
        today = datetime.now().strftime('%Y-%m-%d')
        path = os.path.join(output_dir, f"all_scraped_news_{today}.csv")
        df.to_csv(path, index=False)
        print(f"\nGespeichert: {path} ({len(df)} Einträge)")
