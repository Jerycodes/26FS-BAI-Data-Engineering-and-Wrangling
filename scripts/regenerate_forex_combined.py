"""
regenerate_forex_combined.py - Erzeugt data/processed/forex/forex_alle_quellen_kombiniert.csv neu.

Spiegelt die Kernlogik aus notebooks/datenverarbeitung/datenanalyse_forex.ipynb
(Abschnitte 1 + 7) wider: Rohdaten aus Yahoo, EODHD und MetaTrader einlesen,
auf einheitliches Datumsformat bringen und in ein langes kombiniertes CSV exportieren.

Verwendung (vom Projekt-Root):
    python scripts/regenerate_forex_combined.py
"""

import glob
import os

import pandas as pd


DATA_DIR = os.path.join("data", "raw", "forex")
PROCESSED_DIR = os.path.join("data", "processed", "forex")
PAIRS = ["EUR_USD", "EUR_CHF", "GBP_USD"]


def load_yahoo(pair: str) -> pd.DataFrame:
    pattern = os.path.join(DATA_DIR, "yahoo", f"{pair}_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Keine Yahoo-Datei für {pair} unter {pattern}")
    df = pd.read_csv(files[-1], index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index, utc=True).tz_localize(None).ceil("D")
    df.index.name = "date"
    df = df.rename(columns=str.lower)
    df = df[~df.index.duplicated(keep="first")]
    return df[["open", "high", "low", "close"]].copy()


def load_eodhd(pair: str) -> pd.DataFrame:
    pattern = os.path.join(DATA_DIR, "eodhd", f"{pair}_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Keine EODHD-Datei für {pair} unter {pattern}")
    df = pd.read_csv(files[-1], index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index).normalize()
    df.index.name = "date"
    return df[["open", "high", "low", "close"]].copy()


def load_metatrader_daily() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "metatrader", "EURUSD_Daily_202201030000_202512260000.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"MetaTrader-Daily-Datei fehlt: {path}")
    df = pd.read_csv(path, sep="\t")
    df.columns = [c.strip("<>").lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], format="%Y.%m.%d")
    df = df.set_index("date")
    return df[["open", "high", "low", "close"]].copy()


def main() -> None:
    print("Lade Rohdaten ...")
    data = {}
    for pair in PAIRS:
        data[pair] = {"yahoo": load_yahoo(pair), "eodhd": load_eodhd(pair)}
    data["EUR_USD"]["metatrader"] = load_metatrader_daily()

    for pair in PAIRS:
        for source, df in data[pair].items():
            print(f"  {pair:7s} {source:11s}: {len(df):5d} Zeilen, "
                  f"{df.index.min().date()} bis {df.index.max().date()}")

    print("\nKombiniere Quellen ...")
    all_dfs = []
    for pair in PAIRS:
        sources = data[pair]
        pair_df = pd.DataFrame()
        for source, df in sources.items():
            for col in ["open", "high", "low", "close"]:
                pair_df[f"{source}_{col}"] = df[col]

        pair_df = pair_df.sort_index()
        pair_df.index.name = "date"
        pair_df["pair"] = pair
        pair_df["weekday"] = pair_df.index.weekday
        pair_df["weekday_name"] = pair_df.index.strftime("%a")
        pair_df["is_weekend"] = pair_df["weekday"] >= 5

        source_names = list(sources.keys())
        close_cols = [f"{s}_close" for s in source_names]
        pair_df["n_sources"] = pair_df[close_cols].notna().sum(axis=1)
        pair_df["has_gap"] = pair_df["n_sources"] < len(source_names)

        all_dfs.append(pair_df)
        gaps = pair_df["has_gap"].sum()
        print(f"  {pair}: {len(pair_df)} Zeilen, {gaps} Tage mit Lücken")

    df_combined = pd.concat(all_dfs).sort_values(["pair", "date"])
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    out = os.path.join(PROCESSED_DIR, "forex_alle_quellen_kombiniert.csv")
    df_combined.to_csv(out)
    size_kb = os.path.getsize(out) / 1024
    print(f"\nGespeichert: {out} ({size_kb:.1f} KB, {len(df_combined)} Zeilen)")


if __name__ == "__main__":
    main()
