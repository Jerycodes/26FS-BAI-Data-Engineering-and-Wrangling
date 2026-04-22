"""
oil_loader.py - Ölpreis-Daten (WTI, Brent) von Yahoo Finance laden und als CSV speichern.

Lädt tägliche Ölpreis-Futures (USD/Barrel) und speichert sie als CSV in
`data/raw/oil/yahoo/`. Analog zu `yahoo_loader.py`.

Verwendung:
    python src/data_loading/oil_loader.py
"""

import yfinance as yf
import pandas as pd
import os


def load_oil_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Lädt Ölpreis-Daten von Yahoo Finance (z.B. CL=F = WTI, BZ=F = Brent)."""
    print(f"Lade {symbol} von {start_date} bis {end_date}...")
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date)
    if df.empty:
        print(f"WARNUNG: Keine Daten für {symbol}!")
    else:
        print(f"Erfolgreich {len(df)} Zeilen geladen.")
    return df


def save_to_csv(df: pd.DataFrame, filename: str, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    df.to_csv(filepath)
    print(f"Gespeichert: {filepath}")
    return filepath


if __name__ == "__main__":
    OIL_TICKERS = {
        "CL=F": "WTI_Crude_Oil",
        "BZ=F": "Brent_Crude_Oil",
    }

    START_DATE = "2022-01-01"
    END_DATE = "2026-04-22"
    OUTPUT_DIR = "data/raw/oil/yahoo"

    for yahoo_symbol, name in OIL_TICKERS.items():
        try:
            df = load_oil_data(yahoo_symbol, START_DATE, END_DATE)
            if not df.empty:
                filename = f"{name}_{START_DATE}_to_{END_DATE}.csv"
                save_to_csv(df, filename, OUTPUT_DIR)
                print(f"  Zeitraum: {df.index.min()} bis {df.index.max()}")
                print(f"  Zeilen: {len(df)}\n")
        except Exception as e:
            print(f"FEHLER bei {yahoo_symbol}: {e}\n")

    print("Fertig! Ölpreis-Daten geladen.")
