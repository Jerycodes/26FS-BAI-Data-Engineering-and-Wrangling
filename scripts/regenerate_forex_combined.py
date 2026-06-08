"""
regenerate_forex_combined.py - Erzeugt data/processed/forex/forex_alle_quellen_kombiniert.csv neu.

Spiegelt die Kernlogik aus notebooks/datenverarbeitung/datenanalyse_forex.ipynb
(Abschnitte 1 + 7) wider: Rohdaten aus Yahoo, EODHD und MetaTrader einlesen,
auf einheitliches Datumsformat bringen und in ein langes kombiniertes CSV exportieren.

Qualitätsprüfung — Datums-Ausrichtung:
    Forex ist ein dezentraler Markt; verschiedene Anbieter quotieren denselben
    Moment minimal unterschiedlich (Venue-/Uhrzeit-Streuung von wenigen Pips).
    Ein Mittelwert über Quellen ist dafür das richtige Werkzeug. ABER: Yahoo
    stempelt Tagesbalken gemischt auf 23:00 bzw. 00:00 UTC (Sommerzeit-Artefakt),
    EODHD labelt den Sonntags-Eröffnungsbalken je nach Paar anders. Dadurch sind
    die Tagesreihen von EODHD bei EUR/USD und GBP/USD gegenüber Yahoo um genau
    einen Kalendertag verschoben (gemessen: Tagesrendite-Korrelation ~0.0 statt
    ~0.9, mittlere Differenz 42-50 statt ~2 Pips). Würde man so mitteln, würden
    zwei verschiedene Markttage gemischt. Deshalb richten wir jede Nicht-Yahoo-
    Quelle VOR dem Mitteln datengetrieben an der Yahoo-Referenz aus (der Versatz,
    der die Rendite-Korrelation maximiert) und mitteln erst danach.

Verwendung (vom Projekt-Root):
    python scripts/regenerate_forex_combined.py
"""

import glob
import os

import numpy as np
import pandas as pd


DATA_DIR = os.path.join("data", "raw", "forex")
PROCESSED_DIR = os.path.join("data", "processed", "forex")
PAIRS = ["EUR_USD", "EUR_CHF", "GBP_USD"]
# Referenzquelle, an der alle anderen Quellen zeitlich ausgerichtet werden.
REFERENCE_SOURCE = "yahoo"
# Maximaler getesteter Versatz (in Kalendertagen) bei der Ausrichtung.
MAX_ALIGN_SHIFT = 2
# Ein Versatz wird nur angewandt, wenn er die Rendite-Korrelation gegenüber
# "kein Versatz" um mindestens diesen Betrag verbessert (Schutz gegen Schein-Shifts).
MIN_CORR_GAIN = 0.15


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


def return_correlation(ref_close: pd.Series, src_close: pd.Series) -> float:
    """Pearson-Korrelation der Tages-Log-Returns zweier Kursreihen (gemeinsame Tage)."""
    ref_ret = np.log(ref_close).diff()
    src_ret = np.log(src_close).diff()
    joined = pd.concat([ref_ret, src_ret], axis=1).dropna()
    if len(joined) < 30:
        return float("nan")
    return float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))


def align_to_reference(ref_df: pd.DataFrame, src_df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Richtet src_df zeitlich an ref_df aus.

    Sucht den Datums-Versatz in [-MAX_ALIGN_SHIFT, +MAX_ALIGN_SHIFT] Kalendertagen,
    der die Tagesrendite-Korrelation der close-Kurse maximiert, und verschiebt den
    Index von src_df entsprechend. "Kein Versatz" (0) wird bevorzugt und nur
    überschrieben, wenn ein anderer Versatz die Korrelation um mindestens
    MIN_CORR_GAIN verbessert. Gibt das (ggf. verschobene) DataFrame zurück und
    protokolliert die Entscheidung.
    """
    corr_at = {}
    for shift in range(-MAX_ALIGN_SHIFT, MAX_ALIGN_SHIFT + 1):
        shifted = src_df["close"].copy()
        shifted.index = shifted.index + pd.Timedelta(days=shift)
        corr_at[shift] = return_correlation(ref_df["close"], shifted)

    base = corr_at.get(0, float("nan"))
    best_shift = max(corr_at, key=lambda s: (corr_at[s] if corr_at[s] == corr_at[s] else -2))
    best_corr = corr_at[best_shift]
    # Versatz 0 bevorzugen, ausser ein anderer Versatz gewinnt deutlich.
    if not (best_shift != 0 and (best_corr - base) >= MIN_CORR_GAIN):
        best_shift, best_corr = 0, base

    if best_shift != 0:
        out = src_df.copy()
        out.index = out.index + pd.Timedelta(days=best_shift)
        out.index.name = "date"
        print(f"    {label:11s}: Versatz {best_shift:+d}d angewandt "
              f"(Rendite-Korr {base:+.2f} -> {best_corr:+.2f})")
        return out
    print(f"    {label:11s}: kein Versatz (Rendite-Korr {base:+.2f})")
    return src_df


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

    print("\nQualitätsprüfung — Datums-Ausrichtung an Yahoo-Referenz ...")
    for pair in PAIRS:
        ref = data[pair][REFERENCE_SOURCE]
        print(f"  {pair}:")
        for source in list(data[pair].keys()):
            if source == REFERENCE_SOURCE:
                continue
            data[pair][source] = align_to_reference(ref, data[pair][source], source)

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
