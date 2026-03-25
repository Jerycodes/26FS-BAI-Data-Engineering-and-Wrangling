"""
Forex & News Daten-Dashboard
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
    """Lade alle Rohdaten fuer detaillierten Vergleich."""
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
def load_news_eodhd():
    dfs = {}
    for pair in PAIRS:
        files = sorted(glob.glob(os.path.join(DATA_DIR, "raw", "news", "eodhd", f"{pair}_news_*.csv")))
        if files:
            df = pd.read_csv(files[-1])
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["date_only"] = pd.to_datetime(df["date_only"], errors="coerce")
            dfs[pair] = df
    return dfs


@st.cache_data
def load_news_webscraping():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "raw", "news", "webscraping", "all_scraped_news_*.csv")))
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
    return df


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df_combined = load_combined_forex()
raw_data = load_raw_sources()
news_eodhd = load_news_eodhd()
news_scraping = load_news_webscraping()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("📈 Forex Dashboard")

page = st.sidebar.radio("Navigation", [
    "Uebersicht",
    "Quellenvergleich",
    "Lueckenanalyse",
    "Preisabweichungen",
    "Nachrichten",
    "Eigene Grafik",
])

# ---------------------------------------------------------------------------
# Page: Uebersicht
# ---------------------------------------------------------------------------
if page == "Uebersicht":
    st.title("Forex-Daten Uebersicht")

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Waehrungspaare", len(PAIRS))
    col2.metric("Datenquellen", "3 (Yahoo, EODHD, MT5)")
    col3.metric("Total Datenpunkte", f"{len(df_combined):,}")

    n_gaps = df_combined["has_gap"].sum()
    col4.metric("Tage mit Luecken", n_gaps)

    st.markdown("---")

    # Uebersicht pro Paar
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

# ---------------------------------------------------------------------------
# Page: Quellenvergleich
# ---------------------------------------------------------------------------
elif page == "Quellenvergleich":
    st.title("Quellenvergleich")

    pair = st.selectbox("Waehrungspaar", PAIRS, format_func=lambda x: PAIR_LABELS[x])
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

    # Statistiken
    st.subheader("Deskriptive Statistik")
    stats_cols = [f"{s}_{col_type}" for s in sources]
    stats_df = pair_data[stats_cols].describe().T
    stats_df.index = [s.replace(f"_{col_type}", "").capitalize() for s in stats_df.index]
    st.dataframe(stats_df.round(6), use_container_width=True)

# ---------------------------------------------------------------------------
# Page: Lueckenanalyse
# ---------------------------------------------------------------------------
elif page == "Lueckenanalyse":
    st.title("Lueckenanalyse - Fehlende Daten")

    pair = st.selectbox("Waehrungspaar", PAIRS, format_func=lambda x: PAIR_LABELS[x])
    pair_data = df_combined[df_combined["pair"] == pair]

    sources = [s for s in ["yahoo", "eodhd", "metatrader"] if f"{s}_close" in pair_data.columns and pair_data[f"{s}_close"].notna().any()]

    only_weekdays = st.checkbox("Nur Wochentage anzeigen", value=True)
    if only_weekdays:
        pair_data = pair_data[~pair_data["is_weekend"]]

    # Heatmap: Datenverfuegbarkeit pro Monat
    st.subheader("Monatliche Datenverfuegbarkeit")
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

    # Tage mit Luecken
    st.subheader("Tage mit fehlenden Daten")
    gaps = pair_data[pair_data["has_gap"]]
    if len(gaps) == 0:
        st.success("Keine Luecken gefunden!")
    else:
        st.warning(f"{len(gaps)} Tage mit Luecken")
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

    pair = st.selectbox("Waehrungspaar", PAIRS, format_func=lambda x: PAIR_LABELS[x])
    pair_data = df_combined[df_combined["pair"] == pair]
    pair_data = pair_data[~pair_data["is_weekend"]]

    sources = [s for s in ["yahoo", "eodhd", "metatrader"] if f"{s}_close" in pair_data.columns and pair_data[f"{s}_close"].notna().any()]

    if len(sources) < 2:
        st.warning("Mindestens 2 Quellen noetig fuer Vergleich")
    else:
        col_type = st.selectbox("Preis-Typ", ["close", "open", "high", "low"])

        # Spread (Max - Min) ueber alle Quellen
        st.subheader("Taeglicher Spread (Max - Min aller Quellen)")
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
        st.subheader("Top-10 groesste Abweichungen")
        top = diff.abs().nlargest(10)
        top_df = pd.DataFrame({
            "Datum": top.index.strftime("%Y-%m-%d"),
            "Differenz": diff.loc[top.index].values,
            f"{src_a} {col_type}": pair_data.loc[top.index, f"{src_a}_{col_type}"].values,
            f"{src_b} {col_type}": pair_data.loc[top.index, f"{src_b}_{col_type}"].values,
        })
        st.dataframe(top_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Page: Nachrichten
# ---------------------------------------------------------------------------
elif page == "Nachrichten":
    st.title("Nachrichten-Daten")

    tab1, tab2 = st.tabs(["EODHD News", "Webscraping News"])

    with tab1:
        if news_eodhd:
            pair = st.selectbox("Waehrungspaar", list(news_eodhd.keys()), format_func=lambda x: PAIR_LABELS.get(x, x))
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
            col1.metric("Total Eintraege", len(news_scraping))
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
# Page: Eigene Grafik
# ---------------------------------------------------------------------------
elif page == "Eigene Grafik":
    st.title("Eigene Grafik erstellen")

    pair = st.selectbox("Waehrungspaar", PAIRS, format_func=lambda x: PAIR_LABELS[x])
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

    elif chart_type == "Renditen":
        col_type = st.selectbox("Preis-Typ", ["close", "open"], key="ret_col")
        fig = go.Figure()
        for source in selected_sources:
            returns = pair_data[f"{source}_{col_type}"].pct_change().dropna()
            fig.add_trace(go.Scatter(x=returns.index, y=returns, name=source.capitalize(), mode="lines",
                                     line=dict(width=0.8)))
        fig.add_hline(y=0, line_dash="dash", line_color="red", opacity=0.3)
        fig.update_layout(height=500, title=f"{PAIR_LABELS[pair]} - Taegliche Renditen", yaxis_title="Rendite",
                          hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

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
        else:
            st.info("Mindestens 2 Quellen auswaehlen.")

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
