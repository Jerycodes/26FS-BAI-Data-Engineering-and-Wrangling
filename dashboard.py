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
oil_data = load_oil_data()
news_eodhd = load_news_eodhd()
news_scraping = load_news_webscraping()

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
    "Eigene Grafik",
    "Master Grafik",
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

    # Spalten in einem DataFrame sammeln
    series_dict: dict[str, pd.Series] = {}
    for p in sel_pairs:
        s = get_fx_series(p)
        if not s.empty:
            series_dict[f"{PAIR_LABELS[p]} {fx_field} ({fx_source})"] = s
    for o in sel_oils:
        s = get_oil_series(o)
        if not s.empty:
            series_dict[f"{OIL_LABELS[o]} close"] = s
    if show_sentiment and sel_pairs:
        if sentiment_per_pair:
            for p in sel_pairs:
                s = get_sentiment_series(p)
                if not s.empty:
                    series_dict[f"Sentiment {PAIR_LABELS[p]}"] = s
        else:
            parts = [get_sentiment_series(p) for p in sel_pairs]
            parts = [p for p in parts if not p.empty]
            if parts:
                merged = pd.concat(parts, axis=1).mean(axis=1)
                series_dict[f"Sentiment Mittel ({len(parts)} Paare)"] = merged

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

    # ----- Plot -----
    # Sentiment-Spalten auf eigene Sekundärachse, alles andere auf Hauptachse.
    # Bei Normalisierung landet alles auf einer Achse.
    sentiment_cols = [c for c in df_master.columns if c.startswith("Sentiment")]
    other_cols     = [c for c in df_master.columns if c not in sentiment_cols]

    use_secondary = bool(sentiment_cols) and not normalize
    fig = make_subplots(specs=[[{"secondary_y": use_secondary}]])

    for col in other_cols:
        fig.add_trace(
            go.Scatter(x=df_master.index, y=df_master[col], name=col, mode="lines"),
            secondary_y=False,
        )
    for col in sentiment_cols:
        fig.add_trace(
            go.Scatter(x=df_master.index, y=df_master[col], name=col, mode="lines",
                       line=dict(dash="dot")),
            secondary_y=use_secondary,
        )

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
    fig.update_yaxes(title_text="Index (Start = 100)" if normalize else "Wert", secondary_y=False)
    if use_secondary:
        fig.update_yaxes(title_text="Sentiment (polarity)", secondary_y=True)

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
