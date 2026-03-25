"""
dashboard/app.py

Monitor de Feminicídio em Sergipe — foco em 2026 + histórico (Anuário FBSP).
"""

import datetime
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st
from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")

MUNICIPIO_COORDS = {
    "Aracaju": (-10.9167, -37.0500),
    "Nossa Senhora do Socorro": (-10.8553, -37.1231),
    "Lagarto": (-10.9167, -37.6667),
    "Itabaiana": (-10.6844, -37.4253),
    "São Cristóvão": (-11.0147, -37.2047),
    "Estância": (-11.2667, -37.4500),
    "Tobias Barreto": (-11.1833, -37.9997),
    "Laranjeiras": (-10.8000, -37.1667),
    "Barra dos Coqueiros": (-10.9075, -37.0336),
    "Carmópolis": (-10.6467, -36.9906),
    "Maruim": (-10.7333, -37.0833),
    "Nossa Senhora das Dores": (-10.4933, -37.1969),
    "Propriá": (-10.2167, -36.8333),
    "Simão Dias": (-10.7333, -37.8167),
    "Neópolis": (-10.3167, -36.5833),
    "Canindé de São Francisco": (-9.6439, -37.7961),
    "Poço Redondo": (-9.8000, -37.6833),
    "Nossa Senhora da Glória": (-10.2167, -37.4167),
    "Aquidabã": (-10.2792, -37.0239),
    "Cristinápolis": (-11.4833, -37.7500),
    "Umbaúba": (-11.3667, -37.6667),
    "Indiaroba": (-11.5167, -37.5000),
    "Japaratuba": (-10.5833, -36.9500),
    "Capela": (-10.5000, -37.0500),
    "Itabaianinha": (-11.2667, -37.7833),
    "Boquim": (-11.1500, -37.6167),
    "Lagarto": (-10.9167, -37.6667),
    "Frei Paulo": (-10.5500, -37.5333),
    "Carira": (-10.3500, -37.7000),
}

# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _cfg(key: str, default: str) -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key) or default


def _get_connection():
    return psycopg2.connect(
        host=_cfg("POSTGRES_HOST", "localhost"),
        port=int(_cfg("POSTGRES_PORT", "5432")),
        dbname=_cfg("POSTGRES_DB", "postgres"),
        user=_cfg("POSTGRES_USER", "postgres"),
        password=_cfg("POSTGRES_PASSWORD", "changeme"),
        sslmode="require",
    )


@st.cache_data(ttl=300)
def load_casos() -> pd.DataFrame:
    try:
        conn = _get_connection()
        df = pd.read_sql_query(
            "SELECT id, published_at, source, title, bairro, url, tipo, relacao FROM casos ORDER BY published_at DESC",
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
    page_title="Feminicídio em Sergipe — Monitor 2026",
    page_icon="🔴",
    layout="wide",
)

st.title("🔴 Feminicídio em Sergipe — Monitor 2026")

df_all = load_casos()
anuario = load_anuario()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Filtros")

# Default: 2026
default_inicio = datetime.date(2026, 1, 1)
default_fim = datetime.date.today()

data_inicio = st.sidebar.date_input("Data início", value=default_inicio)
data_fim    = st.sidebar.date_input("Data fim",    value=default_fim)

fontes_disp  = sorted(df_all["source"].dropna().unique()) if not df_all.empty else []
bairros_disp = sorted(df_all["bairro"].dropna().unique()) if not df_all.empty else []
fonte_sel  = st.sidebar.multiselect("Fonte",  fontes_disp,  default=[])
bairro_sel = st.sidebar.multiselect("Município", bairros_disp, default=[])
tipo_sel   = st.sidebar.multiselect("Tipo", ["consumado", "tentativa", "desconhecido"], default=[])
relacao_opcoes = ["ex-companheiro", "ex-marido", "ex-namorado", "companheiro", "marido", "namorado", "familiar", "conhecido", "desconhecido"]
relacao_sel = st.sidebar.multiselect("Relação agressor-vítima", relacao_opcoes, default=[])

st.sidebar.markdown("---")
st.sidebar.caption(
    "Fontes: SSP-SE, G1 Sergipe, Infonet, SE Notícias, "
    "Instagram (@gordinhodopovose, @dougtvnews)  \n"
    "Dados históricos: Anuário FBSP 2025"
)

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
if tipo_sel:
    df = df[df["tipo"].isin(tipo_sel)]
if relacao_sel:
    df = df[df["relacao"].isin(relacao_sel)]

# Subset só 2026 para KPIs fixos
df_2026 = df_all[df_all["published_at"].dt.year == 2026] if not df_all.empty else pd.DataFrame()
mes_atual = datetime.date.today().month
df_mes = df_2026[df_2026["published_at"].dt.month == mes_atual] if not df_2026.empty else pd.DataFrame()


def count_incidents(df: pd.DataFrame) -> int:
    """Count unique incidents: same date + same city = 1 incident."""
    if df.empty:
        return 0
    dedup = df.copy()
    dedup["_date"] = dedup["published_at"].dt.date
    dedup["_city"] = dedup["bairro"].fillna("__unknown__")
    return dedup.drop_duplicates(subset=["_date", "_city"]).shape[0]


def deduplicate_incidents(df: pd.DataFrame) -> pd.DataFrame:
    """Keep one record per incident (date + city), preferring longest title."""
    if df.empty:
        return df
    dedup = df.copy()
    dedup["_date"] = dedup["published_at"].dt.date
    dedup["_city"] = dedup["bairro"].fillna("__unknown__")
    dedup["_tlen"] = dedup["title"].fillna("").str.len()
    dedup = dedup.sort_values("_tlen", ascending=False)
    return dedup.drop_duplicates(subset=["_date", "_city"]).drop(columns=["_date", "_city", "_tlen"])


# ---------------------------------------------------------------------------
# KPIs — foco 2026
# ---------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)

incidentes_2026 = count_incidents(df_2026)
incidentes_mes = count_incidents(df_mes)
mes_anterior = (datetime.date.today().replace(day=1) - datetime.timedelta(days=1))
df_mes_anterior = df_2026[df_2026["published_at"].dt.month == mes_anterior.month] if not df_2026.empty else pd.DataFrame()
incidentes_mes_anterior = count_incidents(df_mes_anterior)
delta_mes = incidentes_mes - incidentes_mes_anterior if incidentes_mes_anterior > 0 else None

consumados_2026 = len(df_2026[df_2026["tipo"] == "consumado"]) if not df_2026.empty and "tipo" in df_2026.columns else 0
tentativas_2026 = len(df_2026[df_2026["tipo"] == "tentativa"]) if not df_2026.empty and "tipo" in df_2026.columns else 0

k1.metric(
    f"🔴 {datetime.date.today().strftime('%B/%Y')}",
    incidentes_mes,
    delta=f"{delta_mes:+d} vs mês anterior" if delta_mes is not None else None,
    delta_color="inverse",
    help="Incidentes únicos no mês atual",
)
k2.metric("Incidentes em 2026", incidentes_2026,
          help=f"{len(df_2026)} registros coletados, agrupados por data+município")
k3.metric("🪦 Consumados 2026", consumados_2026,
          help="Registros classificados como feminicídio consumado")
k4.metric("⚠️ Tentativas 2026", tentativas_2026,
          help="Registros classificados como tentativa de feminicídio")

feminicidios_2024 = anuario.get("feminicidios_por_ano", {}).get("2024", "—")
feminicidios_2023 = anuario.get("feminicidios_por_ano", {}).get("2023", "—")
delta = None
if isinstance(feminicidios_2024, int) and isinstance(feminicidios_2023, int):
    delta = feminicidios_2024 - feminicidios_2023

k5.metric("Feminicídios SE — 2024 (ref.)", feminicidios_2024,
          delta=f"{delta:+d} vs 2023" if delta is not None else None,
          delta_color="inverse")

st.markdown("---")

# ---------------------------------------------------------------------------
# Seção 1 — Dados 2026 (foco principal)
# ---------------------------------------------------------------------------
st.subheader("📰 Casos coletados em 2026 — Sergipe")

if df.empty:
    st.info("Nenhum caso encontrado com os filtros selecionados.")
else:
    df_inc = deduplicate_incidents(df)
    st.caption(f"{len(df_inc)} incidentes únicos ({len(df)} registros coletados de {df['source'].nunique()} fontes)")

    col_ts, col_fonte = st.columns([2, 1])

    with col_ts:
        df_ts = df_inc.copy()
        df_ts["mes"] = df_ts["published_at"].dt.to_period("M").dt.to_timestamp()
        ts = df_ts.groupby("mes").size().reset_index(name="incidentes")
        fig_ts = px.bar(ts, x="mes", y="incidentes", text="incidentes",
                        labels={"mes": "Mês", "incidentes": "Incidentes"},
                        title="Incidentes por mês (2026)")
        fig_ts.update_traces(textposition="outside", marker_color="#c0392b")
        st.plotly_chart(fig_ts, use_container_width=True)

    with col_fonte:
        por_fonte = df.groupby("source").size().reset_index(name="total")
        fig_fonte = px.pie(por_fonte, names="source", values="total",
                           title="Registros por fonte", hole=0.4,
                           color_discrete_sequence=["#c0392b", "#e74c3c", "#f1948a"])
        st.plotly_chart(fig_fonte, use_container_width=True)

    # Gráfico de relação agressor-vítima
    if "relacao" in df.columns:
        df_rel = df[df["relacao"] != "desconhecido"]
        if not df_rel.empty:
            por_relacao = df_rel.groupby("relacao").size().reset_index(name="total").sort_values("total", ascending=True)
            fig_rel = px.bar(por_relacao, x="total", y="relacao", orientation="h",
                             text="total",
                             labels={"total": "Casos", "relacao": "Relação"},
                             title="Relação agressor-vítima",
                             color="total", color_continuous_scale="Reds")
            fig_rel.update_traces(textposition="outside")
            fig_rel.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig_rel, use_container_width=True)

    # Mapa
    df_cidade = df[df["bairro"].notna()].copy()
    if not df_cidade.empty:
        st.subheader("🗺️ Distribuição por município")
        bc = df_cidade["bairro"].value_counts().reset_index()
        bc.columns = ["cidade", "total"]
        bc["lat"] = bc["cidade"].map(lambda b: MUNICIPIO_COORDS.get(b, (None, None))[0])
        bc["lon"] = bc["cidade"].map(lambda b: MUNICIPIO_COORDS.get(b, (None, None))[1])
        bc = bc.dropna(subset=["lat", "lon"])
        if not bc.empty:
            fig_map = px.scatter_mapbox(
                bc, lat="lat", lon="lon", size="total", color="total",
                hover_name="cidade", color_continuous_scale="YlOrRd",
                size_max=40, zoom=8,
                center={"lat": -10.57, "lon": -37.45},
                mapbox_style="open-street-map",
                title="Casos por município — Sergipe",
            )
            st.plotly_chart(fig_map, use_container_width=True)

    # Tabela
    st.subheader("📋 Incidentes")
    cols = ["published_at", "bairro", "tipo", "relacao", "title", "source", "url"]
    _table_cfg = {
        "published_at": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY"),
        "bairro":       st.column_config.TextColumn("Município"),
        "tipo":         st.column_config.TextColumn("Tipo"),
        "relacao":      st.column_config.TextColumn("Relação"),
        "title":        st.column_config.TextColumn("Título", width="large"),
        "source":       st.column_config.TextColumn("Fonte"),
        "url":          st.column_config.LinkColumn("Link", display_text="ver"),
    }
    df_show = df_inc[[c for c in cols if c in df_inc.columns]].sort_values("published_at", ascending=False).reset_index(drop=True)
    st.dataframe(df_show, use_container_width=True, column_config=_table_cfg)
    with st.expander(f"Ver todos os {len(df)} registros coletados"):
        df_all_show = df[[c for c in cols if c in df.columns]].sort_values("published_at", ascending=False).reset_index(drop=True)
        st.dataframe(df_all_show, use_container_width=True, column_config=_table_cfg)

st.markdown("---")

# ---------------------------------------------------------------------------
# Seção 2 — Histórico anual (Anuário FBSP) — contexto
# ---------------------------------------------------------------------------
with st.expander("📊 Histórico anual — Sergipe (Anuário FBSP 2025)", expanded=False):
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
