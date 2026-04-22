"""
eodhd_loader.py - Forex-Daten von EODHD API laden und als CSV speichern.

Dieses Skript lädt historische Forex-Kursdaten von der EODHD API
und speichert sie als CSV-Dateien im Ordner data/raw/forex/eodhd/.

API-Dokumentation: https://eodhd.com/financial-apis/api-for-historical-data-and-volumes
API-Format: https://eodhd.com/api/eod/EURUSD.FOREX?from=2024-01-01&to=2025-12-31&period=d&api_token=KEY&fmt=json

Verwendung:
    python src/data_loading/eodhd_loader.py

Abhängigkeiten:
    pip install requests pandas python-dotenv
"""

import requests
import pandas as pd
import os
from dotenv import load_dotenv


def load_api_key() -> str:
    """
    Lädt den EODHD API-Key aus der .env Datei.
    
    Rückgabe:
        str: Der API-Key
    """
    # .env Datei laden (sucht im aktuellen Verzeichnis)
    load_dotenv()
    
    api_key = os.getenv("EODHD_API_KEY")
    
    if not api_key or api_key == "dein_api_key_hier":
        raise ValueError("Kein gültiger EODHD_API_KEY in .env gefunden!")
    
    return api_key


def load_forex_data(pair: str, start_date: str, end_date: str, api_key: str) -> pd.DataFrame:
    """
    Lädt historische Forex-Daten von der EODHD API.
    
    Parameter:
        pair (str): Währungspaar im EODHD-Format, z.B. "EURUSD.FOREX"
        start_date (str): Startdatum im Format "YYYY-MM-DD"
        end_date (str): Enddatum im Format "YYYY-MM-DD"
        api_key (str): EODHD API-Key
    
    Rückgabe:
        pd.DataFrame: DataFrame mit Spalten date, open, high, low, close, adjusted_close, volume
    """
    print(f"Lade {pair} von {start_date} bis {end_date}...")
    
    # API-URL zusammenbauen
    url = f"https://eodhd.com/api/eod/{pair}"
    params = {
        "from": start_date,
        "to": end_date,
        "period": "d",        # Täglich
        "api_token": api_key,
        "fmt": "json"         # JSON-Format
    }
    
    # API-Request ausführen
    response = requests.get(url, params=params)
    
    # Prüfen ob der Request erfolgreich war
    if response.status_code != 200:
        print(f"FEHLER: HTTP Status {response.status_code}")
        print(f"Antwort: {response.text}")
        return pd.DataFrame()
    
    # JSON in DataFrame umwandeln
    data = response.json()
    
    if not data:
        print(f"WARNUNG: Keine Daten für {pair} erhalten!")
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Datum als Index setzen
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    
    print(f"Erfolgreich {len(df)} Zeilen geladen.")
    return df


def save_to_csv(df: pd.DataFrame, filename: str, output_dir: str) -> str:
    """
    Speichert einen DataFrame als CSV-Datei.
    """
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    df.to_csv(filepath)
    print(f"Gespeichert: {filepath}")
    return filepath


# Hauptprogramm
if __name__ == "__main__":
    
    # API-Key laden
    api_key = load_api_key()
    print("API-Key erfolgreich geladen.\n")
    
    # --- Konfiguration ---
    # Währungspaare im EODHD-Format: SYMBOL.FOREX
    CURRENCY_PAIRS = {
        "EURUSD.FOREX": "EUR_USD",
        "EURCHF.FOREX": "EUR_CHF",
        "GBPUSD.FOREX": "GBP_USD",
    }
    
    # Gleicher Zeitraum wie Yahoo Finance für Vergleich
    START_DATE = "2022-01-01"
    END_DATE = "2026-04-22"
    OUTPUT_DIR = "data/raw/forex/eodhd"
    
    # --- Daten laden und speichern ---
    for eodhd_symbol, name in CURRENCY_PAIRS.items():
        try:
            df = load_forex_data(eodhd_symbol, START_DATE, END_DATE, api_key)
            
            if not df.empty:
                filename = f"{name}_{START_DATE}_to_{END_DATE}.csv"
                save_to_csv(df, filename, OUTPUT_DIR)
                print(f"  Zeitraum: {df.index.min()} bis {df.index.max()}")
                print(f"  Zeilen: {len(df)}")
                print(f"  Spalten: {list(df.columns)}")
                print()
                
        except Exception as e:
            print(f"FEHLER bei {eodhd_symbol}: {e}")
            print()
    
    print("Fertig! Alle EODHD-Daten wurden geladen.")
