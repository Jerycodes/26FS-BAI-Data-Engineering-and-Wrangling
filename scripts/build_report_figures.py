"""
build_report_figures.py - Erzeugt die Abbildungen fuer den Bericht (Ordner docs/figures).

Die Grafiken entsprechen den Auswertungen aus den Notebooks
(sentiment_kurs_lead_lag_analyse.ipynb, datenanalyse_forex.ipynb) und werden in
DOKUMENTATION.docx eingebettet. Zusaetzlich gibt das Skript die Zahlen aus, die im
Bericht zitiert werden (u.a. die Niveau-/Vorlauf-Pruefung).

Aufruf vom Projekt-Root:
    python scripts/build_report_figures.py
"""
import ast
import glob
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.style.use("seaborn-v0_8")
plt.rcParams.update({"figure.dpi": 150, "axes.grid": True, "grid.alpha": 0.3,
                     "axes.titlesize": 12, "font.size": 10})

DATA = Path("data")
FIG = Path("docs/figures")
FIG.mkdir(parents=True, exist_ok=True)
PAIR_LABEL = {"EUR_USD": "EUR/USD", "GBP_USD": "GBP/USD", "EUR_CHF": "EUR/CHF"}
SYM = {"EUR_USD": "EURUSD.FOREX", "GBP_USD": "GBPUSD.FOREX", "EUR_CHF": "EURCHF.FOREX"}

# ---- Daten laden -----------------------------------------------------------
fl = pd.read_csv(DATA / "processed/forex/forex_alle_quellen_kombiniert.csv", parse_dates=["date"]).set_index("date")
fl.index = fl.index.normalize()
fl["close_mean"] = fl[["yahoo_close", "eodhd_close", "metatrader_close"]].mean(axis=1)
price = fl.reset_index().pivot(index="date", columns="pair", values="close_mean").sort_index()


def parse_list(v):
    try:
        return ast.literal_eval(v) if isinstance(v, str) else []
    except Exception:
        return []


def eodhd_sent(pair):
    f = sorted(glob.glob(str(DATA / f"raw/news/eodhd/{pair}_news_*.csv")))[-1]
    d = pd.read_csv(f)
    d["dt"] = pd.to_datetime(d["date"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    d = d[d["symbols"].apply(parse_list).apply(lambda l: SYM[pair] in l)]
    return d.dropna(subset=["polarity"]).groupby("dt")["polarity"].median()


def xcorr(sent, ret, max_lag=10):
    out = {}
    for k in range(-max_lag, max_lag + 1):
        a = pd.concat([sent, ret.shift(-k)], axis=1).dropna()
        out[k] = a.iloc[:, 0].corr(a.iloc[:, 1]) if len(a) >= 5 else np.nan
    return pd.Series(out)


# ===========================================================================
# Abbildung 1: Lead/Lag-Kreuzkorrelation (Tagesebene)
# ===========================================================================
fig, ax = plt.subplots(figsize=(8, 4.2))
for pair, color in [("EUR_USD", "#1f77b4"), ("GBP_USD", "#d62728")]:
    ret = np.log(price[pair]).diff()
    cc = xcorr(eodhd_sent(pair), ret)
    ax.plot(cc.index, cc.values, marker="o", ms=4, color=color, label=PAIR_LABEL[pair])
    n = pd.concat([eodhd_sent(pair), ret], axis=1).dropna().shape[0]
    band = 1.96 / np.sqrt(n)
    ax.axhspan(-band, band, color=color, alpha=0.08)
ax.axhline(0, color="black", lw=0.8)
ax.axvline(0, color="grey", ls=":", lw=0.8)
ax.set_xlabel("Verschiebung in Tagen  (positiv = Sentiment laeuft dem Kurs voraus)")
ax.set_ylabel("Korrelation")
ax.set_title("Zusammenhang Sentiment und Kursveraenderung je Verschiebung")
ax.legend()
fig.tight_layout()
fig.savefig(FIG / "fig_leadlag.png")
plt.close(fig)
print("gespeichert: fig_leadlag.png")

# ===========================================================================
# Abbildung 2: Wochen-Ueberlagerung Kursniveau und Sentiment (deine #57-Idee)
# ===========================================================================
for pair in ["EUR_USD", "GBP_USD"]:
    pw = price[pair].resample("W-FRI").last().dropna()
    sw = eodhd_sent(pair).resample("W-FRI").median()
    sw = sw.reindex(pw.index)
    fig, ax1 = plt.subplots(figsize=(9, 4.2))
    ax1.plot(pw.index, pw.values, color="#1f77b4", lw=1.6, label="Kursniveau (Wochenschluss)")
    ax1.set_ylabel("Kursniveau", color="#1f77b4")
    ax1.tick_params(axis="y", labelcolor="#1f77b4")
    ax2 = ax1.twinx()
    ax2.axhline(0, color="grey", ls=":", lw=0.8)
    ax2.bar(sw.index, sw.values, width=5, color=np.where(sw.values >= 0, "#2ca02c", "#d62728"), alpha=0.5)
    ax2.set_ylabel("Wochen-Sentiment (gruen positiv, rot negativ)", color="#555555")
    ax2.grid(False)
    ax1.set_title(f"{PAIR_LABEL[pair]}: Kursniveau und Nachrichten-Sentiment je Woche")
    fig.tight_layout()
    fig.savefig(FIG / f"fig_weekly_{pair}.png")
    plt.close(fig)
    print(f"gespeichert: fig_weekly_{pair}.png")

# ===========================================================================
# Abbildung 3: Niveau-/Vorlauf-Pruefung -- Sentiment Woche t vs. kumulative
# Kursbewegung ueber die naechsten k Wochen (beantwortet #40)
# ===========================================================================
print("\n--- Niveau-/Vorlauf-Pruefung (Wochen): corr(Sentiment_t, kumul. Kursbewegung bis t+k) ---")
fig, ax = plt.subplots(figsize=(8, 4.2))
ks = list(range(0, 5))
width = 0.35
for i, (pair, color) in enumerate([("EUR_USD", "#1f77b4"), ("GBP_USD", "#d62728")]):
    pw = price[pair].resample("W-FRI").last()
    sw = eodhd_sent(pair).resample("W-FRI").median()
    vals = []
    for k in ks:
        if k == 0:
            fut = np.log(pw).diff()                      # Kursbewegung in derselben Woche
        else:
            fut = np.log(pw).shift(-k) - np.log(pw)      # kumulative Bewegung ueber naechste k Wochen
        a = pd.concat([sw, fut], axis=1).dropna()
        r = a.iloc[:, 0].corr(a.iloc[:, 1]) if len(a) >= 5 else np.nan
        vals.append(r)
    print(f"  {pair}: " + ", ".join(f"k={k}:{v:+.3f}" for k, v in zip(ks, vals)))
    ax.bar(np.array(ks) + (i - 0.5) * width, vals, width, color=color, label=PAIR_LABEL[pair])
ax.axhline(0, color="black", lw=0.8)
ax.set_xlabel("Zeithorizont k in Wochen  (k=0: selbe Woche, k>0: kumulative Bewegung bis Woche t+k)")
ax.set_ylabel("Korrelation mit dem Sentiment der Woche t")
ax.set_title("Sagt das Sentiment einer Woche die Kursbewegung der Folgewochen voraus?")
ax.set_xticks(ks)
ax.legend()
fig.tight_layout()
fig.savefig(FIG / "fig_forward_weeks.png")
plt.close(fig)
print("gespeichert: fig_forward_weeks.png")

# ===========================================================================
# Abbildung 4: Quellenvergleich vor/nach der Datums-Ausrichtung
# ===========================================================================
def raw_yahoo(pair):
    f = sorted(glob.glob(str(DATA / f"raw/forex/yahoo/{pair}_*.csv")))[-1]
    d = pd.read_csv(f, index_col=0, parse_dates=True)
    d.index = pd.to_datetime(d.index, utc=True).tz_localize(None).ceil("D")
    return d.rename(columns=str.lower)["close"][~d.index.duplicated(keep="first")]

def raw_eodhd(pair):
    f = sorted(glob.glob(str(DATA / f"raw/forex/eodhd/{pair}_*.csv")))[-1]
    d = pd.read_csv(f, index_col=0, parse_dates=True)
    d.index = pd.to_datetime(d.index).normalize()
    return d["close"]

def rc(a, b):
    j = pd.concat([np.log(a).diff(), np.log(b).diff()], axis=1).dropna()
    return j.iloc[:, 0].corr(j.iloc[:, 1])

pairs = ["EUR_USD", "GBP_USD", "EUR_CHF"]
before, after = [], []
for p in pairs:
    y, e = raw_yahoo(p), raw_eodhd(p)
    before.append(rc(y, e))
    # beste Ausrichtung wie in der Pipeline
    best = max(range(-2, 3), key=lambda s: (rc(y, e.set_axis(e.index + pd.Timedelta(days=s))) if True else -2))
    after.append(rc(y, e.set_axis(e.index + pd.Timedelta(days=best))))
fig, ax = plt.subplots(figsize=(7.5, 4.2))
x = np.arange(len(pairs))
ax.bar(x - 0.2, before, 0.4, label="vor Ausrichtung", color="#d62728")
ax.bar(x + 0.2, after, 0.4, label="nach Ausrichtung", color="#2ca02c")
ax.set_xticks(x)
ax.set_xticklabels([PAIR_LABEL[p] for p in pairs])
ax.set_ylabel("Uebereinstimmung Yahoo und EODHD (Tagesveraenderung)")
ax.set_title("Quellenvergleich vor und nach der Datums-Ausrichtung")
ax.axhline(0, color="black", lw=0.8)
ax.legend()
fig.tight_layout()
fig.savefig(FIG / "fig_source_alignment.png")
plt.close(fig)
print("gespeichert: fig_source_alignment.png")

# ===========================================================================
# Abbildung 7: Sentiment-Vergleich -- eigenes TextBlob vs. EODHD-Polarity
# ===========================================================================
from textblob import TextBlob

rows = []
for pair in ["EUR_USD", "GBP_USD"]:
    f = sorted(glob.glob(str(DATA / f"raw/news/eodhd/{pair}_news_*.csv")))[-1]
    d = pd.read_csv(f)
    d = d[d["symbols"].apply(parse_list).apply(lambda l: SYM[pair] in l)]
    d = d.dropna(subset=["polarity"])
    # zur Laufzeit begrenzen: gleichmaessige Stichprobe von hoechstens 800 Artikeln je Paar
    if len(d) > 800:
        d = d.iloc[:: max(1, len(d) // 800)]
    for _, r in d.iterrows():
        text = (str(r.get("title") or "") + ". " + str(r.get("content") or ""))[:600].strip()
        if not text or text == ".":
            continue
        rows.append((r["polarity"], TextBlob(text).sentiment.polarity))
cmp = pd.DataFrame(rows, columns=["eodhd", "textblob"])
corr_sent = cmp["eodhd"].corr(cmp["textblob"])
print(f"\n--- Sentiment-Vergleich: Korr(EODHD-Polarity, eigenes TextBlob) = {corr_sent:.3f} (n={len(cmp)}) ---")
fig, ax = plt.subplots(figsize=(6.5, 6))
ax.scatter(cmp["eodhd"], cmp["textblob"], s=8, alpha=0.25, color="#1f77b4")
ax.axhline(0, color="grey", lw=0.6); ax.axvline(0, color="grey", lw=0.6)
ax.plot([-1, 1], [-1, 1], color="#d62728", lw=1, ls="--", label="vollstaendige Uebereinstimmung")
ax.set_xlabel("EODHD-Polarity (vorberechnet)")
ax.set_ylabel("Eigenes TextBlob-Sentiment")
ax.set_title(f"Eigenes Sentiment vs. EODHD auf demselben Text (Korrelation {corr_sent:.2f})")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "fig_sentiment_compare.png")
plt.close(fig)
print("gespeichert: fig_sentiment_compare.png")

# ===========================================================================
# Abbildung 8: Oelpreise (WTI und Brent) und Bezug zu den Wechselkursen
# ===========================================================================
def load_oil(name):
    f = sorted(glob.glob(str(DATA / f"raw/oil/yahoo/{name}_*.csv")))[-1]
    d = pd.read_csv(f, index_col=0, parse_dates=True)
    d.index = pd.to_datetime(d.index, utc=True).tz_localize(None).normalize()
    return d["Close"]

wti = load_oil("WTI_Crude_Oil")
brent = load_oil("Brent_Crude_Oil")
fig, ax = plt.subplots(figsize=(9, 4.2))
ax.plot(wti.index, wti.values, color="#1f77b4", lw=1.2, label="WTI")
ax.plot(brent.index, brent.values, color="#ff7f0e", lw=1.2, label="Brent")
ax.set_ylabel("Oelpreis in US-Dollar je Barrel")
ax.set_title("Oelpreise WTI und Brent im Zeitverlauf")
ax.legend()
fig.tight_layout()
fig.savefig(FIG / "fig_oil.png")
plt.close(fig)
print("gespeichert: fig_oil.png")
print("--- Bezug Oel zu Wechselkursen (Korrelation der Tagesveraenderungen) ---")
for pair in ["EUR_USD", "GBP_USD"]:
    pr = price[pair].dropna()
    for oname, oser in [("WTI", wti), ("Brent", brent)]:
        c = pd.concat([np.log(pr).diff(), np.log(oser).diff()], axis=1).dropna()
        print(f"  {pair} vs {oname}: {c.iloc[:,0].corr(c.iloc[:,1]):+.3f}")

# ===========================================================================
# Verifikation Sonntag/Wochenende (#24/#25)
# ===========================================================================
print("\n--- Sonntags-/Wochenend-Abdeckung je Quelle (Anzahl Zeilen je Wochentag, EUR_USD roh) ---")
for src, loader in [("yahoo", raw_yahoo), ("eodhd", raw_eodhd)]:
    s = loader("EUR_USD")
    wd = pd.Series(s.index.weekday).value_counts().sort_index().to_dict()
    print(f"  {src}: {wd}   (5=Sa, 6=So)")
print("Hinweis: Yahoo-Sonntage sind Artefakt der 23:00-Zeitstempel; echte Sonntagswerte liefert EODHD.")
print("\nAlle Abbildungen in docs/figures/ erzeugt.")
