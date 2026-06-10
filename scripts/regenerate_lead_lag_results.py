"""Rechnet data/processed/news/lead_lag_results.csv direkt nach (1:1 Logik aus dem
Lead/Lag-Notebook), OHNE Jupyter-Kernel. Nutzt close_mean = Mittel über die an Yahoo
ausgerichteten Quellen (yahoo/eodhd/metatrader).

Hintergrund: `jupyter nbconvert --execute` kann auf diesem Setup im Kernel hängen
bleiben; dieses Skript erzeugt dieselben Zahlen headless und deterministisch.

Aufruf vom Projekt-Root:
    python scripts/regenerate_lead_lag_results.py
"""
import ast
import glob
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path.cwd()
DATA = ROOT / "data"
PAIRS = ["EUR_USD", "EUR_CHF", "GBP_USD"]
PAIR_SYMBOL = {"EUR_USD": "EURUSD.FOREX", "EUR_CHF": "EURCHF.FOREX", "GBP_USD": "GBPUSD.FOREX"}
CLOSE_COLS = ["yahoo_close", "eodhd_close", "metatrader_close"]

# --- Forex: Mittel über Quellen, Wide-Format, Log-Returns -------------------
forex_long = pd.read_csv(DATA / "processed/forex/forex_alle_quellen_kombiniert.csv",
                         parse_dates=["date"]).set_index("date")
forex_long.index = forex_long.index.normalize()
forex_long["close_mean"] = forex_long[CLOSE_COLS].mean(axis=1, skipna=True)
forex_close = forex_long.reset_index().pivot(index="date", columns="pair", values="close_mean").sort_index()
returns = np.log(forex_close).diff()


def _parse_list(val):
    if isinstance(val, list):
        return val
    if not isinstance(val, str) or not val.strip():
        return []
    try:
        return ast.literal_eval(val)
    except (ValueError, SyntaxError):
        return []


def load_eodhd_sentiment_daily(pair):
    files = sorted(glob.glob(str(DATA / "raw/news/eodhd" / f"{pair}_news_*.csv")))
    if not files:
        return pd.Series(dtype=float, name=pair)
    df = pd.read_csv(files[-1])
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df["date_only"] = df["date"].dt.tz_convert(None).dt.normalize()
    df["symbols_list"] = df["symbols"].apply(_parse_list)
    df = df[df["symbols_list"].apply(lambda l: PAIR_SYMBOL[pair] in l)]
    if df.empty or "polarity" not in df.columns:
        return pd.Series(dtype=float, name=pair)
    s = df.dropna(subset=["polarity"]).groupby("date_only")["polarity"].median()
    s.name = pair
    return s


sentiment_eodhd = pd.concat([load_eodhd_sentiment_daily(p) for p in PAIRS], axis=1).sort_index()
sentiment_web = pd.read_csv(DATA / "processed/news/webscraping_sentiment_daily.csv",
                            parse_dates=["date"], index_col="date")["polarity_median"].sort_index()


def make_dataset(returns_df, sentiment, interpolate):
    full_idx = pd.date_range(returns_df.index.min(), returns_df.index.max(), freq="D")
    df = returns_df.reindex(full_idx)
    if interpolate:
        df = df.interpolate(method="time")
    s = sentiment.reindex(full_idx)
    return df, s


def assemble(pair, way, interpolate):
    sent = sentiment_eodhd[pair] if way == "clean" else sentiment_web
    r, s = make_dataset(returns[[pair]], sent, interpolate)
    return pd.concat([r.rename(columns={pair: "return"}), s.rename("sentiment")], axis=1)


def cross_correlation(sentiment, ret, max_lag=10):
    rows = []
    for k in range(-max_lag, max_lag + 1):
        aligned = pd.concat([sentiment, ret.shift(-k)], axis=1).dropna()
        if len(aligned) >= 5:
            rows.append({"lag": k, "corr": aligned.iloc[:, 0].corr(aligned.iloc[:, 1]), "n": len(aligned)})
        else:
            rows.append({"lag": k, "corr": np.nan, "n": len(aligned)})
    return pd.DataFrame(rows)


def conf_band(n, alpha=0.05):
    return norm.ppf(1 - alpha / 2) / np.sqrt(max(n, 1))


rows = []
for pair in PAIRS:
    for way in ["clean", "dirty"]:
        for interp in [False, True]:
            df = assemble(pair, way, interp)
            cc = cross_correlation(df["sentiment"], df["return"])
            if cc["corr"].dropna().empty:
                rows.append({"pair": pair, "way": way, "interpolation": interp, "best_lag": np.nan,
                             "max_abs_corr": np.nan, "corr_at_lag_0": np.nan, "n_median": 0, "band_95": np.nan})
                continue
            best = cc.loc[cc["corr"].abs().idxmax()]
            n_med = int(cc["n"].median())
            rows.append({
                "pair": pair, "way": way, "interpolation": interp,
                "best_lag": int(best["lag"]),
                "max_abs_corr": round(float(best["corr"]), 4),
                "corr_at_lag_0": round(float(cc.loc[cc["lag"] == 0, "corr"].iloc[0]), 4),
                "n_median": n_med,
                "band_95": round(float(conf_band(n_med)), 4),
            })

results = pd.DataFrame(rows).sort_values(["pair", "way", "interpolation"]).reset_index(drop=True)
out = DATA / "processed/news/lead_lag_results.csv"
results.to_csv(out, index=False)
print("Geschrieben:", out)
print(results.to_string(index=False))

# --- Granger-Test (identische Logik wie Lead/Lag-Notebook Sektion 6) --------
# Schreibt die p-Werte reproduzierbar nach granger_results.csv, damit die im
# Bericht (Tabelle 9) und Dashboard zitierten Werte nicht nur hartcodiert sind.
from statsmodels.tsa.stattools import grangercausalitytests

granger_rows = []
for pair in ["EUR_USD", "GBP_USD"]:
    df = assemble(pair, "clean", interpolate=False).dropna()
    for direction, cols in [("sentiment_to_return", ["return", "sentiment"]),
                            ("return_to_sentiment", ["sentiment", "return"])]:
        res = grangercausalitytests(df[cols], maxlag=5, verbose=False)
        for lag, r in res.items():
            granger_rows.append({"pair": pair, "direction": direction, "lag": lag,
                                 "p_value": round(float(r[0]["ssr_ftest"][1]), 4), "n": len(df)})

granger = pd.DataFrame(granger_rows)
gout = DATA / "processed/news/granger_results.csv"
granger.to_csv(gout, index=False)
print("\nGeschrieben:", gout)
print(granger.to_string(index=False))
