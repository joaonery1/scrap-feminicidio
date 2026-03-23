"""
dashboard/app.py

Monitor de Feminicídio em Sergipe — dados ao vivo (scrapers) + histórico (Anuário FBSP).
"""

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st
from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")

BAIRRO_COORDS = {
    "Atalaia": (-11.030, -37.055),
    "Centro": (-10.916, -37.053),
    "Coroa do Meio": (-11.010, -37.040),
    "Farolândia": (-10.970, -37.055),
    "Jardins": (-10.960, -37.060),
    "São Conrado": (-10.950, -37.070),
    "Luzia": (-10.930, -37.060),
    "Grageru": (-10.940, -37.065),
    "Industrial": (-10.910, -37.060),
    "Jabotiana": (-10.970, -37.080),
    "13 de Julho": (-10.925, -37.058),
    "Siqueira Campos": (-10.920, -37.055),
}

# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        dbname=os.getenv("POSTGRES_DB", "scrapshe"),
        user=os.getenv("POSTGRES_USER", "scrapshe"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme"),
    )


@st.cache_data(ttl=3600)
def load_casos() -> pd.DataFrame:
    try:
        conn = _get_connection()
        df = pd.read_sql_query(
            "SELECT id, published_at, source, title, bairro, url FROM casos ORDER BY published_at DESC",
            conn,
        )
        conn.close()
    except Exception as exc:
        st.error(f"Erro ao conectar ao banco de dados: {exc}")
        return pd.DataFrame()
    if not df.empty:
        df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    return df


@st.cache_data
def load_anuario() -> dict:
    path = _root / "pipeline" / "anuario_sergipe.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Feminicídio em Sergipe — Monitor",
    page_icon="🔴",
    layout="wide",
)

st.title("🔴 Feminicídio em Sergipe — Monitor de Casos")

df_all = load_casos()
anuario = load_anuario()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Filtros")

import datetime
if not df_all.empty and df_all["published_at"].notna().any():
    min_date = df_all["published_at"].min().date()
    max_date = df_all["published_at"].max().date()
else:
    min_date = datetime.date(2026, 3, 1)
    max_date = datetime.date.today()

data_inicio = st.sidebar.date_input("Data início", value=min_date)
data_fim    = st.sidebar.date_input("Data fim",    value=max_date)

fontes_disp  = sorted(df_all["source"].dropna().unique()) if not df_all.empty else []
bairros_disp = sorted(df_all["bairro"].dropna().unique()) if not df_all.empty else []
fonte_sel  = st.sidebar.multiselect("Fonte",  fontes_disp,  default=[])
bairro_sel = st.sidebar.multiselect("Bairro", bairros_disp, default=[])

st.sidebar.markdown("---")
st.sidebar.caption("Fontes: SSP-SE, G1 Sergipe  \nDados históricos: Anuário FBSP 2025")

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------
df = df_all.copy()
if not df.empty:
    df = df[
        (df["published_at"].dt.date >= data_inicio) &
        (df["published_at"].dt.date <= data_fim)
    ]
if bairro_sel:
    df = df[df["bairro"].isin(bairro_sel)]
if fonte_sel:
    df = df[df["source"].isin(fonte_sel)]

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)

k1.metric("Casos coletados (total)", len(df_all))
k2.metric("Casos no período filtrado", len(df))

feminicidios_2024 = anuario.get("feminicidios_por_ano", {}).get("2024", "—")
feminicidios_2023 = anuario.get("feminicidios_por_ano", {}).get("2023", "—")
delta = None
if isinstance(feminicidios_2024, int) and isinstance(feminicidios_2023, int):
    delta = feminicidios_2024 - feminicidios_2023

k3.metric("Feminicídios SE — 2024", feminicidios_2024,
          delta=f"{delta:+d} vs 2023" if delta is not None else None,
          delta_color="inverse")
k4.metric("Tentativas SE — 2024",
          anuario.get("tentativas_feminicidio", {}).get("2024", "—"))

st.markdown("---")

# ---------------------------------------------------------------------------
# Seção 1 — Histórico anual (Anuário FBSP)
# ---------------------------------------------------------------------------
st.subheader("📊 Histórico anual — Sergipe (Anuário FBSP 2025)")

serie = anuario.get("serie_historica_proporcao_feminicidio_pct", {})
fem_ano = anuario.get("feminicidios_por_ano", {})
tent_ano = anuario.get("tentativas_feminicidio", {})

col_hist, col_tent = st.columns(2)

with col_hist:
    anos_conf = sorted([a for a in fem_ano if fem_ano[a] is not None])
    if anos_conf:
        df_conf = pd.DataFrame({
            "Ano": [int(a) for a in anos_conf],
            "Feminicídios": [fem_ano[a] for a in anos_conf],
        })
        fig_conf = px.bar(
            df_conf, x="Ano", y="Feminicídios",
            text="Feminicídios",
            color="Feminicídios",
            color_continuous_scale="Reds",
            title="Feminicídios confirmados por ano (SE)",
        )
        fig_conf.update_traces(textposition="outside")
        fig_conf.update_layout(coloraxis_showscale=False, showlegend=False)
        st.plotly_chart(fig_conf, use_container_width=True)

with col_tent:
    anos_tent = sorted([a for a in tent_ano if tent_ano[a] is not None])
    if anos_tent:
        df_tent = pd.DataFrame({
            "Ano": [int(a) for a in anos_tent],
            "Tentativas": [tent_ano[a] for a in anos_tent],
        })
        fig_tent = px.bar(
            df_tent, x="Ano", y="Tentativas",
            text="Tentativas",
            color="Tentativas",
            color_continuous_scale="Oranges",
            title="Tentativas de feminicídio por ano (SE)",
        )
        fig_tent.update_traces(textposition="outside")
        fig_tent.update_layout(coloraxis_showscale=False, showlegend=False)
        st.plotly_chart(fig_tent, use_container_width=True)

# Proporção histórica
if serie:
    anos_s = sorted([a for a in serie if isinstance(serie[a], (int, float))])
    if anos_s:
        df_serie = pd.DataFrame({
            "Ano": [int(a) for a in anos_s],
            "% feminicídios/homicídios mulheres": [serie[a] for a in anos_s],
        })
        fig_serie = px.line(
            df_serie, x="Ano", y="% feminicídios/homicídios mulheres",
            markers=True,
            title="Proporção de feminicídios em relação a homicídios de mulheres — SE (%)",
        )
        fig_serie.add_hline(
            y=df_serie["% feminicídios/homicídios mulheres"].mean(),
            line_dash="dot", line_color="gray",
            annotation_text="média", annotation_position="bottom right",
        )
        st.plotly_chart(fig_serie, use_container_width=True)

st.caption(f"Fonte: {anuario.get('fonte', 'Anuário FBSP 2025')}")
st.markdown("---")

# ---------------------------------------------------------------------------
# Seção 2 — Dados ao vivo (banco de dados)
# ---------------------------------------------------------------------------
st.subheader("📰 Casos coletados — Março 2026 (scrapers SSP-SE + G1)")

if df.empty:
    st.info("Nenhum caso encontrado com os filtros selecionados.")
    st.stop()

col_ts, col_fonte = st.columns([2, 1])

with col_ts:
    df_ts = df.copy()
    df_ts["mes"] = df_ts["published_at"].dt.to_period("M").dt.to_timestamp()
    ts = df_ts.groupby("mes").size().reset_index(name="casos")
    fig_ts = px.bar(ts, x="mes", y="casos", text="casos",
                    labels={"mes": "Mês", "casos": "Registros"},
                    title="Registros coletados por mês")
    fig_ts.update_traces(textposition="outside", marker_color="#c0392b")
    st.plotly_chart(fig_ts, use_container_width=True)

with col_fonte:
    por_fonte = df.groupby("source").size().reset_index(name="total")
    fig_fonte = px.pie(por_fonte, names="source", values="total",
                       title="Por fonte", hole=0.4,
                       color_discrete_sequence=["#c0392b", "#e74c3c", "#f1948a"])
    st.plotly_chart(fig_fonte, use_container_width=True)

# ---------------------------------------------------------------------------
# Mapa
# ---------------------------------------------------------------------------
df_bairro = df[df["bairro"].notna()].copy()
if not df_bairro.empty:
    st.subheader("🗺️ Distribuição por bairro")
    bc = df_bairro["bairro"].value_counts().reset_index()
    bc.columns = ["bairro", "total"]
    bc["lat"] = bc["bairro"].map(lambda b: BAIRRO_COORDS.get(b, (None, None))[0])
    bc["lon"] = bc["bairro"].map(lambda b: BAIRRO_COORDS.get(b, (None, None))[1])
    bc = bc.dropna(subset=["lat", "lon"])
    if not bc.empty:
        fig_map = px.scatter_mapbox(
            bc, lat="lat", lon="lon", size="total", color="total",
            hover_name="bairro", color_continuous_scale="Reds",
            size_max=30, zoom=12,
            center={"lat": -10.950, "lon": -37.060},
            mapbox_style="open-street-map",
            title="Casos por bairro",
        )
        st.plotly_chart(fig_map, use_container_width=True)

# ---------------------------------------------------------------------------
# Tabela
# ---------------------------------------------------------------------------
st.subheader("📋 Registros")
cols = ["published_at", "source", "title", "bairro", "url"]
st.dataframe(
    df[[c for c in cols if c in df.columns]].reset_index(drop=True),
    use_container_width=True,
)
