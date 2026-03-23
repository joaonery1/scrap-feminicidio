"""
dashboard/app.py

Streamlit dashboard for Feminicídio em Aracaju/SE monitor.
"""

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------------------
# Neighborhood coordinates (approximate)
# ---------------------------------------------------------------------------
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
# Database helpers
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
def load_data() -> pd.DataFrame:
    """Load all casos from PostgreSQL."""
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


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Feminicídio em Aracaju/SE — Monitor de Casos",
    layout="wide",
)

st.title("Feminicídio em Aracaju/SE — Monitor de Casos")

df_all = load_data()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.header("Filtros")

if not df_all.empty and df_all["published_at"].notna().any():
    min_date = df_all["published_at"].min().date()
    max_date = df_all["published_at"].max().date()
else:
    import datetime
    min_date = datetime.date(2020, 1, 1)
    max_date = datetime.date.today()

data_inicio = st.sidebar.date_input("Data início", value=min_date)
data_fim = st.sidebar.date_input("Data fim", value=max_date)

bairros_disponiveis = sorted(df_all["bairro"].dropna().unique().tolist()) if not df_all.empty else []
bairro_sel = st.sidebar.multiselect("Bairro", options=bairros_disponiveis, default=[])

fontes_disponiveis = sorted(df_all["source"].dropna().unique().tolist()) if not df_all.empty else []
fonte_sel = st.sidebar.multiselect("Fonte", options=fontes_disponiveis, default=[])

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------
df = df_all.copy()

if not df.empty:
    mask = (
        (df["published_at"].dt.date >= data_inicio)
        & (df["published_at"].dt.date <= data_fim)
    )
    df = df[mask]

if bairro_sel:
    df = df[df["bairro"].isin(bairro_sel)]

if fonte_sel:
    df = df[df["source"].isin(fonte_sel)]

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

total_geral = len(df_all)
total_filtrado = len(df)

if not df_all.empty and df_all["bairro"].notna().any():
    bairro_top = df_all["bairro"].value_counts().idxmax()
else:
    bairro_top = "N/A"

col1.metric("Total de casos", total_geral)
col2.metric("Casos no período filtrado", total_filtrado)
col3.metric("Bairro com mais casos", bairro_top)

# ---------------------------------------------------------------------------
# Guard: no data after filters
# ---------------------------------------------------------------------------
if df.empty:
    st.info("Nenhum caso encontrado com os filtros selecionados.")
    st.stop()

# ---------------------------------------------------------------------------
# Time series chart
# ---------------------------------------------------------------------------
st.subheader("Casos por mês")

df_ts = df.copy()
df_ts["mes"] = df_ts["published_at"].dt.to_period("M").dt.to_timestamp()
ts_data = df_ts.groupby("mes").size().reset_index(name="casos")

fig_ts = px.line(
    ts_data,
    x="mes",
    y="casos",
    markers=True,
    labels={"mes": "Mês", "casos": "Número de casos"},
    title="Série temporal de casos/mês",
)
st.plotly_chart(fig_ts, use_container_width=True)

# ---------------------------------------------------------------------------
# Map: heat by neighborhood
# ---------------------------------------------------------------------------
st.subheader("Mapa de calor por bairro")

df_bairro = df[df["bairro"].notna()].copy()
bairro_counts = df_bairro["bairro"].value_counts().reset_index()
bairro_counts.columns = ["bairro", "total"]

# Add coordinates
bairro_counts["lat"] = bairro_counts["bairro"].map(lambda b: BAIRRO_COORDS.get(b, (None, None))[0])
bairro_counts["lon"] = bairro_counts["bairro"].map(lambda b: BAIRRO_COORDS.get(b, (None, None))[1])
bairro_counts = bairro_counts.dropna(subset=["lat", "lon"])

if not bairro_counts.empty:
    mapbox_token = os.getenv("MAPBOX_TOKEN", "")
    if mapbox_token:
        px.set_mapbox_access_token(mapbox_token)
        map_style = "mapbox://styles/mapbox/light-v10"
    else:
        map_style = "open-street-map"

    fig_map = px.scatter_mapbox(
        bairro_counts,
        lat="lat",
        lon="lon",
        size="total",
        color="total",
        hover_name="bairro",
        hover_data={"total": True, "lat": False, "lon": False},
        color_continuous_scale="Reds",
        size_max=30,
        zoom=12,
        center={"lat": -10.950, "lon": -37.060},
        mapbox_style=map_style,
        title="Distribuição de casos por bairro",
        labels={"total": "Casos"},
    )
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.info("Sem dados de bairro disponíveis para exibir no mapa.")

# ---------------------------------------------------------------------------
# Data table
# ---------------------------------------------------------------------------
st.subheader("Registros")

display_cols = ["published_at", "source", "title", "bairro", "url"]
available_cols = [c for c in display_cols if c in df.columns]

st.dataframe(
    df[available_cols].reset_index(drop=True),
    use_container_width=True,
)
