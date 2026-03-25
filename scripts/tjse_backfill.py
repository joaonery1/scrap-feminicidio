"""
scripts/tjse_backfill.py

Backfill dos registros TJ-SE já inseridos:
1. Remove raw_records (e casos derivados) onde o body NÃO contém "feminicid"
   (falsos positivos capturados antes da validação de keyword ser implementada)
2. Para os válidos, re-busca o texto no TJ-SE e salva o trecho ao redor de "feminicid"
   em vez do cabeçalho do documento.

Uso:
    python scripts/tjse_backfill.py
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

_root = Path(__file__).resolve().parent.parent
_env = _root / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env, override=False)
    except ImportError:
        pass

try:
    import psycopg2
    import requests
except ImportError as e:
    print(f"Dependência faltando: {e}. Run: pip install psycopg2-binary requests", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://www.tjse.jus.br/diario/internet"
WINDOW = 600  # chars ao redor de "feminicid"


def get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT") or "5432"),
        dbname=os.getenv("POSTGRES_DB", "postgres"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        sslmode="require",
    )


def fetch_tjse_text(session: requests.Session, nu_edicao: str, cd_secao: str) -> str:
    """Re-busca o texto de uma seção do TJ-SE e retorna o trecho com 'feminicid'."""
    data = {
        "tmp.diario.nu_edicao": nu_edicao,
        "tmp.diario.cd_secao": cd_secao,
        "tmp.verintegra": "1",
    }
    resp = session.post(f"{BASE_URL}/principal.wsp", data=data, timeout=20)
    html = resp.content.decode("latin-1")
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()

    # Extrai contexto ao redor de "feminicid"
    lower = text.lower()
    idx = lower.find("feminicid")
    if idx < 0:
        return ""
    half = WINDOW // 2
    start = max(0, idx - half)
    end = min(len(text), idx + half)
    excerpt = text[start:end].strip()
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt = excerpt + "..."
    return excerpt


def init_session() -> requests.Session:
    """Cria sessão com cookie de sessão do TJ-SE."""
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (compatible; scrapshe/1.0)"
    s.get(f"{BASE_URL}/pesquisar.wsp", timeout=15)  # inicializa cookie
    return s


def parse_url_params(url: str) -> dict:
    """Extrai parâmetros da URL canônica do TJ-SE."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return {k: v[0] for k, v in params.items()}


def main():
    conn = get_conn()
    session = init_session()

    with conn.cursor() as cur:
        cur.execute("SELECT id, url, body FROM raw_records WHERE source = 'tjse' ORDER BY id")
        records = cur.fetchall()

    print(f"Total registros TJ-SE: {len(records)}")

    false_positives = []
    to_update = []

    for raw_id, url, body in records:
        if "feminicid" not in (body or "").lower():
            false_positives.append(raw_id)
            print(f"  [FALSO POSITIVO] id={raw_id} url={url[:80]}")
            continue

        # Re-busca para pegar trecho correto ao redor de "feminicid"
        params = parse_url_params(url)
        nu_edicao = params.get("tmp.diario.nu_edicao", "")
        cd_secao = params.get("tmp.diario.cd_secao", "")
        if not nu_edicao or not cd_secao:
            print(f"  [SKIP] id={raw_id} — URL sem params esperados")
            continue

        novo_body = fetch_tjse_text(session, nu_edicao, cd_secao)
        if not novo_body:
            false_positives.append(raw_id)
            print(f"  [FALSO POSITIVO após re-fetch] id={raw_id}")
            continue

        to_update.append((novo_body, raw_id))
        print(f"  [OK] id={raw_id} edicao={nu_edicao} secao={cd_secao}")

    # Remove falsos positivos
    if false_positives:
        with conn.cursor() as cur:
            # Remove casos derivados primeiro
            cur.execute(
                "DELETE FROM casos WHERE raw_id = ANY(%s)",
                (false_positives,)
            )
            casos_del = cur.rowcount
            # Remove raw_records
            cur.execute(
                "DELETE FROM raw_records WHERE id = ANY(%s)",
                (false_positives,)
            )
            raw_del = cur.rowcount
        conn.commit()
        print(f"\nRemovidos {raw_del} raw_records e {casos_del} casos (falsos positivos).")

    # Atualiza body dos válidos
    if to_update:
        with conn.cursor() as cur:
            for novo_body, raw_id in to_update:
                cur.execute(
                    "UPDATE raw_records SET body = %s WHERE id = %s",
                    (novo_body, raw_id)
                )
                # Atualiza body_trecho no caso derivado
                trecho = novo_body[:500]
                cur.execute(
                    "UPDATE casos SET body_trecho = %s WHERE raw_id = %s",
                    (trecho, raw_id)
                )
        conn.commit()
        print(f"Atualizados {len(to_update)} registros com trecho correto.")

    conn.close()
    print("Pronto.")


if __name__ == "__main__":
    main()
