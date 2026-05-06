"""
generate_lead_lag_notebook.py
==============================

Erzeugt das Notebook
``notebooks/datenverarbeitung/sentiment_kurs_lead_lag_analyse.ipynb``,
das die zentrale Projektfrage beantwortet:

    "Hat das Sentiment von Finanznachrichten einen Einfluss auf
     Wechselkurse — und wenn ja, wie stark und mit welcher zeitlichen
     Verzögerung?"

Das Skript ist deterministisch: bei jedem Aufruf wird das Notebook
identisch neu aufgebaut. Manuelle Anpassungen am Notebook gehen also
verloren, sobald dieses Skript erneut ausgeführt wird.

Aufruf vom Projekt-Root:
    python scripts/generate_lead_lag_notebook.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

OUTPUT = Path("notebooks") / "datenverarbeitung" / "sentiment_kurs_lead_lag_analyse.ipynb"


# ---------------------------------------------------------------------------
# Helfer: Cells als kurze Funktionen, damit der Notebook-Aufbau lesbar bleibt.
# ---------------------------------------------------------------------------

def md(text: str):
    """Markdown-Cell aus einem mehrzeiligen String."""
    return new_markdown_cell(text.strip("\n"))


def code(src: str):
    """Code-Cell aus einem mehrzeiligen String."""
    return new_code_cell(src.strip("\n"))


# ---------------------------------------------------------------------------
# Inhalt
# ---------------------------------------------------------------------------

cells = []

# Titel + Hypothese -----------------------------------------------------------
cells.append(md(r"""
# Sentiment ↔ Wechselkurs — Lead/Lag-Analyse

**Modul:** Data Engineering & Wrangling, BAI, FHNW (FS 2026)
**Notebook-Zweck:** Beantwortung der zentralen Projekt-Hypothese.

## Hypothese

> *Hat das Sentiment von Finanznachrichten einen Einfluss auf Währungskurse —
> und wenn ja, wie viel?*

Methodisch übersetzt:

- **Sentiment am Tag $t$** soll **Kursveränderungen am Tag $t+k$** vorhersagen können (Lead-Effekt, $k > 0$).
- Falls die Korrelation hauptsächlich bei $k \approx 0$ auftritt, ist Sentiment **gleichzeitige** Begleitinformation — kein Lead-Effekt.
- Falls die Korrelation bei $k < 0$ am stärksten ist, **bewegt sich der Kurs zuerst** und die Nachrichten reagieren — die Kausalrichtung wäre umgekehrt.

Wir testen die Hypothese parallel auf zwei Datenpfaden, die das Projekt sauber trennt:

1. **Sauberer Weg** — EODHD-News mit von EODHD vorberechneter Polarity, kombiniert mit Yahoo+EODHD-Forex.
2. **Dirty Weg / PoC** — Webscraping-News (RSS + Reddit) mit eigener TextBlob-Sentiment-Analyse, ebenfalls kombiniert mit Yahoo+EODHD-Forex.

Der Vergleich beider Wege ist Teil der Aussage: stimmen die Resultate überein, oder verdeckt der "saubere" Datensatz Unterschiede, die die selbstgebaute Pipeline aufdeckt — oder umgekehrt?

## Methodischer Hinweis (Quelle: Claude)

Cross-Korrelation für Lead/Lag-Analyse von Zeitreihen ist **kein Inhalt der FHNW-Vorlesung W1–W8**. Die Methodik orientiert sich an der Standard-Statistik-Literatur:

- **Pearson-Korrelation** zwischen $x_t$ und $y_{t+k}$ für $k \in [-10, +10]$ Handelstage.
- Vorzeichenkonvention: $k > 0$ heisst "$x$ führt $y$ um $k$ Tage".
- Konfidenzband (kein Signifikanztest): unter $H_0\!: \rho = 0$ ist $\hat\rho \approx \mathcal{N}(0, 1/N)$, also $\pm 1{.}96/\sqrt{N}$ für $\alpha = 5\%$.
- **Returns** statt Preis-Levels: Forex-Levels haben Trends (nicht-stationär); Korrelation auf Levels ist statistisch verzerrt. Log-Returns $r_t = \ln(P_t / P_{t-1})$ sind annähernd stationär und symmetrisch.

Dass Lead/Lag in den Kursvorlesungen nicht behandelt wurde, dokumentieren wir als Limitation.
"""))

# Setup ----------------------------------------------------------------------
cells.append(md("## 1. Setup"))

cells.append(code(r"""
import os
import glob
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=FutureWarning)

# Projekt-Root finden (Notebook liegt zwei Ebenen tief)
ROOT = Path.cwd()
while not (ROOT / "data").exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent
DATA_DIR = ROOT / "data"
print("Projekt-Root:", ROOT)
print("Datenordner :", DATA_DIR)
"""))

cells.append(code(r"""
# Plot-Konfiguration: gemäss Slide W8 (Datenvisualisierung) verwenden wir
# - keine abgeschnittenen Achsen
# - Viridis statt Jet bei sequenziellen Skalen
# - divergierende Farbskalen für Sentiment um 0
# - 2D statt 3D
plt.style.use("seaborn-v0_8")
plt.rcParams.update({
    "figure.figsize": (11, 4.5),
    "figure.dpi": 110,
    "axes.grid": True,
    "grid.alpha": 0.3,
})

PAIR_LABELS = {"EUR_USD": "EUR/USD", "EUR_CHF": "EUR/CHF", "GBP_USD": "GBP/USD"}
PAIRS = list(PAIR_LABELS.keys())
"""))

# Daten laden ---------------------------------------------------------------
cells.append(md(r"""
## 2. Daten laden

### 2.1 Forex — Outer-Join aller Quellen

Die Forex-Daten kommen aus `data/processed/forex/forex_alle_quellen_kombiniert.csv`.
Diese Datei wird vom Skript `scripts/regenerate_forex_combined.py` erzeugt und enthält
die Quellen Yahoo, EODHD und (nur für EUR/USD) MetaTrader 5 in **Long-Format**:
eine Zeile pro `(date, pair)`-Kombination, eine Spalte `<source>_close` pro Quelle.

**Designentscheidung — kein Mittelwert/Interpolation in der Roh-Datei:** Wir bilden
den Mittelwert *nicht* schon im CSV, sondern erst hier im Notebook. Das hat zwei
Gründe (Quelle: Claude):

1. **Transparenz** — die Quelldaten bleiben pro Anbieter sichtbar, Differenzen sind
   später noch nachprüfbar.
2. **Methodik-Vergleich** — wir können den Mittelwert mit oder ohne Interpolation
   bilden und den Effekt im selben Notebook gegenüberstellen (siehe Sektion 4).
"""))

cells.append(code(r"""
forex_path = DATA_DIR / "processed" / "forex" / "forex_alle_quellen_kombiniert.csv"
forex_long = pd.read_csv(forex_path, parse_dates=["date"]).set_index("date")
forex_long.index = forex_long.index.normalize()
print("Forex Long-Format:", forex_long.shape)
forex_long.head()
"""))

cells.append(code(r"""
# Mittelwert über die verfügbaren close-Quellen pro (date, pair).
# `mean(axis=1, skipna=True)` ignoriert NaN — d.h. wenn an einem Tag nur Yahoo
# verfügbar ist, ist der Mittelwert = Yahoo. Das ist genau der Default des
# Master-Grafik-Dashboards bei Auswahl "mittelwert" als Forex-Quelle.

CLOSE_COLS = ["yahoo_close", "eodhd_close", "metatrader_close"]
forex_long["close_mean"] = forex_long[CLOSE_COLS].mean(axis=1, skipna=True)

forex_close = (
    forex_long
    .reset_index()
    .pivot(index="date", columns="pair", values="close_mean")
    .sort_index()
)
print("Forex-close (Mittelwert) Wide-Format:", forex_close.shape)
forex_close.tail()
"""))

# Sentiment-Loader -----------------------------------------------------------
cells.append(md(r"""
### 2.2 Sentiment — Sauberer Weg (EODHD Polarity)

EODHD liefert pro Artikel ein Feld `polarity` ∈ [-1, 1].
Wir filtern defensiv pro Paar nach dem kanonischen FX-Symbol (gleiche Logik wie
in `dashboard.py:load_news_eodhd`) und aggregieren auf Tagesebene mit dem **Median**.

**Begründung Median (statt Mittelwert):** [Folien Woche 3, S. 19] — der RobustScaler
verwendet Median und IQR statt Mittelwert/Std, weil Median **robuster gegen
Ausreisser** ist. Bei einzelnen sehr stark formulierten News-Artikeln verzerrt
ein Mittelwert das Tagesbild stärker als ein Median.

**Begründung kein Auffüllen fehlender Tage:** [Folien Woche 2, S. 11] —
Tage ohne Artikel sind nicht *zufällig* fehlend (MCAR), sondern hängen davon ab,
ob etwas zum Berichten passierte. Wir halten Sentiment-NaN bewusst als NaN: ein
fehlender Tag ist *kein* "neutraler Tag mit Sentiment 0".
"""))

cells.append(code(r"""
import ast


def _parse_list(val):
    if isinstance(val, list):
        return val
    if not isinstance(val, str) or not val.strip():
        return []
    try:
        return ast.literal_eval(val)
    except (ValueError, SyntaxError):
        return []


PAIR_SYMBOL = {
    "EUR_USD": "EURUSD.FOREX",
    "EUR_CHF": "EURCHF.FOREX",
    "GBP_USD": "GBPUSD.FOREX",
}

def load_eodhd_sentiment_daily(pair: str) -> pd.Series:
    # Tagesmedian der EODHD-Polarity, gefiltert nach kanonischem FX-Symbol.
    pattern = str(DATA_DIR / "raw" / "news" / "eodhd" / f"{pair}_news_*.csv")
    files = sorted(glob.glob(pattern))
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


sentiment_eodhd = pd.concat(
    [load_eodhd_sentiment_daily(p) for p in PAIRS], axis=1
).sort_index()
print("EODHD-Sentiment (Tagesmedian) shape:", sentiment_eodhd.shape)
print("Coverage (Anteil Tage mit Sentiment):")
print((sentiment_eodhd.notna().mean() * 100).round(1).astype(str) + " %")
sentiment_eodhd.tail()
"""))

cells.append(md(r"""
### 2.3 Sentiment — Dirty Weg (Webscraping + TextBlob)

Quelle: `data/processed/news/webscraping_sentiment_daily.csv`, erzeugt vom
PoC-Skript `scripts/regenerate_webscraping_sentiment.py`. Die Datei ist
**nicht paar-spezifisch** — sie aggregiert alle gescrapten Forex-Nachrichten
(RSS + Reddit) zu einem globalen Tages-Median. Wir verwenden denselben Wert
für alle drei Paare (Limitation, siehe Schluss-Diskussion).
"""))

cells.append(code(r"""
ws_path = DATA_DIR / "processed" / "news" / "webscraping_sentiment_daily.csv"
sentiment_webscraping = pd.read_csv(
    ws_path, parse_dates=["date"], index_col="date"
)["polarity_median"].sort_index()
sentiment_webscraping.name = "all_pairs"
print("Webscraping-Sentiment shape:", sentiment_webscraping.shape)
print("Datumsbereich:", sentiment_webscraping.index.min().date(), "bis", sentiment_webscraping.index.max().date())
sentiment_webscraping.tail()
"""))

# Returns --------------------------------------------------------------------
cells.append(md(r"""
## 3. Forex-Returns berechnen

Wir verwenden **Log-Returns** $r_t = \ln(P_t) - \ln(P_{t-1})$.

Begründung (Quelle: Claude — in den Slides nicht behandelt):

- **Stationarität:** Levels haben langfristige Trends; eine Korrelation auf Levels misst
  primär Trend-Übereinstimmung, nicht Reaktion auf News.
- **Symmetrie:** ein Anstieg von 1% und ein Abfall von 1% ergeben Log-Returns
  $\pm 0{.}00995$ (fast symmetrisch). Bei Simple Returns ist die Symmetrie verzerrt.
- **Skalenfrei:** ein Log-Return ist additiv über Zeit, sodass $\sum_t r_t$ den
  kumulierten Log-Return ergibt.
"""))

cells.append(code(r"""
returns = np.log(forex_close).diff()
returns.head()
"""))

# Sensitivitätsanalyse -------------------------------------------------------
cells.append(md(r"""
## 4. Sensitivitätsanalyse — mit / ohne Interpolation

Forex hat strukturelle Lücken (Wochenende, Feiertage). Sentiment hat sporadische
Lücken (Tage ohne Artikel). Beim Zusammenführen bleibt nur die Schnittmenge der
Tage übrig — das kann je nach Paar 30–50 % der Tage kosten und damit die
Aussagekraft der Lag-Korrelation reduzieren.

[Folien Woche 2, S. 16] empfehlen für Zeitreihen "Vorherige oder zukünftige Werte
zum Auffüllen". Wir testen das hier explizit:

- **Variante A** — keine Interpolation. Saubere, aber kleinere Stichprobe.
- **Variante B** — Forex linear zeitinterpoliert auf Tagesfrequenz. Sentiment
  bleibt **NaN** (siehe Sektion 2.2: Sentiment-Lücken sind MNAR, dürfen nicht
  aufgefüllt werden).

Die Korrelationen werden für beide Varianten berechnet. Wenn sie sich kaum
unterscheiden, ist die Wahl unkritisch; wenn sie deutlich abweichen, müssen wir
die Limitation diskutieren.
"""))

cells.append(code(r"""
def make_dataset(returns_df: pd.DataFrame, sentiment: pd.Series, *, interpolate: bool) -> pd.DataFrame:
    # Tagesfrequenz-Reindex; optional Forex linear interpolieren; Sentiment unangetastet.
    full_idx = pd.date_range(returns_df.index.min(), returns_df.index.max(), freq="D")
    df = returns_df.reindex(full_idx)
    if interpolate:
        df = df.interpolate(method="time")
    df.index.name = "date"
    s = sentiment.reindex(full_idx)
    s.index.name = "date"
    return df, s

# Sentiment für sauberen Weg ist paar-spezifisch (Wide-Format)
def assemble_clean(pair: str, *, interpolate: bool) -> pd.DataFrame:
    r, s = make_dataset(returns[[pair]], sentiment_eodhd[pair], interpolate=interpolate)
    out = pd.concat([r.rename(columns={pair: "return"}), s.rename("sentiment")], axis=1)
    return out

def assemble_dirty(pair: str, *, interpolate: bool) -> pd.DataFrame:
    r, s = make_dataset(returns[[pair]], sentiment_webscraping, interpolate=interpolate)
    out = pd.concat([r.rename(columns={pair: "return"}), s.rename("sentiment")], axis=1)
    return out
"""))

# Cross-Korrelation ---------------------------------------------------------
cells.append(md(r"""
## 5. Cross-Korrelation: Sentiment führt Return?

### 5.1 Funktion

Wir berechnen für jedes $k \in [-10, +10]$:

$$\hat\rho_k = \mathrm{corr}(\text{sentiment}_t,\ \text{return}_{t+k})$$

Vorzeichen-Konvention:

- **$k > 0$**: Sentiment führt Return — wenn an Tag $t$ negative News kommen,
  fällt der Kurs erst $k$ Tage später. **Das ist die Hypothese.**
- **$k = 0$**: gleichzeitige Bewegung — Sentiment ist Begleit-Information.
- **$k < 0$**: Return führt Sentiment — der Kurs reagiert zuerst, die News
  spiegeln sie nachträglich.
"""))

cells.append(code(r"""
def cross_correlation(sentiment: pd.Series, ret: pd.Series, *, max_lag: int = 10) -> pd.DataFrame:
    # Pearson corr(sentiment_t, return_{t+k}) für k in [-max_lag, +max_lag].
    rows = []
    for k in range(-max_lag, max_lag + 1):
        # sentiment_t vs return_{t+k} == sentiment unverschoben vs. return.shift(-k)
        aligned = pd.concat([sentiment, ret.shift(-k)], axis=1).dropna()
        if len(aligned) >= 5:
            r = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
            rows.append({"lag": k, "corr": r, "n": len(aligned)})
        else:
            rows.append({"lag": k, "corr": np.nan, "n": len(aligned)})
    return pd.DataFrame(rows)


def conf_band(n: int, alpha: float = 0.05) -> float:
    # Approximatives Konfidenzband +/- z_{1-alpha/2}/sqrt(n) unter H0: rho = 0.
    from scipy.stats import norm
    z = norm.ppf(1 - alpha / 2)
    return z / np.sqrt(max(n, 1))
"""))

cells.append(md(r"""
### 5.2 Resultate pro Paar — Sauberer vs. Dirty Weg

Pro Paar erzeugen wir zwei Plots nebeneinander (sauber vs. dirty), jeweils mit
und ohne Interpolation farblich codiert.

**Farbwahl** (Quelle: Folien Woche 8 + Claude): kategoriale Quellen-Unterscheidung
mit Standard-Tableau-Farbpalette (kontrastreich, farbenblindfreundlich); kein
Viridis hier, weil die Reihen kategorial und nicht ordinal sind.
"""))

cells.append(code(r"""
def plot_pair_lead_lag(pair: str, max_lag: int = 10):
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.5), sharey=True)

    for ax, way, assemble in [
        (axes[0], "Sauberer Weg (EODHD)",   assemble_clean),
        (axes[1], "Dirty Weg (Webscraping + TextBlob)", assemble_dirty),
    ]:
        for interp, color, label in [(False, "tab:blue", "ohne Interpolation"),
                                     (True,  "tab:orange", "mit Interpolation")]:
            df = assemble(pair, interpolate=interp).dropna(how="all")
            cc = cross_correlation(df["sentiment"], df["return"], max_lag=max_lag)
            ax.plot(cc["lag"], cc["corr"], marker="o", color=color, label=label)
            # Konfidenzband basierend auf der mittleren Stichprobengröße
            n_med = int(cc["n"].median())
            band = conf_band(n_med)
            ax.axhspan(-band, band, color=color, alpha=0.10)

        ax.axhline(0, color="black", linewidth=0.8)
        ax.axvline(0, color="grey", linestyle=":", linewidth=0.8)
        ax.set_xlabel("Lag k (Tage); k>0 = Sentiment führt Return")
        ax.set_title(f"{PAIR_LABELS[pair]} — {way}")
        ax.legend(loc="best", fontsize=8)

    axes[0].set_ylabel("Pearson-Korrelation")
    fig.suptitle(f"Lead/Lag: Sentiment vs. Forex-Returns — {PAIR_LABELS[pair]}", y=1.02)
    fig.tight_layout()
    plt.show()
"""))

cells.append(code("plot_pair_lead_lag('EUR_USD')"))

cells.append(code("plot_pair_lead_lag('GBP_USD')"))

cells.append(md(r"""
### 5.3 Sonderfall EUR/CHF

EODHD liefert für EUR/CHF nur ~12 Artikel über den gesamten Zeitraum
(siehe `CLAUDE.md`, Sektion "News-Sentiment handling"). Auf dem sauberen Weg
ist die Stichprobe so klein, dass jede Korrelation rein numerisches Rauschen
darstellt — wir zeigen das Resultat trotzdem, *gerade weil* es eine
methodische Limitation des EODHD-Datensatzes für diese Währung dokumentiert.

Auf dem Dirty Weg ist die Coverage besser, aber das globale Webscraping-Sentiment
ist nicht paar-spezifisch und damit nur bedingt aussagekräftig.
"""))

cells.append(code("plot_pair_lead_lag('EUR_CHF')"))

# Granger Stub ---------------------------------------------------------------
cells.append(md(r"""
## 6. Granger-Causality (optional, aktuell deaktiviert)

Der Granger-Test prüft formell, ob die *Vergangenheit* einer Reihe X die
Vorhersage von Y verbessert — über das hinaus, was Ys eigene Vergangenheit
schon leistet. Das wäre ein striktererer Test als die einfache Cross-Korrelation.

Granger benötigt das Paket `statsmodels`, das aktuell **nicht** in
`requirements.txt` steht. Falls ihr den Test nachrüsten wollt:

```
pip install statsmodels
```

Anschliessend die Cell unten ausführen. **Wichtig:** Granger-Causality testet
*lineare Vorhersagbarkeit*, nicht echte Kausalität — d.h. das Ergebnis bleibt
eine statistische Aussage über Zeitreihen-Reihenfolge, kein kausaler Beleg.
"""))

cells.append(code(r"""
# Aktiviere bei Bedarf: pip install statsmodels
try:
    from statsmodels.tsa.stattools import grangercausalitytests
    df = assemble_clean("EUR_USD", interpolate=False).dropna()
    print("Granger: Sentiment Granger-causes Return? (1..5 Lags)")
    res = grangercausalitytests(df[["return", "sentiment"]], maxlag=5, verbose=False)
    for lag, r in res.items():
        p = r[0]["ssr_ftest"][1]
        print(f"  Lag {lag}: p-Wert = {p:.4f}")
except ImportError:
    print("statsmodels nicht installiert — Granger-Test übersprungen.")
"""))

# Aussage / Schluss -------------------------------------------------------
cells.append(md(r"""
## 7. Beantwortung der Hypothese

Die Beantwortung erfolgt qualitativ anhand der Plots aus Sektion 5; eine harte
Zahl ist bei der vorliegenden Stichprobe nicht seriös begründbar. Die typischen
Befunde, die in dieser Datenlage zu erwarten sind (und in den Plots geprüft
werden sollten):

1. **Korrelation auf Lag 0** in der Größenordnung 0.0–0.15 — schwach, am Rand des
   Konfidenzbandes. Das ist konsistent mit einer **gleichzeitigen** statt
   führenden Reaktion.
2. **Asymmetrie zwischen positivem und negativem Lag** liefert den entscheidenden
   Hinweis: ist die Korrelation bei $k > 0$ deutlich höher als bei $k < 0$, hat
   Sentiment einen **Vorlauf**. Liegt das Maximum bei $k < 0$, läuft der Markt
   den News voraus.
3. **Dirty Weg** zeigt in der Regel niedrigere Korrelationen, weil
   (a) das globale Webscraping-Sentiment nicht paar-spezifisch ist und
   (b) der Zeitraum kürzer ist (~Sep 2024 ff.).

Die genaue Aussage — und damit die Antwort auf die Hypothese — ergibt sich aus
dem Output, sobald das Notebook auf den aktuellen Daten gerechnet wurde. Die
Interpretation gehört in die `DOKUMENTATION.md` (Sektion "Analyse-Resultate"),
**nicht** als hartcodierte Aussage hier ins Notebook.

## 8. Limitationen

- **Stichprobengrösse**: pro Paar ~300–500 Tages-Datenpunkte mit gleichzeitig
  Sentiment und Return. Für Lag-Analysen am Rande des Vertretbaren.
- **EUR/CHF EODHD**: ~12 Artikel — nicht aussagekräftig.
- **Webscraping-Sentiment**: nicht paar-spezifisch; nur eine globale Forex-Stimmung.
- **TextBlob auf Finanztexten**: TextBlob ist auf Allgemeinsprache trainiert;
  finanzielle Fachsprache ("hawkish", "dovish", "rate hike") wird teilweise
  falsch klassifiziert. Spezialisierte Modelle (FinBERT, VADER mit
  Finanz-Lexikon) wären eine sinnvolle Erweiterung.
- **Korrelation ≠ Kausalität**: alle Aussagen oben beziehen sich auf
  *zeitliche Vorhersagbarkeit*, nicht auf einen kausalen Mechanismus.
"""))


# ---------------------------------------------------------------------------
# Notebook schreiben
# ---------------------------------------------------------------------------

nb = new_notebook(cells=cells)
nb.metadata.update({
    "kernelspec": {"name": "python3", "display_name": "Python 3"},
    "language_info": {"name": "python"},
})

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    nbformat.write(nb, f)
print(f"Notebook geschrieben: {OUTPUT} ({OUTPUT.stat().st_size / 1024:.1f} KB)")
