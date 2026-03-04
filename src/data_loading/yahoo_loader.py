"""
yahoo_loader.py - Forex-Daten von Yahoo Finance laden und als CSV speichern.

Dieses Skript lädt historische Forex-Kursdaten (z.B. EUR/USD, EUR/CHF, GBP/USD)
von Yahoo Finance herunter und speichert sie als CSV-Dateien im Ordner data/raw/forex/yahoo/.

Verwendung:
    python src/data_loading/yahoo_loader.py

Abhängigkeiten:
    pip install yfinance pandas
"""

import yfinance as yf
import pandas as pd
import os
from datetime import datetime


def load_forex_data(pair: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Lädt historische Forex-Daten von Yahoo Finance.
    
    Parameter:
        pair (str): Währungspaar im Yahoo-Format, z.B. "EURUSD=X"
        start_date (str): Startdatum im Format "YYYY-MM-DD"
        end_date (str): Enddatum im Format "YYYY-MM-DD"
    
    Rückgabe:
        pd.DataFrame: DataFrame mit Spalten Open, High, Low, Close, Volume
    """
    print(f"Lade {pair} von {start_date} bis {end_date}...")
    
    # Daten von Yahoo Finance herunterladen
    ticker = yf.Ticker(pair)
    df = ticker.history(start=start_date, end=end_date)
    
    # Prüfen ob Daten geladen wurden
    if df.empty:
        print(f"WARNUNG: Keine Daten für {pair} gefunden!")
        return df
    
    print(f"Erfolgreich {len(df)} Zeilen geladen.")
    return df


def save_to_csv(df: pd.DataFrame, filename: str, output_dir: str) -> str:
    """
    Speichert einen DataFrame als CSV-Datei.
    
    Parameter:
        df (pd.DataFrame): Die zu speichernden Daten
        filename (str): Name der CSV-Datei (ohne Pfad)
        output_dir (str): Zielordner
    
    Rückgabe:
        str: Vollständiger Pfad der gespeicherten Datei
    """
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    df.to_csv(filepath)
    print(f"Gespeichert: {filepath}")
    return filepath


# Hauptprogramm: Wird ausgeführt wenn das Skript direkt gestartet wird
if __name__ == "__main__":
    
    # --- Konfiguration ---
    CURRENCY_PAIRS = {
        "EURUSD=X": "EUR_USD",
        "EURCHF=X": "EUR_CHF",
        "GBPUSD=X": "GBP_USD",
    }
    
    START_DATE = "2024-01-01"
    END_DATE = "2025-12-31"
    OUTPUT_DIR = "data/raw/forex/yahoo"
    
    # --- Daten laden und speichern ---
    for yahoo_symbol, name in CURRENCY_PAIRS.items():
        try:
            df = load_forex_data(yahoo_symbol, START_DATE, END_DATE)
            
            if not df.empty:
                filename = f"{name}_{START_DATE}_to_{END_DATE}.csv"
                save_to_csv(df, filename, OUTPUT_DIR)
                print(f"  Zeitraum: {df.index.min()} bis {df.index.max()}")
                print(f"  Zeilen: {len(df)}")
                print(f"  Spalten: {list(df.columns)}")
                print()
                
        except Exception as e:
            print(f"FEHLER bei {yahoo_symbol}: {e}")
            print()
    
    print("Fertig! Alle Daten wurden geladen.")
