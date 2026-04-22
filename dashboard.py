"""
Forex & News Sentiment Dashboard
FHNW - Data Engineering & Wrangling
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- Seiten-Konfiguration ---
st.set_page_config(
    page_title="Forex & News Sentiment",
    page_icon="📈",
    layout="wide"
)

# --- Daten laden ---
@st.cache_data
def load_data():
    df = pd.read_csv('data/final/forex_news_merged.csv')
    df['date'] = pd.to_datetime(df['date'])
    return df

df = load_data()

# --- Titel ---
st.title("📈 Forex & News Sentiment Dashboard")
st.markdown("**Frage:** Wenn die Nachrichten negativ sind — fällt der Kurs am nächsten Tag?")
st.divider()

# --- Sidebar: Filter ---
st.sidebar.header("🔧 Filter")

pair = st.sidebar.selectbox(
    "Währungspaar",
    options=['EUR_USD', 'EUR_CHF', 'GBP_USD'],
    index=0
)

date_min = df['date'].min().date()
date_max = df['date'].max().date()
date_range = st.sidebar.date_input(
    "Zeitraum",
    value=[date_min, date_max],
    min_value=date_min,
    max_value=date_max
)

# --- Daten filtern ---
df_filtered = df[df['pair'] == pair].copy()
if len(date_range) == 2:
    df_filtered = df_filtered[
        (df_filtered['date'].dt.date >= date_range[0]) &
        (df_filtered['date'].dt.date <= date_range[1])
    ]

df_news = df_filtered.dropna(subset=['polarity_mean'])

# --- Kennzahlen oben ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Handelstage", f"{len(df_filtered)}")
with col2:
    st.metric("Tage mit News", f"{len(df_news)}")
with col3:
    avg_sentiment = df_news['polarity_mean'].mean()
    st.metric("Ø Sentiment", f"{avg_sentiment:+.3f}", delta="positiv" if avg_sentiment > 0 else "negativ")
with col4:
    corr = df_news['polarity_mean'].corr(df_news['close_change_next_day'])
    st.metric("Korrelation (Sentiment → nächster Tag)", f"{corr:+.4f}")

st.divider()

# --- Grafik 1: Kursverlauf + Sentiment ---
st.subheader(f"📊 Kursverlauf & News-Sentiment — {pair.replace('_', '/')}")

fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    row_heights=[0.6, 0.4],
    subplot_titles=["Schlusskurs (close)", "News-Sentiment (polarity)"],
    vertical_spacing=0.08
)

# Kursverlauf
fig.add_trace(
    go.Scatter(x=df_filtered['date'], y=df_filtered['close'],
               mode='lines', name='Kurs',
               line=dict(color='steelblue', width=1.5)),
    row=1, col=1
)

# Sentiment als Balken (grün = positiv, rot = negativ)
colors = ['green' if x > 0 else 'red' for x in df_news['polarity_mean']]
fig.add_trace(
    go.Bar(x=df_news['date'], y=df_news['polarity_mean'],
           name='Sentiment', marker_color=colors, opacity=0.6),
    row=2, col=1
)

fig.update_layout(height=550, showlegend=False)
fig.update_yaxes(title_text="Kurs", row=1, col=1)
fig.update_yaxes(title_text="Polarity", row=2, col=1)
st.plotly_chart(fig, use_container_width=True)

# --- Grafik 2 & 3 nebeneinander ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🔍 Sentiment → Kurs nächster Tag")
    df_scatter = df_news.dropna(subset=['close_change_next_day'])
    fig2 = px.scatter(
        df_scatter,
        x='polarity_mean',
        y='close_change_next_day',
        trendline='ols',
        labels={
            'polarity_mean': 'Sentiment heute',
            'close_change_next_day': 'Kursveränderung morgen (%)'
        },
        title=f"Korrelation: {corr:+.4f}",
        color_discrete_sequence=['orange']
    )
    fig2.add_hline(y=0, line_dash="dash", line_color="black", opacity=0.4)
    fig2.add_vline(x=0, line_dash="dash", line_color="black", opacity=0.4)
    st.plotly_chart(fig2, use_container_width=True)

with col_right:
    st.subheader("📰 Artikel pro Tag")
    fig3 = px.bar(
        df_news,
        x='date',
        y='article_count',
        labels={'date': 'Datum', 'article_count': 'Anzahl Artikel'},
        color='article_count',
        color_continuous_scale='Blues'
    )
    fig3.update_coloraxes(showscale=False)
    st.plotly_chart(fig3, use_container_width=True)

# --- Vergleich aller Paare ---
st.divider()
st.subheader("🌍 Vergleich aller Währungspaare")

corr_data = []
for p in ['EUR_USD', 'EUR_CHF', 'GBP_USD']:
    df_p = df[df['pair'] == p].dropna(subset=['polarity_mean', 'close_change_next_day'])
    corr_val = df_p['polarity_mean'].corr(df_p['close_change_next_day'])
    corr_data.append({'Währungspaar': p.replace('_', '/'), 'Korrelation': round(corr_val, 4)})

df_corr = pd.DataFrame(corr_data)

col_a, col_b = st.columns([1, 2])
with col_a:
    st.dataframe(df_corr, hide_index=True, use_container_width=True)

with col_b:
    colors_bar = ['green' if x > 0 else 'red' for x in df_corr['Korrelation']]
    fig4 = go.Figure(go.Bar(
        x=df_corr['Währungspaar'],
        y=df_corr['Korrelation'],
        marker_color=colors_bar,
        text=df_corr['Korrelation'],
        textposition='outside'
    ))
    fig4.add_hline(y=0, line_color='black', opacity=0.4)
    fig4.update_layout(
        title="Korrelation: Sentiment heute → Kurs morgen",
        yaxis_title="Pearson Korrelation",
        height=350
    )
    st.plotly_chart(fig4, use_container_width=True)

# --- Rohdaten Tabelle ---
st.divider()
st.subheader("📋 Rohdaten")
st.dataframe(
    df_filtered[['date', 'pair', 'close', 'article_count', 'polarity_mean', 'close_change', 'close_change_next_day']].sort_values('date', ascending=False),
    hide_index=True,
    use_container_width=True
)
