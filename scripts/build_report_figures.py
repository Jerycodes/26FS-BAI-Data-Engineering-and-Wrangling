"""
build_report_figures.py - Erzeugt die Abbildungen für den Bericht (Ordner docs/figures).

Die Grafiken entsprechen den Auswertungen aus den Notebooks
(sentiment_kurs_lead_lag_analyse.ipynb, datenanalyse_forex.ipynb) und werden in
DOKUMENTATION.docx eingebettet. Zusätzlich gibt das Skript die Zahlen aus, die im
Bericht zitiert werden (u.a. die Niveau-/Vorlauf-Prüfung).

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
plt.rcParams.update({"figure.dpi": 150, "savefig.dpi": 200, "axes.grid": True, "grid.alpha": 0.3,
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
    # Kalendertag-Logik wie in regenerate_lead_lag_results.py: Returns und
    # Sentiment auf tägliche Frequenz reindizieren, damit shift(-k)
    # Kalendertage zählt. So zeigt die Abbildung exakt dieselbe Statistik
    # wie lead_lag_results.csv und die Tabellen im Bericht.
    full_idx = pd.date_range(ret.index.min(), ret.index.max(), freq="D")
    ret = ret.reindex(full_idx)
    sent = sent.reindex(full_idx)
    out, ns = {}, {}
    for k in range(-max_lag, max_lag + 1):
        a = pd.concat([sent, ret.shift(-k)], axis=1).dropna()
        out[k] = a.iloc[:, 0].corr(a.iloc[:, 1]) if len(a) >= 5 else np.nan
        ns[k] = len(a)
    return pd.Series(out), pd.Series(ns)


# ===========================================================================
# Abbildung: EDA der Tagesveränderungen -- Verteilung und Ausreisser
# ===========================================================================
print("--- EDA/Ausreisser: Tagesveränderungen (log) je Paar ---")
rets = {p: np.log(price[p]).diff().dropna() * 100 for p in ["EUR_USD", "GBP_USD", "EUR_CHF"]}
for p, r in rets.items():
    z = (r - r.mean()) / r.std()
    q1, q3 = r.quantile(0.25), r.quantile(0.75)
    iqr = q3 - q1
    n_iqr = ((r < q1 - 1.5 * iqr) | (r > q3 + 1.5 * iqr)).sum()
    print(f"  {p}: n={len(r)}, std={r.std():.3f}%, |z|>3: {(z.abs() > 3).sum()}, "
          f"ausserhalb 1.5*IQR: {n_iqr} ({n_iqr/len(r)*100:.1f}%), "
          f"min={r.min():+.2f}% am {r.idxmin():%d.%m.%Y}, max={r.max():+.2f}% am {r.idxmax():%d.%m.%Y}")

fig, (axh, axb) = plt.subplots(1, 2, figsize=(10, 4.2), gridspec_kw={"width_ratios": [3, 2]})
colors = {"EUR_USD": "#0072B2", "GBP_USD": "#E69F00", "EUR_CHF": "#D55E00"}
for p, r in rets.items():
    axh.hist(r, bins=80, density=True, histtype="step", lw=1.5,
             color=colors[p], label=PAIR_LABEL[p])
axh.set_xlabel("Tagesveränderung in Prozent")
axh.set_ylabel("Dichte")
axh.set_title("Verteilung der Tagesveränderungen")
axh.legend()
bp = axb.boxplot([rets[p] for p in rets], tick_labels=[PAIR_LABEL[p] for p in rets],
                 patch_artist=True, flierprops={"marker": ".", "ms": 3, "alpha": 0.5})
for patch, p in zip(bp["boxes"], rets):
    patch.set_facecolor(colors[p]); patch.set_alpha(0.6)
for med in bp["medians"]:
    med.set_color("black")
axb.set_ylabel("Tagesveränderung in Prozent")
axb.set_title("Boxplot mit Extremwerten")
fig.tight_layout()
fig.savefig(FIG / "fig_eda_returns.png")
plt.close(fig)
print("gespeichert: fig_eda_returns.png")


# ===========================================================================
# Abbildung 1: Lead/Lag-Kreuzkorrelation (Tagesebene)
# ===========================================================================
fig, ax = plt.subplots(figsize=(8, 4.2))
for pair, color in [("EUR_USD", "#0072B2"), ("GBP_USD", "#E69F00")]:
    ret = np.log(price[pair]).diff()
    cc, ns = xcorr(eodhd_sent(pair), ret)
    ax.plot(cc.index, cc.values, marker="o", ms=4, color=color, label=PAIR_LABEL[pair])
    band = 1.96 / np.sqrt(ns)  # Konfidenzband mit dem tatsächlichen n je Verschiebung
    ax.fill_between(band.index, -band.values, band.values, color=color, alpha=0.08)
ax.axhline(0, color="black", lw=0.8)
ax.axvline(0, color="grey", ls=":", lw=0.8)
ax.set_xticks(range(-10, 11, 2))  # nur ganzzahlige Verschiebungen, keine Dezimal-Ticks
ax.set_xlabel("Verschiebung in Tagen  (positiv = Sentiment läuft dem Kurs voraus)")
ax.set_ylabel("Korrelation")
ax.set_title("Zusammenhang Sentiment und Kursveränderung je Verschiebung")
ax.legend()
fig.tight_layout()
fig.savefig(FIG / "fig_leadlag.png")
plt.close(fig)
print("gespeichert: fig_leadlag.png")

# ===========================================================================
# Abbildung: Wochen-Überlagerung Kursniveau und Sentiment, oben gesamter
# Zeitraum, unten Zoom auf die letzten 12 Monate (dichteste News-Abdeckung)
# ===========================================================================
def plot_price_sentiment(ax1, pw, sw, bar_width, zoom=False, sent_ylim=None):
    # Kurslinie: Marker zeigen die einzelnen Wochenschluss-Punkte; im Zoom
    # gestrichelt verbunden, damit die Wochen-Aggregation erkennbar ist.
    ax1.plot(pw.index, pw.values, color="#333333", lw=1.1,
             ls="--" if zoom else "-", marker="o", ms=3.5 if zoom else 2,
             label="Kursniveau (Wochenschluss)")
    ax1.set_ylabel("Kursniveau", color="#333333")
    ax1.tick_params(axis="y", labelcolor="#333333")
    ax2 = ax1.twinx()
    ax2.axhline(0, color="grey", ls=":", lw=0.8)
    ax2.bar(sw.index, sw.values, width=bar_width,
            color=np.where(sw.values >= 0, "#0072B2", "#D55E00"), alpha=0.85)
    # Wochen mit Artikeln, aber exakt neutralem Median (0): als graue Punkte
    # auf der Nulllinie markieren -- unterscheidbar von Wochen ohne Artikel.
    neutral = sw[sw == 0]
    ax2.plot(neutral.index, neutral.values, ls="none", marker="o",
             ms=3.5 if zoom else 2.5, color="#777777",
             label="neutrale Woche (Median 0)")
    ax2.set_ylabel("Wochen-Sentiment", color="#555555")
    if sent_ylim is not None:
        ax2.set_ylim(*sent_ylim)  # gleiche Skala in beiden Panels, sonst wirken identische Werte unterschiedlich gross
    ax2.grid(False)
    return ax2


from matplotlib.patches import Patch
from matplotlib.lines import Line2D

WEEKLY_LEGEND = [
    Line2D([], [], color="#333333", lw=1.1, marker="o", ms=3, label="Kursniveau (Wochenschluss)"),
    Patch(facecolor="#0072B2", alpha=0.85, label="Wochen-Sentiment positiv"),
    Patch(facecolor="#D55E00", alpha=0.85, label="Wochen-Sentiment negativ"),
    Line2D([], [], ls="none", marker="o", ms=4, color="#777777", label="neutrale Woche (Median 0)"),
]

for pair in ["EUR_USD", "GBP_USD"]:
    pw = price[pair].resample("W-FRI").last().dropna()
    sw = eodhd_sent(pair).resample("W-FRI").median()
    sw = sw.reindex(pw.index)
    n_neutral = int((sw == 0).sum())
    print(f"  {pair}: {int(sw.notna().sum())} Wochen mit Artikeln, davon exakt neutral (Median 0): "
          f"{n_neutral}, ohne Artikel: {int(sw.isna().sum())}")
    zoom_start = pw.index.max() - pd.DateOffset(months=12)
    pad = 0.05 * (sw.max() - sw.min())
    sent_ylim = (sw.min() - pad, sw.max() + pad)
    fig, (ax_full, ax_zoom) = plt.subplots(2, 1, figsize=(11, 7.5))
    plot_price_sentiment(ax_full, pw, sw, bar_width=5, sent_ylim=sent_ylim)
    ax_full.axvspan(zoom_start, pw.index.max(), color="#999999", alpha=0.12)
    ax_full.set_title(f"{PAIR_LABEL[pair]}: Kursniveau und Nachrichten-Sentiment je Woche, gesamter Zeitraum")
    ax_full.legend(handles=WEEKLY_LEGEND, loc="upper left", fontsize=8)
    pz, sz = pw[pw.index >= zoom_start], sw[sw.index >= zoom_start]
    plot_price_sentiment(ax_zoom, pz, sz, bar_width=4, zoom=True, sent_ylim=sent_ylim)
    ax_zoom.set_title("Vergrösserung: die letzten zwölf Monate (grau markierter Bereich oben)")
    fig.tight_layout()
    fig.savefig(FIG / f"fig_weekly_{pair}.png")
    plt.close(fig)
    print(f"gespeichert: fig_weekly_{pair}.png")

# ===========================================================================
# Abbildung 3: Niveau-/Vorlauf-Prüfung -- Sentiment Woche t vs. kumulative
# Kursbewegung über die nächsten k Wochen (beantwortet #40)
# ===========================================================================
print("\n--- Niveau-/Vorlauf-Prüfung (Wochen): corr(Sentiment_t, kumul. Kursbewegung bis t+k) ---")
fig, ax = plt.subplots(figsize=(8, 4.2))
ks = list(range(0, 5))
width = 0.35
for i, (pair, color) in enumerate([("EUR_USD", "#0072B2"), ("GBP_USD", "#E69F00")]):
    pw = price[pair].resample("W-FRI").last()
    sw = eodhd_sent(pair).resample("W-FRI").median()
    vals = []
    for k in ks:
        if k == 0:
            fut = np.log(pw).diff()                      # Kursbewegung in derselben Woche
        else:
            fut = np.log(pw).shift(-k) - np.log(pw)      # kumulative Bewegung über nächste k Wochen
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
# Zusammenhang im selben Zeitraum je Zeithorizont (Tag/Woche/Monat/Quartal)
# und Vorlauf-Check auf Monatsebene (Tabelle im Bericht, Kapitel 9.3)
# ===========================================================================
print("\n--- Zusammenhang im selben Zeitraum je Zeithorizont ---")
for pair in ["EUR_USD", "GBP_USD"]:
    s = eodhd_sent(pair)
    parts = []
    for label, freq in [("Tag", None), ("Woche", "W-FRI"), ("Monat", "ME"), ("Quartal", "QE")]:
        if freq is None:
            ret, sv = np.log(price[pair]).diff(), s
        else:
            pw = price[pair].resample(freq).last()
            ret, sv = np.log(pw).diff(), s.resample(freq).median()
        a = pd.concat([sv, ret], axis=1).dropna()
        r = a.iloc[:, 0].corr(a.iloc[:, 1]) if len(a) >= 5 else np.nan
        parts.append(f"{label}: r={r:+.3f} (n={len(a)})")
        if freq == "ME":  # Vorlauf-Check: Sentiment Monat t vs. Bewegung Monat t+1
            b = pd.concat([sv, ret.shift(-1)], axis=1).dropna()
            parts.append(f"Monat t+1: r={b.iloc[:, 0].corr(b.iloc[:, 1]):+.3f} (n={len(b)})")
    print(f"  {pair}: " + " | ".join(parts))

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
    # beste Ausrichtung wie in der Pipeline (regenerate_forex_combined.py):
    # Versatz 0 bevorzugen, ausser ein anderer gewinnt um MIN_CORR_GAIN
    corr_at = {s: rc(y, e.set_axis(e.index + pd.Timedelta(days=s))) for s in range(-2, 3)}
    best = max(corr_at, key=lambda s: (corr_at[s] if corr_at[s] == corr_at[s] else -2))
    if not (best != 0 and corr_at[best] - corr_at[0] >= 0.15):
        best = 0
    after.append(corr_at[best])
fig, ax = plt.subplots(figsize=(7.5, 4.2))
x = np.arange(len(pairs))
b1 = ax.bar(x - 0.2, before, 0.4, label="vor Ausrichtung", color="#E69F00")
b2 = ax.bar(x + 0.2, after, 0.4, label="nach Ausrichtung", color="#0072B2")
ax.bar_label(b1, labels=[f"{round(v, 2) + 0.0:.2f}" for v in before], fontsize=9)
ax.bar_label(b2, labels=[f"{round(v, 2) + 0.0:.2f}" for v in after], fontsize=9)
ax.set_xticks(x)
ax.set_xticklabels([PAIR_LABEL[p] for p in pairs])
ax.set_ylabel("Korrelation der Tagesveränderungen\n(Yahoo vs. EODHD)")
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
    # zur Laufzeit begrenzen: gleichmässige Stichprobe von höchstens 800 Artikeln je Paar
    if len(d) > 800:
        d = d.iloc[:: max(1, len(d) // 800)]
    for _, r in d.iterrows():
        # pd.isna-sicher: NaN darf nicht als Literal-Text "nan" einfliessen
        parts = [str(x) for x in (r.get("title"), r.get("content")) if isinstance(x, str) and x.strip()]
        text = ". ".join(parts)[:600].strip()
        if not text:
            continue
        rows.append((r["polarity"], TextBlob(text).sentiment.polarity))
cmp = pd.DataFrame(rows, columns=["eodhd", "textblob"])
corr_sent = cmp["eodhd"].corr(cmp["textblob"])
print(f"\n--- Sentiment-Vergleich: Korr(EODHD-Polarity, eigenes TextBlob) = {corr_sent:.3f} (n={len(cmp)}) ---")
fig, ax = plt.subplots(figsize=(6.5, 6))
ax.scatter(cmp["eodhd"], cmp["textblob"], s=8, alpha=0.25, color="#0072B2")
ax.axhline(0, color="grey", lw=0.6); ax.axvline(0, color="grey", lw=0.6)
ax.plot([-1, 1], [-1, 1], color="#555555", lw=1, ls="--", label="vollständige Übereinstimmung")
ax.set_xlabel("EODHD-Polarity (vorberechnet)")
ax.set_ylabel("Eigenes TextBlob-Sentiment")
ax.set_title(f"Eigenes Sentiment vs. EODHD auf demselben Text (Korrelation {corr_sent:.2f})")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "fig_sentiment_compare.png")
plt.close(fig)
print("gespeichert: fig_sentiment_compare.png")

# ===========================================================================
# Abbildung 8: Ölpreise (WTI und Brent) und Bezug zu den Wechselkursen
# ===========================================================================
def load_oil(name):
    f = sorted(glob.glob(str(DATA / f"raw/oil/yahoo/{name}_*.csv")))[-1]
    d = pd.read_csv(f, index_col=0, parse_dates=True)
    d.index = pd.to_datetime(d.index, utc=True).tz_localize(None).normalize()
    return d["Close"]

wti = load_oil("WTI_Crude_Oil")
brent = load_oil("Brent_Crude_Oil")
fig, ax = plt.subplots(figsize=(9, 4.2))
ax.plot(wti.index, wti.values, color="#0072B2", lw=1.2, label="WTI")
ax.plot(brent.index, brent.values, color="#E69F00", lw=1.2, label="Brent")
ax.set_ylabel("Ölpreis in US-Dollar je Barrel")
ax.set_title("Ölpreise WTI und Brent im Zeitverlauf")
ax.legend()
fig.tight_layout()
fig.savefig(FIG / "fig_oil.png")
plt.close(fig)
print("gespeichert: fig_oil.png")
print("--- Bezug Öl zu Wechselkursen (Korrelation der Tagesveränderungen) ---")
for pair in ["EUR_USD", "GBP_USD"]:
    pr = price[pair].dropna()
    for oname, oser in [("WTI", wti), ("Brent", brent)]:
        c = pd.concat([np.log(pr).diff(), np.log(oser).diff()], axis=1).dropna()
        print(f"  {pair} vs {oname}: {c.iloc[:,0].corr(c.iloc[:,1]):+.3f}")

# ===========================================================================
# Abbildung (Anhang E): monatliche Datenabdeckung je Quelle und Paar
# ===========================================================================
def raw_mt():
    f = sorted(glob.glob(str(DATA / "raw/forex/metatrader/*Daily*")))[0]
    d = pd.read_csv(f, sep="\t")
    d.columns = [c.strip("<>").lower() for c in d.columns]
    d["date"] = pd.to_datetime(d["date"])
    return d.set_index("date")["close"]


cov_series = {}
for p in pairs:
    cov_series[f"Yahoo {PAIR_LABEL[p]}"] = raw_yahoo(p)
    cov_series[f"EODHD {PAIR_LABEL[p]}"] = raw_eodhd(p)
cov_series["MetaTrader EUR/USD"] = raw_mt()

cov = pd.DataFrame({name: s.resample("ME").count() for name, s in cov_series.items()}).T
cov_labels = [c.strftime("%Y-%m") for c in cov.columns]
fig, ax = plt.subplots(figsize=(12, 3.8))
im = ax.imshow(cov.values, aspect="auto", cmap="Blues", vmin=0)
ax.set_yticks(range(len(cov.index)))
ax.set_yticklabels(cov.index, fontsize=8)
xticks = list(range(0, cov.shape[1], 3))
ax.set_xticks(xticks)
ax.set_xticklabels([cov_labels[i] for i in xticks], fontsize=7, rotation=45)
fig.colorbar(im, ax=ax, label="Tage mit Daten im Monat")
ax.set_title("Monatliche Datenabdeckung je Quelle und Währungspaar")
ax.grid(False)
fig.tight_layout()
fig.savefig(FIG / "fig_coverage.png")
plt.close(fig)
print("gespeichert: fig_coverage.png")

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
