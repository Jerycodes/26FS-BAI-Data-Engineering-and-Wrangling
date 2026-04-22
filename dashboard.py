"""
Forex, Öl & News Daten-Dashboard
Starten mit: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import glob
import os

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Forex Data Wrangling Dashboard",
    page_icon="📈",
    layout="wide",
)

DATA_DIR = "data"
PAIRS = ["EUR_USD", "EUR_CHF", "GBP_USD"]
PAIR_LABELS = {"EUR_USD": "EUR/USD", "EUR_CHF": "EUR/CHF", "GBP_USD": "GBP/USD"}
OIL_TICKERS = ["WTI_Crude_Oil", "Brent_Crude_Oil"]
OIL_LABELS = {"WTI_Crude_Oil": "WTI Crude Oil", "Brent_Crude_Oil": "Brent Crude Oil"}

# ---------------------------------------------------------------------------
# Data Loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data
def load_combined_forex():
    path = os.path.join(DATA_DIR, "processed", "forex", "forex_alle_quellen_kombiniert.csv")
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df


@st.cache_data
def load_raw_sources():
    """Lade alle Rohdaten für detaillierten Vergleich."""
    data = {}
    for pair in PAIRS:
        data[pair] = {}

        # Yahoo
        files = sorted(glob.glob(os.path.join(DATA_DIR, "raw", "forex", "yahoo", f"{pair}_*.csv")))
        if files:
            df = pd.read_csv(files[-1], index_col=0, parse_dates=True)
            df.index = pd.to_datetime(df.index, utc=True).tz_localize(None).ceil("D")
            df = df[~df.index.duplicated(keep="first")]
            df = df.rename(columns=str.lower)
            data[pair]["yahoo"] = df

        # EODHD
        files = sorted(glob.glob(os.path.join(DATA_DIR, "raw", "forex", "eodhd", f"{pair}_*.csv")))
        if files:
            df = pd.read_csv(files[-1], index_col=0, parse_dates=True)
            df.index = pd.to_datetime(df.index).normalize()
            data[pair]["eodhd"] = df

    # MetaTrader nur EUR/USD
    mt_path = os.path.join(DATA_DIR, "raw", "forex", "metatrader", "EURUSD_Daily_202201030000_202512260000.csv")
    if os.path.exists(mt_path):
        df = pd.read_csv(mt_path, sep="\t")
        df.columns = [c.strip("<>").lower() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"], format="%Y.%m.%d")
        df = df.set_index("date")
        data["EUR_USD"]["metatrader"] = df

    return data


@st.cache_data
def load_oil_data():
    """Lade Ölpreisdaten von Yahoo Finance."""
    oil = {}
    for ticker in OIL_TICKERS:
        files = sorted(glob.glob(os.path.join(DATA_DIR, "raw", "oil", "yahoo", f"{ticker}_*.csv")))
        if files:
            df = pd.read_csv(files[-1], index_col=0, parse_dates=True)
            df.index = pd.to_datetime(df.index, utc=True).tz_localize(None).ceil("D")
            df = df[~df.index.duplicated(keep="first")]
            df = df.rename(columns=str.lower)
            oil[ticker] = df
    return oil


@st.cache_data
def load_news_eodhd():
    """Lädt EODHD-News pro Paar und filtert defensiv nach dem kanonischen FX-Symbol.

    Parst ausserdem `symbols` und `tags` zu echten Listen, damit das Dashboard
    nach Tags filtern kann.
    """
    import ast

    def _parse(val):
        if isinstance(val, list):
            return val
        if not isinstance(val, str) or not val.strip():
            return []
        try:
            return ast.literal_eval(val)
        except (ValueError, SyntaxError):
            return []

    pair_symbol = {"EUR_USD": "EURUSD.FOREX", "EUR_CHF": "EURCHF.FOREX", "GBP_USD": "GBPUSD.FOREX"}
    dfs = {}
    for pair in PAIRS:
        files = sorted(glob.glob(os.path.join(DATA_DIR, "raw", "news", "eodhd", f"{pair}_news_*.csv")))
        if files:
            df = pd.read_csv(files[-1])
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["date_only"] = pd.to_datetime(df["date_only"], errors="coerce")
            df["symbols_list"] = df["symbols"].apply(_parse)
            df["tags_list"] = df["tags"].apply(_parse)
            sym = pair_symbol[pair]
            df = df[df["symbols_list"].apply(lambda l: sym in l)].reset_index(drop=True)
            dfs[pair] = df
    return dfs


@st.cache_data
def load_news_webscraping():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "raw", "news", "webscraping", "all_scraped_news_*.csv")))
    files = [f for f in files if "PRE-FIX" not in f]
    if not files:
        return pd.DataFrame()
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df["scrape_file"] = os.path.basename(f)
        dfs.append(df)
    df = pd.concat(dfs, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["date_only"] = pd.to_datetime(df["date_only"], errors="coerce")
    # Deduplizieren nach Artikel-Link (gleicher Artikel in mehreren Scrapes)
    df = df.drop_duplicates(subset="link", keep="first").reset_index(drop=True)
    return df


@st.cache_data
def load_webscraping_sentiment_daily():
    """Liest das aggregierte Tagesmedian-Sentiment aus dem PoC-Pipeline-Output."""
    path = os.path.join(DATA_DIR, "processed", "news", "webscraping_sentiment_daily.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, index_col="date", parse_dates=True)
    return df


@st.cache_data
def load_webscraping_articles_sentiment():
    """Liest die unique Artikel mit TextBlob-Sentiment aus dem PoC-Pipeline-Output."""
    path = os.path.join(DATA_DIR, "processed", "news", "webscraping_articles_sentiment.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df["date_only"] = pd.to_datetime(df["date_only"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df_combined = load_combined_forex()
raw_data = load_raw_sources()
oil_data = load_oil_data()
news_eodhd = load_news_eodhd()
news_scraping = load_news_webscraping()
webscraping_sent_daily = load_webscraping_sentiment_daily()
webscraping_articles_sent = load_webscraping_articles_sentiment()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("📈 Forex & Öl Dashboard")

page = st.sidebar.radio("Navigation", [
    "Übersicht",
    "Quellenvergleich",
    "Lückenanalyse",
    "Preisabweichungen",
    "Ölpreise",
    "Nachrichten",
    "Sentiment-Vergleich",
    "Eigene Grafik",
    "Master Grafik",
    "Master Grafik 2",
])

# ---------------------------------------------------------------------------
# Page: Übersicht
# ---------------------------------------------------------------------------
if page == "Übersicht":
    st.title("Forex-Daten Übersicht")

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Währungspaare", len(PAIRS))
    col2.metric("Datenquellen", "3 (Yahoo, EODHD, MT5)")
    col3.metric("Total Datenpunkte", f"{len(df_combined):,}")

    n_gaps = df_combined["has_gap"].sum()
    col4.metric("Tage mit Lücken", n_gaps)

    st.markdown("---")

    # Übersicht pro Paar
    for pair in PAIRS:
        pair_data = df_combined[df_combined["pair"] == pair]
        st.subheader(PAIR_LABELS[pair])

        sources = [s for s in ["yahoo", "eodhd", "metatrader"] if f"{s}_close" in pair_data.columns and pair_data[f"{s}_close"].notna().any()]

        fig = go.Figure()
        for source in sources:
            col_name = f"{source}_close"
            series = pair_data[col_name].dropna()
            fig.add_trace(go.Scatter(
                x=series.index, y=series,
                name=source.capitalize(),
                mode="lines",
                line=dict(width=1),
            ))
        fig.update_layout(
            height=350,
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis_title="Datum",
            yaxis_title="Close-Preis",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Tabelle unter der Grafik
        with st.expander(f"Daten anzeigen: {PAIR_LABELS[pair]}"):
            table_cols = [f"{s}_close" for s in sources]
            st.dataframe(pair_data[table_cols].dropna(how="all").round(6), use_container_width=True, height=300)

# ---------------------------------------------------------------------------
# Page: Quellenvergleich
# ---------------------------------------------------------------------------
elif page == "Quellenvergleich":
    st.title("Quellenvergleich")

    pair = st.selectbox("Währungspaar", PAIRS, format_func=lambda x: PAIR_LABELS[x])
    pair_data = df_combined[df_combined["pair"] == pair]
    sources = [s for s in ["yahoo", "eodhd", "metatrader"] if f"{s}_close" in pair_data.columns and pair_data[f"{s}_close"].notna().any()]

    col_type = st.selectbox("Preis-Typ", ["close", "open", "high", "low"])

    date_range = st.date_input(
        "Zeitraum",
        value=(pair_data.index.min().date(), pair_data.index.max().date()),
        min_value=pair_data.index.min().date(),
        max_value=pair_data.index.max().date(),
    )
    if len(date_range) == 2:
        mask = (pair_data.index.date >= date_range[0]) & (pair_data.index.date <= date_range[1])
        pair_data = pair_data[mask]

    # Kursverlauf
    st.subheader(f"{PAIR_LABELS[pair]} - {col_type.capitalize()} Preis")
    fig = go.Figure()
    for source in sources:
        col_name = f"{source}_{col_type}"
        series = pair_data[col_name].dropna()
        fig.add_trace(go.Scatter(
            x=series.index, y=series,
            name=source.capitalize(),
            mode="lines",
            line=dict(width=1),
        ))
    fig.update_layout(height=450, hovermode="x unified", xaxis_title="Datum", yaxis_title="Preis")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Daten anzeigen"):
        table_cols = [f"{s}_{col_type}" for s in sources]
        st.dataframe(pair_data[table_cols].dropna(how="all").round(6), use_container_width=True, height=300)

    # Differenzen
    if len(sources) >= 2:
        st.subheader("Differenzen zwischen Quellen")
        ref_source = st.selectbox("Referenzquelle", sources, index=0)
        other_sources = [s for s in sources if s != ref_source]

        fig_diff = go.Figure()
        for other in other_sources:
            ref_col = f"{ref_source}_{col_type}"
            other_col = f"{other}_{col_type}"
            diff = pair_data[ref_col] - pair_data[other_col]
            fig_diff.add_trace(go.Scatter(
                x=diff.index, y=diff,
                name=f"{ref_source} - {other}",
                mode="lines",
                line=dict(width=1),
            ))
        fig_diff.add_hline(y=0, line_dash="dash", line_color="red", opacity=0.3)
        fig_diff.update_layout(height=350, hovermode="x unified", yaxis_title="Differenz")
        st.plotly_chart(fig_diff, use_container_width=True)

        with st.expander("Differenzen anzeigen"):
            diff_table = pd.DataFrame()
            for other in other_sources:
                diff_table[f"{ref_source} - {other}"] = pair_data[f"{ref_source}_{col_type}"] - pair_data[f"{other}_{col_type}"]
            st.dataframe(diff_table.dropna(how="all").round(6), use_container_width=True, height=300)

    # Statistiken
    st.subheader("Deskriptive Statistik")
    stats_cols = [f"{s}_{col_type}" for s in sources]
    stats_df = pair_data[stats_cols].describe().T
    stats_df.index = [s.replace(f"_{col_type}", "").capitalize() for s in stats_df.index]
    st.dataframe(stats_df.round(6), use_container_width=True)

# ---------------------------------------------------------------------------
# Page: Lückenanalyse
# ---------------------------------------------------------------------------
elif page == "Lückenanalyse":
    st.title("Lückenanalyse - Fehlende Daten")

    pair = st.selectbox("Währungspaar", PAIRS, format_func=lambda x: PAIR_LABELS[x])
    pair_data = df_combined[df_combined["pair"] == pair]

    sources = [s for s in ["yahoo", "eodhd", "metatrader"] if f"{s}_close" in pair_data.columns and pair_data[f"{s}_close"].notna().any()]

    only_weekdays = st.checkbox("Nur Wochentage anzeigen", value=True)
    if only_weekdays:
        pair_data = pair_data[~pair_data["is_weekend"]]

    # Heatmap: Datenverfügbarkeit pro Monat
    st.subheader("Monatliche Datenverfügbarkeit")
    coverage = pd.DataFrame(index=pair_data.index)
    for source in sources:
        coverage[source] = pair_data[f"{source}_close"].notna().astype(int)

    monthly = coverage.resample("ME").mean()
    fig_heat = px.imshow(
        monthly.T.values,
        x=monthly.index.strftime("%Y-%m"),
        y=[s.capitalize() for s in sources],
        color_continuous_scale="RdYlGn",
        zmin=0, zmax=1,
        labels=dict(color="Abdeckung"),
        aspect="auto",
    )
    fig_heat.update_layout(height=200 + 50 * len(sources), xaxis=dict(tickangle=45))
    st.plotly_chart(fig_heat, use_container_width=True)

    # Tage mit Lücken
    st.subheader("Tage mit fehlenden Daten")
    gaps = pair_data[pair_data["has_gap"]]
    if len(gaps) == 0:
        st.success("Keine Lücken gefunden!")
    else:
        st.warning(f"{len(gaps)} Tage mit Lücken")
        gap_display = gaps.copy()
        gap_display["fehlend_in"] = ""
        for idx, row in gap_display.iterrows():
            missing = [s for s in sources if pd.isna(row[f"{s}_close"])]
            gap_display.loc[idx, "fehlend_in"] = ", ".join(missing)
        display_cols = ["weekday_name", "n_sources", "fehlend_in"] + [f"{s}_close" for s in sources]
        st.dataframe(gap_display[display_cols], use_container_width=True, height=400)

    # Tagesabdeckung
    st.subheader("Tagesweise Abdeckung (letzte 60 Tage)")
    recent = coverage.tail(60)
    fig_daily = px.imshow(
        recent.T.values,
        x=recent.index.strftime("%Y-%m-%d"),
        y=[s.capitalize() for s in sources],
        color_continuous_scale=["#ff4444", "#44bb44"],
        zmin=0, zmax=1,
        aspect="auto",
    )
    fig_daily.update_layout(height=200 + 50 * len(sources), xaxis=dict(tickangle=45))
    st.plotly_chart(fig_daily, use_container_width=True)

# ---------------------------------------------------------------------------
# Page: Preisabweichungen
# ---------------------------------------------------------------------------
elif page == "Preisabweichungen":
    st.title("Preisabweichungen zwischen Quellen")

    pair = st.selectbox("Währungspaar", PAIRS, format_func=lambda x: PAIR_LABELS[x])
    pair_data = df_combined[df_combined["pair"] == pair]
    pair_data = pair_data[~pair_data["is_weekend"]]

    sources = [s for s in ["yahoo", "eodhd", "metatrader"] if f"{s}_close" in pair_data.columns and pair_data[f"{s}_close"].notna().any()]

    if len(sources) < 2:
        st.warning("Mindestens 2 Quellen nötig für Vergleich")
    else:
        col_type = st.selectbox("Preis-Typ", ["close", "open", "high", "low"])

        # Spread (Max - Min) über alle Quellen
        st.subheader("Täglicher Spread (Max - Min aller Quellen)")
        price_cols = [f"{s}_{col_type}" for s in sources]
        daily_max = pair_data[price_cols].max(axis=1)
        daily_min = pair_data[price_cols].min(axis=1)
        spread = daily_max - daily_min

        fig_spread = go.Figure()
        fig_spread.add_trace(go.Scatter(
            x=spread.index, y=spread,
            fill="tozeroy", fillcolor="rgba(255, 100, 100, 0.3)",
            line=dict(color="coral", width=1),
            name="Spread",
        ))
        fig_spread.update_layout(height=300, yaxis_title="Spread (absolut)", hovermode="x unified")
        st.plotly_chart(fig_spread, use_container_width=True)

        with st.expander("Spread-Daten anzeigen"):
            spread_table = pd.DataFrame({"spread": spread})
            for s in sources:
                spread_table[f"{s}_{col_type}"] = pair_data[f"{s}_{col_type}"]
            st.dataframe(spread_table.dropna(how="all").round(6), use_container_width=True, height=300)

        # Statistiken
        col1, col2, col3 = st.columns(3)
        col1.metric("Mittlerer Spread", f"{spread.mean():.6f}")
        col2.metric("Maximaler Spread", f"{spread.max():.6f}")
        col3.metric("Tage > 0.01 Spread", f"{(spread > 0.01).sum()}")

        # Paarweiser Vergleich
        st.subheader("Paarweiser Vergleich")
        src_a = st.selectbox("Quelle A", sources, index=0)
        src_b = st.selectbox("Quelle B", [s for s in sources if s != src_a], index=0)

        diff = pair_data[f"{src_a}_{col_type}"] - pair_data[f"{src_b}_{col_type}"]
        diff = diff.dropna()

        col1, col2 = st.columns(2)
        with col1:
            fig_hist = px.histogram(diff, nbins=100, title="Verteilung der Abweichungen")
            fig_hist.update_layout(height=350, xaxis_title="Differenz", yaxis_title="Anzahl Tage")
            st.plotly_chart(fig_hist, use_container_width=True)

        with col2:
            fig_scatter = px.scatter(
                x=pair_data[f"{src_a}_{col_type}"],
                y=pair_data[f"{src_b}_{col_type}"],
                title=f"{src_a.capitalize()} vs. {src_b.capitalize()}",
                labels={"x": src_a.capitalize(), "y": src_b.capitalize()},
                opacity=0.3,
            )
            min_val = min(pair_data[f"{src_a}_{col_type}"].min(), pair_data[f"{src_b}_{col_type}"].min())
            max_val = max(pair_data[f"{src_a}_{col_type}"].max(), pair_data[f"{src_b}_{col_type}"].max())
            fig_scatter.add_trace(go.Scatter(x=[min_val, max_val], y=[min_val, max_val],
                                             mode="lines", line=dict(color="red", dash="dash"), name="Diagonale"))
            fig_scatter.update_layout(height=350)
            st.plotly_chart(fig_scatter, use_container_width=True)

        # Top Abweichungen
        st.subheader("Top-10 grösste Abweichungen")
        top = diff.abs().nlargest(10)
        top_df = pd.DataFrame({
            "Datum": top.index.strftime("%Y-%m-%d"),
            "Differenz": diff.loc[top.index].values,
            f"{src_a} {col_type}": pair_data.loc[top.index, f"{src_a}_{col_type}"].values,
            f"{src_b} {col_type}": pair_data.loc[top.index, f"{src_b}_{col_type}"].values,
        })
        st.dataframe(top_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Page: Ölpreise
# ---------------------------------------------------------------------------
elif page == "Ölpreise":
    st.title("Ölpreise: WTI & Brent Crude Oil")

    if not oil_data:
        st.warning("Keine Öldaten vorhanden. Bitte zuerst das Notebook 05_eda_oil_yahoo.ipynb ausführen.")
    else:
        # KPIs
        col1, col2, col3 = st.columns(3)
        if "WTI_Crude_Oil" in oil_data:
            wti_last = oil_data["WTI_Crude_Oil"]["close"].dropna().iloc[-1]
            col1.metric("WTI (letzter Close)", f"${wti_last:.2f}")
        if "Brent_Crude_Oil" in oil_data:
            brent_last = oil_data["Brent_Crude_Oil"]["close"].dropna().iloc[-1]
            col2.metric("Brent (letzter Close)", f"${brent_last:.2f}")
        if "WTI_Crude_Oil" in oil_data and "Brent_Crude_Oil" in oil_data:
            spread_last = brent_last - wti_last
            col3.metric("Brent-WTI Spread", f"${spread_last:.2f}")

        st.markdown("---")

        # Kursverlauf
        st.subheader("Kursverlauf (USD/Barrel)")
        fig_oil = go.Figure()
        for ticker in OIL_TICKERS:
            if ticker in oil_data:
                series = oil_data[ticker]["close"].dropna()
                fig_oil.add_trace(go.Scatter(
                    x=series.index, y=series,
                    name=OIL_LABELS[ticker],
                    mode="lines", line=dict(width=1),
                ))
        fig_oil.update_layout(height=450, hovermode="x unified", xaxis_title="Datum", yaxis_title="Preis (USD)",
                              legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig_oil, use_container_width=True)

        with st.expander("Öldaten anzeigen"):
            oil_table = pd.DataFrame({OIL_LABELS[t]: oil_data[t]["close"] for t in OIL_TICKERS if t in oil_data})
            st.dataframe(oil_table.dropna(how="all").round(2), use_container_width=True, height=300)

        # Brent-WTI Spread
        if "WTI_Crude_Oil" in oil_data and "Brent_Crude_Oil" in oil_data:
            st.subheader("Brent-WTI Spread")
            spread_df = pd.DataFrame({
                "WTI": oil_data["WTI_Crude_Oil"]["close"],
                "Brent": oil_data["Brent_Crude_Oil"]["close"],
            }).dropna()
            spread_df["Spread"] = spread_df["Brent"] - spread_df["WTI"]

            fig_spread = go.Figure()
            fig_spread.add_trace(go.Scatter(
                x=spread_df.index, y=spread_df["Spread"],
                fill="tozeroy", fillcolor="rgba(100, 150, 255, 0.3)",
                line=dict(color="steelblue", width=1), name="Spread",
            ))
            fig_spread.add_hline(y=spread_df["Spread"].mean(), line_dash="dash", line_color="red",
                                 annotation_text=f"Mittelwert: ${spread_df['Spread'].mean():.2f}")
            fig_spread.update_layout(height=300, yaxis_title="Spread (USD)", hovermode="x unified")
            st.plotly_chart(fig_spread, use_container_width=True)

        # Korrelation mit Forex
        st.subheader("Korrelation Öl vs. Forex (tägliche Renditen)")
        all_close = pd.DataFrame()
        for ticker in OIL_TICKERS:
            if ticker in oil_data:
                all_close[OIL_LABELS[ticker]] = oil_data[ticker]["close"]
        for pair in PAIRS:
            files = sorted(glob.glob(os.path.join(DATA_DIR, "raw", "forex", "yahoo", f"{pair}_*.csv")))
            if files:
                df_fx = pd.read_csv(files[-1], index_col=0, parse_dates=True)
                df_fx.index = pd.to_datetime(df_fx.index, utc=True).tz_localize(None).ceil("D")
                df_fx = df_fx[~df_fx.index.duplicated(keep="first")]
                df_fx = df_fx.rename(columns=str.lower)
                all_close[PAIR_LABELS[pair]] = df_fx["close"]

        all_close = all_close.dropna()
        if len(all_close) > 30:
            returns = all_close.pct_change().dropna()
            corr = returns.corr()

            fig_corr = px.imshow(
                corr.values, x=corr.columns, y=corr.index,
                color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
                text_auto=".3f", aspect="auto",
            )
            fig_corr.update_layout(height=400, title="Korrelationsmatrix (tägliche Renditen)")
            st.plotly_chart(fig_corr, use_container_width=True)

            # Rollende Korrelation
            st.subheader("Rollende Korrelation: WTI vs. Forex")
            window = st.slider("Rolling-Window (Tage)", 10, 120, 30, key="oil_window")

            fig_roll = go.Figure()
            for pair in PAIRS:
                label = PAIR_LABELS[pair]
                if "WTI Crude Oil" in returns.columns and label in returns.columns:
                    rolling_corr = returns["WTI Crude Oil"].rolling(window).corr(returns[label])
                    fig_roll.add_trace(go.Scatter(
                        x=rolling_corr.index, y=rolling_corr,
                        name=f"WTI vs. {label}", mode="lines", line=dict(width=1),
                    ))
            fig_roll.add_hline(y=0, line_dash="dash", line_color="black", opacity=0.3)
            fig_roll.update_layout(height=400, yaxis_title="Korrelation", hovermode="x unified",
                                   yaxis=dict(range=[-1, 1]))
            st.plotly_chart(fig_roll, use_container_width=True)

            # Normalisierte Kurse
            st.subheader("Normalisierte Kursentwicklung (Indexbasis 100)")
            normalized = (all_close / all_close.iloc[0]) * 100
            fig_norm = go.Figure()
            for col in normalized.columns:
                fig_norm.add_trace(go.Scatter(
                    x=normalized.index, y=normalized[col],
                    name=col, mode="lines", line=dict(width=1),
                ))
            fig_norm.add_hline(y=100, line_dash="dash", line_color="black", opacity=0.3)
            fig_norm.update_layout(height=450, yaxis_title="Index (Start = 100)", hovermode="x unified",
                                   legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig_norm, use_container_width=True)
        else:
            st.warning("Nicht genügend gemeinsame Handelstage für Korrelationsanalyse.")

# ---------------------------------------------------------------------------
# Page: Nachrichten
# ---------------------------------------------------------------------------
elif page == "Nachrichten":
    st.title("Nachrichten-Daten")

    tab1, tab2 = st.tabs(["EODHD News", "Webscraping News"])

    with tab1:
        if news_eodhd:
            pair = st.selectbox("Währungspaar", list(news_eodhd.keys()), format_func=lambda x: PAIR_LABELS.get(x, x))
            df_news = news_eodhd[pair]

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Artikel", len(df_news))
            if "polarity" in df_news.columns:
                col2.metric("Mit Sentiment", df_news["polarity"].notna().sum())
                col3.metric("Ohne Sentiment", df_news["polarity"].isna().sum())

            # Artikel pro Tag
            st.subheader("Artikel pro Tag")
            daily = df_news.groupby("date_only").size().reset_index(name="count")
            fig = px.bar(daily, x="date_only", y="count", title="Anzahl Artikel pro Tag")
            fig.update_layout(height=300, xaxis_title="Datum", yaxis_title="Anzahl")
            st.plotly_chart(fig, use_container_width=True)

            # Sentiment-Verteilung
            if "polarity" in df_news.columns:
                st.subheader("Sentiment-Verteilung")
                fig_sent = px.histogram(df_news.dropna(subset=["polarity"]), x="polarity", nbins=50,
                                        title="Polarity-Verteilung")
                fig_sent.update_layout(height=300)
                st.plotly_chart(fig_sent, use_container_width=True)

            # Tabelle
            st.subheader("Artikel-Tabelle")
            display_cols = [c for c in ["date_only", "title", "polarity", "neg", "neu", "pos"] if c in df_news.columns]
            st.dataframe(df_news[display_cols].head(100), use_container_width=True, height=400)
        else:
            st.info("Keine EODHD News-Daten vorhanden.")

    with tab2:
        if not news_scraping.empty:
            col1, col2 = st.columns(2)
            col1.metric("Total Einträge", len(news_scraping))
            col2.metric("Quellen", news_scraping["source"].nunique() if "source" in news_scraping.columns else "?")

            if "source" in news_scraping.columns:
                st.subheader("Artikel pro Quelle")
                source_counts = news_scraping["source"].value_counts()
                fig = px.bar(x=source_counts.index, y=source_counts.values,
                             title="Anzahl Artikel pro Quelle")
                fig.update_layout(height=350, xaxis_title="Quelle", yaxis_title="Anzahl")
                st.plotly_chart(fig, use_container_width=True)

            st.subheader("Artikel-Tabelle")
            display_cols = [c for c in ["date_only", "source", "title", "summary"] if c in news_scraping.columns]
            st.dataframe(news_scraping[display_cols].head(100), use_container_width=True, height=400)
        else:
            st.info("Keine Webscraping News-Daten vorhanden.")

# ---------------------------------------------------------------------------
# Page: Sentiment-Vergleich
# ---------------------------------------------------------------------------
elif page == "Sentiment-Vergleich":
    st.title("Sentiment-Vergleich: EODHD vs. TextBlob")
    st.caption("Vergleich der vorberechneten EODHD-Polarity mit eigener TextBlob-Sentiment-Analyse auf dem Artikeltext.")

    from textblob import TextBlob

    @st.cache_data
    def compute_textblob_sentiment():
        """Berechnet TextBlob-Sentiment auf EODHD-Artikeltext für alle Paare."""
        results = {}
        for pair in PAIRS:
            if pair not in news_eodhd or news_eodhd[pair].empty:
                continue
            df = news_eodhd[pair].copy()
            # TextBlob auf title + content
            df["tb_title"] = df["title"].apply(
                lambda t: TextBlob(str(t)).sentiment.polarity if isinstance(t, str) and t.strip() else np.nan
            )
            df["tb_content"] = df["content"].apply(
                lambda t: TextBlob(str(t)).sentiment.polarity if isinstance(t, str) and t.strip() else np.nan
            )
            df["tb_combined"] = df[["tb_title", "tb_content"]].mean(axis=1)
            results[pair] = df
        return results

    with st.spinner("TextBlob-Sentiment wird berechnet (dauert beim ersten Mal)..."):
        tb_data = compute_textblob_sentiment()

    pair = st.selectbox("Währungspaar", [p for p in PAIRS if p in tb_data],
                        format_func=lambda x: PAIR_LABELS[x], key="sv_pair")

    if pair in tb_data:
        df = tb_data[pair]

        # --- Tagesverlauf: Mean und Median ---
        st.subheader("Tagesverlauf: EODHD vs. TextBlob Polarity")
        agg_func = st.radio("Aggregation", ["Median", "Mittelwert"], horizontal=True, key="sv_agg")
        func = "median" if agg_func == "Median" else "mean"

        daily = df.groupby("date_only").agg(
            eodhd_polarity=("polarity", func),
            textblob_polarity=("tb_combined", func),
        ).sort_index().dropna()

        fig_daily = go.Figure()
        fig_daily.add_trace(go.Scatter(
            x=daily.index, y=daily["eodhd_polarity"],
            name="EODHD (vorberechnet)", line=dict(color="orange", width=1),
        ))
        fig_daily.add_trace(go.Scatter(
            x=daily.index, y=daily["textblob_polarity"],
            name="TextBlob (eigene Analyse)", line=dict(color="royalblue", width=1),
        ))
        fig_daily.add_hline(y=0, line_dash="dash", line_color="grey", line_width=0.5)
        fig_daily.update_layout(
            height=450,
            title=f"{PAIR_LABELS[pair]} – Tägliche Polarity ({agg_func})",
            yaxis_title="Polarity",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_daily, use_container_width=True)

        # --- Korrelation ---
        r = daily["eodhd_polarity"].corr(daily["textblob_polarity"])
        st.metric("Pearson-Korrelation (Tagesebene)", f"{r:.4f}", delta=None)

        # --- Scatter Plot ---
        st.subheader("Artikel-Ebene: EODHD vs. TextBlob Polarity")
        scatter_df = df.dropna(subset=["polarity", "tb_combined"])
        fig_scatter = px.scatter(
            scatter_df, x="polarity", y="tb_combined",
            opacity=0.1,
            labels={"polarity": "EODHD Polarity", "tb_combined": "TextBlob Polarity"},
            title=f"{PAIR_LABELS[pair]} – Artikel-Sentiment (n={len(scatter_df)})",
        )
        fig_scatter.add_shape(type="line", x0=-1, y0=-1, x1=1, y1=1,
                              line=dict(color="red", dash="dash", width=1))
        fig_scatter.update_layout(height=500)
        st.plotly_chart(fig_scatter, use_container_width=True)

        # --- Verteilung ---
        st.subheader("Verteilung der Polarity-Werte")
        col1, col2 = st.columns(2)
        with col1:
            fig_hist_e = px.histogram(scatter_df, x="polarity", nbins=50,
                                      title="EODHD (vorberechnet)", color_discrete_sequence=["orange"])
            st.plotly_chart(fig_hist_e, use_container_width=True)
        with col2:
            fig_hist_t = px.histogram(scatter_df, x="tb_combined", nbins=50,
                                      title="TextBlob (eigene Analyse)", color_discrete_sequence=["royalblue"])
            st.plotly_chart(fig_hist_t, use_container_width=True)

        # --- Statistik ---
        st.subheader("Statistik")
        stats = pd.DataFrame({
            "EODHD": scatter_df["polarity"].describe(),
            "TextBlob": scatter_df["tb_combined"].describe(),
        }).round(4)
        st.dataframe(stats, use_container_width=True)

# ---------------------------------------------------------------------------
# Page: Eigene Grafik
# ---------------------------------------------------------------------------
elif page == "Eigene Grafik":
    st.title("Eigene Grafik erstellen")

    pair = st.selectbox("Währungspaar", PAIRS, format_func=lambda x: PAIR_LABELS[x])
    pair_data = df_combined[df_combined["pair"] == pair]
    pair_data = pair_data[~pair_data["is_weekend"]]

    sources = [s for s in ["yahoo", "eodhd", "metatrader"] if f"{s}_close" in pair_data.columns and pair_data[f"{s}_close"].notna().any()]

    chart_type = st.selectbox("Diagramm-Typ", ["Linienchart", "Candlestick", "Renditen", "Korrelation", "Boxplot"])

    date_range = st.date_input(
        "Zeitraum",
        value=(pair_data.index.min().date(), pair_data.index.max().date()),
        min_value=pair_data.index.min().date(),
        max_value=pair_data.index.max().date(),
        key="custom_date",
    )
    if len(date_range) == 2:
        mask = (pair_data.index.date >= date_range[0]) & (pair_data.index.date <= date_range[1])
        pair_data = pair_data[mask]

    selected_sources = st.multiselect("Quellen", sources, default=sources)

    if chart_type == "Linienchart":
        col_type = st.selectbox("Preis-Typ", ["close", "open", "high", "low"], key="line_col")
        fig = go.Figure()
        for source in selected_sources:
            series = pair_data[f"{source}_{col_type}"].dropna()
            fig.add_trace(go.Scatter(x=series.index, y=series, name=source.capitalize(), mode="lines"))
        fig.update_layout(height=500, title=f"{PAIR_LABELS[pair]} - {col_type.capitalize()}", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Daten anzeigen"):
            table_cols = [f"{s}_{col_type}" for s in selected_sources]
            st.dataframe(pair_data[table_cols].dropna(how="all").round(6), use_container_width=True, height=300)

    elif chart_type == "Candlestick":
        source = st.selectbox("Quelle", selected_sources)
        fig = go.Figure(data=go.Candlestick(
            x=pair_data.index,
            open=pair_data[f"{source}_open"],
            high=pair_data[f"{source}_high"],
            low=pair_data[f"{source}_low"],
            close=pair_data[f"{source}_close"],
            name=source.capitalize(),
        ))
        fig.update_layout(height=500, title=f"{PAIR_LABELS[pair]} - {source.capitalize()} Candlestick",
                          xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Daten anzeigen"):
            ohlc_cols = [f"{source}_{c}" for c in ["open", "high", "low", "close"]]
            st.dataframe(pair_data[ohlc_cols].dropna(how="all").round(6), use_container_width=True, height=300)

    elif chart_type == "Renditen":
        col_type = st.selectbox("Preis-Typ", ["close", "open"], key="ret_col")
        fig = go.Figure()
        for source in selected_sources:
            returns = pair_data[f"{source}_{col_type}"].pct_change().dropna()
            fig.add_trace(go.Scatter(x=returns.index, y=returns, name=source.capitalize(), mode="lines",
                                     line=dict(width=0.8)))
        fig.add_hline(y=0, line_dash="dash", line_color="red", opacity=0.3)
        fig.update_layout(height=500, title=f"{PAIR_LABELS[pair]} - Tägliche Renditen", yaxis_title="Rendite",
                          hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Renditen anzeigen"):
            ret_table = pd.DataFrame()
            for source in selected_sources:
                ret_table[source] = pair_data[f"{source}_{col_type}"].pct_change()
            st.dataframe(ret_table.dropna(how="all").round(6), use_container_width=True, height=300)

    elif chart_type == "Korrelation":
        col_type = st.selectbox("Preis-Typ", ["close", "open", "high", "low"], key="corr_col")
        window = st.slider("Rolling-Window (Tage)", 10, 120, 30)

        if len(selected_sources) >= 2:
            prices = pd.DataFrame()
            for source in selected_sources:
                prices[source] = pair_data[f"{source}_{col_type}"]
            returns = prices.pct_change().dropna()

            fig = go.Figure()
            for i, src_a in enumerate(selected_sources):
                for src_b in selected_sources[i + 1:]:
                    rolling_corr = returns[src_a].rolling(window).corr(returns[src_b])
                    fig.add_trace(go.Scatter(
                        x=rolling_corr.index, y=rolling_corr,
                        name=f"{src_a} vs {src_b}",
                        mode="lines",
                    ))
            fig.update_layout(height=400, title=f"Rolling Korrelation ({window} Tage)", yaxis_title="Korrelation",
                              hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Korrelationsdaten anzeigen"):
                corr_table = pd.DataFrame()
                for i, src_a in enumerate(selected_sources):
                    for src_b in selected_sources[i + 1:]:
                        corr_table[f"{src_a} vs {src_b}"] = returns[src_a].rolling(window).corr(returns[src_b])
                st.dataframe(corr_table.dropna(how="all").round(6), use_container_width=True, height=300)
        else:
            st.info("Mindestens 2 Quellen auswählen.")

    elif chart_type == "Boxplot":
        col_type = st.selectbox("Preis-Typ", ["close", "open", "high", "low"], key="box_col")
        mode = st.radio("Modus", ["Preise", "Renditen"])

        fig = go.Figure()
        for source in selected_sources:
            if mode == "Preise":
                values = pair_data[f"{source}_{col_type}"].dropna()
            else:
                values = pair_data[f"{source}_{col_type}"].pct_change().dropna()
            fig.add_trace(go.Box(y=values, name=source.capitalize()))

        fig.update_layout(height=450, title=f"{PAIR_LABELS[pair]} - {mode} Boxplot ({col_type})")
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Daten anzeigen"):
            box_table = pd.DataFrame()
            for source in selected_sources:
                if mode == "Preise":
                    box_table[source] = pair_data[f"{source}_{col_type}"]
                else:
                    box_table[source] = pair_data[f"{source}_{col_type}"].pct_change()
            st.dataframe(box_table.dropna(how="all").round(6), use_container_width=True, height=300)

# ---------------------------------------------------------------------------
# Page: Master Grafik
# ---------------------------------------------------------------------------
elif page == "Master Grafik":
    st.title("Master Grafik")
    st.caption("Eine Grafik für alles: Forex, Öl und News-Sentiment frei kombinierbar mit Zeitraum, Aggregation und Normalisierung.")

    # ----- Sidebar-Steuerelemente -----
    st.sidebar.markdown("---")
    st.sidebar.subheader("Master Grafik Einstellungen")

    sel_pairs = st.sidebar.multiselect(
        "Währungspaare",
        PAIRS,
        default=["EUR_USD"],
        format_func=lambda x: PAIR_LABELS[x],
    )
    fx_source = st.sidebar.selectbox(
        "Forex-Quelle",
        ["mittelwert", "yahoo", "eodhd"],
        help="'mittelwert' = Mittelwert aus yahoo + eodhd (nur wo beide vorhanden)",
    )
    fx_field = st.sidebar.selectbox("Forex-Feld", ["close", "open", "high", "low"])

    sel_oils = st.sidebar.multiselect(
        "Ölpreise",
        OIL_TICKERS,
        default=[],
        format_func=lambda x: OIL_LABELS[x],
    )

    show_sentiment = st.sidebar.checkbox("News-Sentiment (EODHD polarity) anzeigen", value=True)
    sentiment_per_pair = st.sidebar.checkbox(
        "Sentiment pro Paar (sonst Mittel über gewählte Paare)",
        value=True,
        disabled=not show_sentiment,
    )

    # Tag-Filter aufbauen aus allen verfügbaren Tags der gewählten Paare
    available_tags: set[str] = set()
    if show_sentiment:
        for p in sel_pairs:
            df_n = news_eodhd.get(p)
            if df_n is not None and "tags_list" in df_n.columns:
                for lst in df_n["tags_list"]:
                    available_tags.update(lst)
    sel_tags = st.sidebar.multiselect(
        "News-Tags filtern (leer = alle)",
        sorted(available_tags),
        default=[],
        disabled=not show_sentiment,
        help="Ein Artikel zählt, wenn seine Tag-Liste mindestens einen der gewählten Tags enthält.",
    )

    freq_label = st.sidebar.selectbox(
        "Aggregation (Auflösung)",
        ["Täglich", "Wöchentlich", "Monatlich", "Quartalsweise"],
    )
    freq_map = {"Täglich": "D", "Wöchentlich": "W-MON", "Monatlich": "MS", "Quartalsweise": "QS"}
    freq = freq_map[freq_label]

    agg_label = st.sidebar.selectbox(
        "Aggregations-Funktion",
        ["Mittelwert", "Median", "Letzter Wert", "Min", "Max", "Summe"],
        help="Wie die täglichen Werte zu Wochen/Monaten/... zusammengefasst werden.",
    )
    agg_map = {"Mittelwert": "mean", "Median": "median", "Letzter Wert": "last", "Min": "min", "Max": "max", "Summe": "sum"}
    agg_func = agg_map[agg_label]

    fill_gaps = st.sidebar.checkbox(
        "Fehlende Tage interpolieren (linear, vor Aggregation)",
        value=False,
        help="Wochenenden/Feiertage werden zeitgewichtet linear gefüllt – nur sinnvoll bei täglicher Auflösung.",
    )
    normalize = st.sidebar.checkbox(
        "Normalisieren (Index = 100 am Startdatum)",
        value=False,
        help="Macht Reihen mit unterschiedlichen Skalen vergleichbar.",
    )

    # Zeitraum aus den verfügbaren Daten ableiten
    min_date = df_combined.index.min().date()
    max_date = df_combined.index.max().date()
    date_range = st.sidebar.date_input(
        "Zeitraum",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="master_date",
    )

    # ----- Daten zusammenstellen -----
    def get_fx_series(pair: str) -> pd.Series:
        sub = df_combined[df_combined["pair"] == pair]
        if fx_source == "mittelwert":
            yh = sub.get(f"yahoo_{fx_field}")
            ed = sub.get(f"eodhd_{fx_field}")
            if yh is None or ed is None:
                return pd.Series(dtype=float)
            both = pd.concat([yh, ed], axis=1)
            return both.mean(axis=1, skipna=False).dropna()
        col = f"{fx_source}_{fx_field}"
        if col not in sub.columns:
            return pd.Series(dtype=float)
        return sub[col].dropna()

    def get_oil_series(ticker: str) -> pd.Series:
        df = oil_data.get(ticker)
        if df is None or df.empty:
            return pd.Series(dtype=float)
        for c in ["close", "Close"]:
            if c in df.columns:
                return df[c].dropna()
        return pd.Series(dtype=float)

    def get_sentiment_series(pair: str) -> pd.Series:
        df = news_eodhd.get(pair)
        if df is None or df.empty or "polarity" not in df.columns:
            return pd.Series(dtype=float)
        if sel_tags:
            tag_set = set(sel_tags)
            df = df[df["tags_list"].apply(lambda l: bool(set(l) & tag_set))]
        if df.empty:
            return pd.Series(dtype=float)
        # Median pro Tag (robuster gegen einzelne extreme Artikel als der Mittelwert)
        s = df.dropna(subset=["date_only"]).groupby("date_only")["polarity"].median()
        s.index = pd.to_datetime(s.index)
        return s

    # Spalten in einem DataFrame sammeln, plus Kategorie-Mapping für die Achsenzuordnung
    series_dict: dict[str, pd.Series] = {}
    series_category: dict[str, str] = {}  # label -> 'forex' | 'oil' | 'sentiment'
    for p in sel_pairs:
        s = get_fx_series(p)
        if not s.empty:
            label = f"{PAIR_LABELS[p]} {fx_field} ({fx_source})"
            series_dict[label] = s
            series_category[label] = "forex"
    for o in sel_oils:
        s = get_oil_series(o)
        if not s.empty:
            label = f"{OIL_LABELS[o]} close"
            series_dict[label] = s
            series_category[label] = "oil"
    if show_sentiment and sel_pairs:
        if sentiment_per_pair:
            for p in sel_pairs:
                s = get_sentiment_series(p)
                if not s.empty:
                    label = f"Sentiment {PAIR_LABELS[p]}"
                    series_dict[label] = s
                    series_category[label] = "sentiment"
        else:
            parts = [get_sentiment_series(p) for p in sel_pairs]
            parts = [p for p in parts if not p.empty]
            if parts:
                merged = pd.concat(parts, axis=1).mean(axis=1)
                label = f"Sentiment Mittel ({len(parts)} Paare)"
                series_dict[label] = merged
                series_category[label] = "sentiment"

    if not series_dict:
        st.warning("Keine Reihen ausgewählt – bitte mindestens ein Paar oder einen Ölpreis wählen.")
        st.stop()

    df_master = pd.concat(series_dict, axis=1).sort_index()
    df_master.index = pd.to_datetime(df_master.index)

    # Zeitraum-Filter
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        df_master = df_master.loc[(df_master.index >= start) & (df_master.index <= end)]

    if df_master.empty:
        st.warning("Keine Daten im gewählten Zeitraum.")
        st.stop()

    # Optional interpolieren (vor Aggregation)
    if fill_gaps:
        full_idx = pd.date_range(df_master.index.min(), df_master.index.max(), freq="D")
        df_master = df_master.reindex(full_idx).interpolate(method="time")
        df_master.index.name = "date"

    # Aggregation
    if freq != "D":
        df_master = df_master.resample(freq).agg(agg_func)

    # Normalisierung (Index = 100 am ersten gültigen Wert pro Reihe)
    if normalize:
        first_valid = df_master.apply(lambda c: c.dropna().iloc[0] if c.dropna().size else np.nan)
        df_master = df_master.divide(first_valid).multiply(100)

    # ----- Plot mit dynamisch vielen Y-Achsen -----
    # Bei Normalisierung sind alle Reihen vergleichbar -> eine Achse.
    # Sonst kriegt jede vorhandene Kategorie (forex / oil / sentiment) eine eigene Y-Achse,
    # damit Reihen mit sehr unterschiedlichen Skalen (z.B. EUR/USD ~1.3 vs. Brent ~80 vs. Sentiment ~0.1)
    # alle gut sichtbar bleiben.
    CATEGORY_INFO = {
        "forex":     {"title": f"Forex-Kurs ({fx_field})", "color": "#1f77b4", "dash": "solid"},
        "oil":       {"title": "Öl (USD)",                 "color": "#2ca02c", "dash": "solid"},
        "sentiment": {"title": "Sentiment (polarity)",     "color": "#d62728", "dash": "dot"},
    }

    fig = go.Figure()

    if normalize:
        # Eine Achse, alles vergleichbar
        for col in df_master.columns:
            cat = series_category.get(col, "forex")
            fig.add_trace(go.Scatter(
                x=df_master.index, y=df_master[col], name=col, mode="lines",
                line=dict(dash=CATEGORY_INFO[cat]["dash"]),
            ))
        fig.update_layout(yaxis=dict(title="Index (Start = 100)"))
    else:
        # Welche Kategorien sind tatsächlich vorhanden? Reihenfolge bestimmt die Achsenzuordnung.
        cats_present = [c for c in ["forex", "oil", "sentiment"] if c in series_category.values()]
        # cat -> ('y', 'y2', 'y3')
        cat_to_axis = {cat: f"y{i+1}" if i > 0 else "y" for i, cat in enumerate(cats_present)}

        for col in df_master.columns:
            cat = series_category.get(col, "forex")
            info = CATEGORY_INFO[cat]
            fig.add_trace(go.Scatter(
                x=df_master.index, y=df_master[col], name=col, mode="lines",
                yaxis=cat_to_axis[cat],
                line=dict(dash=info["dash"]),
            ))

        # Achsen-Layout: Hauptachse links, weitere Achsen rechts mit Versatz
        layout_axes: dict = {}
        # X-Achse einschränken, damit rechts Platz für 1-2 zusätzliche Achsen ist
        n_extra = max(0, len(cats_present) - 1)
        right_padding = 0.06 * n_extra
        layout_axes["xaxis"] = dict(domain=[0.0, max(0.7, 1.0 - right_padding)])

        for i, cat in enumerate(cats_present):
            info = CATEGORY_INFO[cat]
            if i == 0:
                layout_axes["yaxis"] = dict(
                    title=dict(text=info["title"], font=dict(color=info["color"])),
                    tickfont=dict(color=info["color"]),
                )
            else:
                position = 1.0 - 0.06 * (i - 1)
                layout_axes[f"yaxis{i+1}"] = dict(
                    title=dict(text=info["title"], font=dict(color=info["color"])),
                    tickfont=dict(color=info["color"]),
                    overlaying="y",
                    side="right",
                    anchor="free" if i > 1 else "x",
                    position=position if i > 1 else None,
                    showgrid=False,
                )

        fig.update_layout(**layout_axes)

    title_bits = [
        f"{len(sel_pairs)} Paar(e)" if sel_pairs else "",
        f"{len(sel_oils)} Öl" if sel_oils else "",
        freq_label,
        agg_label,
        "normalisiert" if normalize else "",
    ]
    fig.update_layout(
        height=600,
        title=" · ".join(b for b in title_bits if b),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )

    st.plotly_chart(fig, use_container_width=True)

    # ----- Korrelations- und Datentabelle -----
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Pearson-Korrelation")
        if df_master.shape[1] >= 2:
            st.dataframe(df_master.corr().round(3), use_container_width=True)
        else:
            st.info("Mindestens 2 Reihen für eine Korrelation nötig.")
    with col2:
        st.subheader("Statistik")
        st.dataframe(df_master.describe().round(4), use_container_width=True)

    with st.expander("Aggregierte Daten anzeigen"):
        st.dataframe(df_master.round(6), use_container_width=True, height=400)
        st.download_button(
            "Als CSV herunterladen",
            df_master.to_csv().encode("utf-8"),
            file_name="master_grafik.csv",
            mime="text/csv",
        )

# ---------------------------------------------------------------------------
# Page: Master Grafik 2 — Proof of Concept: Webscraping-News + eigene Sentiment-Analyse
# ---------------------------------------------------------------------------
elif page == "Master Grafik 2":
    st.title("Master Grafik 2 — Proof of Concept")
    st.caption(
        "Gleiche Methodik wie Master Grafik 1, aber mit **Webscraping-News** (RSS + Reddit) "
        "und **eigener TextBlob-Sentiment-Analyse** statt EODHD. Forex/Oel bleiben identisch "
        "(Yahoo + EODHD kombiniert). Dient dem Vergleich, ob der Zusammenhang in Master Grafik 1 "
        "mit einer unabhaengigen Nachrichtenquelle reproduzierbar ist."
    )

    if webscraping_sent_daily.empty:
        st.warning(
            "Aggregiertes Webscraping-Sentiment fehlt. Bitte einmalig "
            "`python scripts/regenerate_webscraping_sentiment.py` ausfuehren — das erzeugt "
            "`data/processed/news/webscraping_sentiment_daily.csv`."
        )
        st.stop()

    # ----- Sidebar -----
    st.sidebar.markdown("---")
    st.sidebar.subheader("Master Grafik 2 Einstellungen")

    sel_pairs2 = st.sidebar.multiselect(
        "Währungspaare",
        PAIRS,
        default=["EUR_USD"],
        format_func=lambda x: PAIR_LABELS[x],
        key="mg2_pairs",
    )
    fx_source2 = st.sidebar.selectbox(
        "Forex-Quelle",
        ["mittelwert", "yahoo", "eodhd"],
        help="'mittelwert' = Mittelwert aus yahoo + eodhd (nur wo beide vorhanden)",
        key="mg2_fxsrc",
    )
    fx_field2 = st.sidebar.selectbox("Forex-Feld", ["close", "open", "high", "low"], key="mg2_field")

    sel_oils2 = st.sidebar.multiselect(
        "Ölpreise",
        OIL_TICKERS,
        default=[],
        format_func=lambda x: OIL_LABELS[x],
        key="mg2_oils",
    )

    show_sent2 = st.sidebar.checkbox(
        "Eigenes TextBlob-Sentiment (Webscraping) anzeigen",
        value=True,
        key="mg2_sent",
    )
    sent_metric2 = st.sidebar.selectbox(
        "Sentiment-Kennzahl",
        ["polarity_median", "polarity_mean"],
        help="Tagesmedian (robust) oder Tagesmittel.",
        disabled=not show_sent2,
        key="mg2_sentmetric",
    )

    # Quelle-Filter: arbeitet auf den Artikel-Level-Daten (deduppliziert)
    available_src = (
        sorted(webscraping_articles_sent["source"].dropna().unique().tolist())
        if not webscraping_articles_sent.empty else []
    )
    sel_src2 = st.sidebar.multiselect(
        "News-Quellen filtern (leer = alle)",
        available_src,
        default=[],
        disabled=not show_sent2 or webscraping_articles_sent.empty,
        help="Filtert Artikel pro Quelle (z.B. nur RSS ohne Reddit). Re-aggregiert Median on-the-fly.",
        key="mg2_src",
    )

    freq_label2 = st.sidebar.selectbox(
        "Aggregation (Auflösung)",
        ["Täglich", "Wöchentlich", "Monatlich", "Quartalsweise"],
        index=1,
        key="mg2_freq",
    )
    freq_map2 = {"Täglich": "D", "Wöchentlich": "W-MON", "Monatlich": "MS", "Quartalsweise": "QS"}
    freq2 = freq_map2[freq_label2]

    agg_label2 = st.sidebar.selectbox(
        "Aggregations-Funktion",
        ["Mittelwert", "Median", "Letzter Wert", "Min", "Max", "Summe"],
        key="mg2_agg",
    )
    agg_map2 = {"Mittelwert": "mean", "Median": "median", "Letzter Wert": "last", "Min": "min", "Max": "max", "Summe": "sum"}
    agg_func2 = agg_map2[agg_label2]

    fill_gaps2 = st.sidebar.checkbox(
        "Fehlende Tage interpolieren (linear, vor Aggregation)",
        value=False,
        key="mg2_fill",
    )
    normalize2 = st.sidebar.checkbox(
        "Normalisieren (Index = 100 am Startdatum)",
        value=False,
        key="mg2_norm",
    )

    # ----- Daten zusammenstellen -----
    def get_fx_series2(pair: str) -> pd.Series:
        sub = df_combined[df_combined["pair"] == pair]
        if fx_source2 == "mittelwert":
            yh = sub.get(f"yahoo_{fx_field2}")
            ed = sub.get(f"eodhd_{fx_field2}")
            if yh is None or ed is None:
                return pd.Series(dtype=float)
            return pd.concat([yh, ed], axis=1).mean(axis=1, skipna=False).dropna()
        col = f"{fx_source2}_{fx_field2}"
        if col not in sub.columns:
            return pd.Series(dtype=float)
        return sub[col].dropna()

    def get_webscrape_sentiment_series() -> pd.Series:
        """Liest das Tagesmedian-Sentiment; re-aggregiert wenn Quelle gefiltert wird."""
        if sel_src2 and not webscraping_articles_sent.empty:
            df = webscraping_articles_sent[webscraping_articles_sent["source"].isin(sel_src2)]
            df = df.dropna(subset=["date", "polarity_tb"])
            if df.empty:
                return pd.Series(dtype=float)
            df = df.copy()
            df["date_norm"] = df["date"].dt.tz_convert(None).dt.normalize()
            agg_fn = "median" if sent_metric2 == "polarity_median" else "mean"
            s = df.groupby("date_norm")["polarity_tb"].agg(agg_fn)
            s.index = pd.to_datetime(s.index)
            return s
        if webscraping_sent_daily.empty or sent_metric2 not in webscraping_sent_daily.columns:
            return pd.Series(dtype=float)
        return webscraping_sent_daily[sent_metric2].dropna()

    series_dict2: dict[str, pd.Series] = {}
    series_category2: dict[str, str] = {}
    for p in sel_pairs2:
        s = get_fx_series2(p)
        if not s.empty:
            label = f"{PAIR_LABELS[p]} {fx_field2} ({fx_source2})"
            series_dict2[label] = s
            series_category2[label] = "forex"
    for o in sel_oils2:
        df = oil_data.get(o)
        if df is not None and not df.empty:
            for c in ["close", "Close"]:
                if c in df.columns:
                    label = f"{OIL_LABELS[o]} close"
                    series_dict2[label] = df[c].dropna()
                    series_category2[label] = "oil"
                    break
    if show_sent2:
        s = get_webscrape_sentiment_series()
        if not s.empty:
            src_info = f"{len(sel_src2)} Quellen" if sel_src2 else f"alle {len(available_src)} Quellen"
            label = f"Sentiment TextBlob ({sent_metric2.replace('polarity_', '')}, {src_info})"
            series_dict2[label] = s
            series_category2[label] = "sentiment"

    if not series_dict2:
        st.warning("Keine Reihen verfügbar – bitte mindestens ein Paar, Öl oder Sentiment aktivieren.")
        st.stop()

    df_master2 = pd.concat(series_dict2, axis=1).sort_index()
    df_master2.index = pd.to_datetime(df_master2.index)

    # Zeitraum-Auswahl über tatsächliche Daten
    min_d = df_master2.index.min().date()
    max_d = df_master2.index.max().date()
    date_range2 = st.sidebar.date_input(
        "Zeitraum",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
        key="mg2_date",
    )
    if isinstance(date_range2, tuple) and len(date_range2) == 2:
        start, end = pd.to_datetime(date_range2[0]), pd.to_datetime(date_range2[1])
        df_master2 = df_master2.loc[(df_master2.index >= start) & (df_master2.index <= end)]

    if df_master2.empty:
        st.warning("Keine Daten im gewählten Zeitraum.")
        st.stop()

    # Überlapp-Hinweis: Sentiment-Abdeckung ist durch Scrape-Reichweite begrenzt
    fx_cols = [c for c, cat in series_category2.items() if cat == "forex"]
    sn_cols = [c for c, cat in series_category2.items() if cat == "sentiment"]
    if fx_cols and sn_cols:
        overlap = df_master2[fx_cols + sn_cols].dropna(how="any")
        if overlap.empty:
            st.info(
                "Forex und Webscraping-Sentiment haben im gewaehlten Zeitraum keine gemeinsamen Tage — "
                "Korrelation ist nicht berechenbar. Zeitraum anpassen oder Woche/Monat als Aggregation waehlen."
            )
        else:
            st.caption(f"Gemeinsame Tage Forex ↔ Sentiment: **{len(overlap)}**")

    if fill_gaps2:
        full_idx = pd.date_range(df_master2.index.min(), df_master2.index.max(), freq="D")
        df_master2 = df_master2.reindex(full_idx).interpolate(method="time")
        df_master2.index.name = "date"

    if freq2 != "D":
        df_master2 = df_master2.resample(freq2).agg(agg_func2)

    if normalize2:
        first_valid = df_master2.apply(lambda c: c.dropna().iloc[0] if c.dropna().size else np.nan)
        df_master2 = df_master2.divide(first_valid).multiply(100)

    # ----- Plot mit separaten Y-Achsen pro Kategorie -----
    CATEGORY_INFO2 = {
        "forex":     {"title": f"Forex-Kurs ({fx_field2})",        "color": "#1f77b4", "dash": "solid"},
        "oil":       {"title": "Öl (USD)",                          "color": "#2ca02c", "dash": "solid"},
        "sentiment": {"title": "TextBlob-Polarity (Webscraping)",   "color": "#d62728", "dash": "dot"},
    }

    fig2 = go.Figure()
    if normalize2:
        for col in df_master2.columns:
            cat = series_category2.get(col, "forex")
            fig2.add_trace(go.Scatter(
                x=df_master2.index, y=df_master2[col], name=col, mode="lines",
                line=dict(dash=CATEGORY_INFO2[cat]["dash"]),
            ))
        fig2.update_layout(yaxis=dict(title="Index (Start = 100)"))
    else:
        cats_present = [c for c in ["forex", "oil", "sentiment"] if c in series_category2.values()]
        cat_to_axis = {cat: f"y{i+1}" if i > 0 else "y" for i, cat in enumerate(cats_present)}
        for col in df_master2.columns:
            cat = series_category2.get(col, "forex")
            info = CATEGORY_INFO2[cat]
            fig2.add_trace(go.Scatter(
                x=df_master2.index, y=df_master2[col], name=col, mode="lines",
                yaxis=cat_to_axis[cat],
                line=dict(dash=info["dash"]),
            ))
        layout_axes: dict = {}
        n_extra = max(0, len(cats_present) - 1)
        right_padding = 0.06 * n_extra
        layout_axes["xaxis"] = dict(domain=[0.0, max(0.7, 1.0 - right_padding)])
        for i, cat in enumerate(cats_present):
            info = CATEGORY_INFO2[cat]
            if i == 0:
                layout_axes["yaxis"] = dict(
                    title=dict(text=info["title"], font=dict(color=info["color"])),
                    tickfont=dict(color=info["color"]),
                )
            else:
                position = 1.0 - 0.06 * (i - 1)
                layout_axes[f"yaxis{i+1}"] = dict(
                    title=dict(text=info["title"], font=dict(color=info["color"])),
                    tickfont=dict(color=info["color"]),
                    overlaying="y",
                    side="right",
                    anchor="free" if i > 1 else "x",
                    position=position if i > 1 else None,
                    showgrid=False,
                )
        fig2.update_layout(**layout_axes)

    title_bits2 = [
        f"{len(sel_pairs2)} Paar(e)" if sel_pairs2 else "",
        f"{len(sel_oils2)} Öl" if sel_oils2 else "",
        "TextBlob-Sentiment" if show_sent2 else "",
        freq_label2,
        agg_label2,
        "normalisiert" if normalize2 else "",
    ]
    fig2.update_layout(
        height=600,
        title=" · ".join(b for b in title_bits2 if b),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig2, use_container_width=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Pearson-Korrelation")
        if df_master2.shape[1] >= 2 and df_master2.dropna(how="any").shape[0] >= 2:
            st.dataframe(df_master2.corr().round(3), use_container_width=True)
        else:
            st.info("Zu wenige gemeinsame Beobachtungen für eine Korrelation.")
    with col2:
        st.subheader("Statistik")
        st.dataframe(df_master2.describe().round(4), use_container_width=True)

    with st.expander("Aggregierte Daten anzeigen"):
        st.dataframe(df_master2.round(6), use_container_width=True, height=400)
        st.download_button(
            "Als CSV herunterladen",
            df_master2.to_csv().encode("utf-8"),
            file_name="master_grafik_2.csv",
            mime="text/csv",
            key="mg2_dl",
        )
