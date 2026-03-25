"""
scripts/infonet_backfill.py

Backfill histórico do Infonet: percorre páginas de busca e insere
registros de 2026 em raw_records. Para quando encontrar artigos de 2025.

Uso:
    python scripts/infonet_backfill.py
"""

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env", override=False)

SEARCH_URL = "https://infonet.com.br/page/{page}/?s=feminicidio"
CUTOFF = datetime(2026, 1, 1)
MAX_PAGES = 10
DELAY = 2  # segundos entre requests

MONTH_MAP = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}

RE_ARTICLE = re.compile(
    r'<h2[^>]*>\s*<a\s+href="(https://infonet\.com\.br/noticias/[^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL,
)
RE_TIME = re.compile(r'<time[^>]*>(.*?)</time>', re.DOTALL)


def parse_date(raw: str) -> datetime | None:
    raw = raw.strip().lower()
    m = re.match(r"(\d{1,2})\s+(\w+),?\s+(\d{4})", raw)
    if not m:
        return None
    day, mon, year = int(m.group(1)), m.group(2)[:3], int(m.group(3))
    month = MONTH_MAP.get(mon)
    if not month:
        return None
    return datetime(year, month, day)


def connect():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST") or "localhost",
        port=int(os.getenv("POSTGRES_PORT") or "5432"),
        dbname=os.getenv("POSTGRES_DB") or "postgres",
        user=os.getenv("POSTGRES_USER") or "postgres",
        password=os.getenv("POSTGRES_PASSWORD") or "",
        sslmode="require",
    )


def insert(conn, url, title, published_at):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw_records (source, url, title, body, published_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING
            """,
            ("infonet", url, title[:500], title[:500], published_at),
        )
        inserted = cur.rowcount
    conn.commit()
    return inserted == 1


def main():
    conn = connect()
    total = 0

    for page in range(1, MAX_PAGES + 1):
        url = SEARCH_URL.format(page=page)
        print(f"Fetching page {page}: {url}")

        resp = requests.get(url, timeout=30, headers={"User-Agent": "scrapshe/1.0"})
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}, parando.")
            break

        html = resp.content.decode("utf-8", errors="replace")
        articles = RE_ARTICLE.findall(html)
        times = RE_TIME.findall(html)

        if not articles:
            print("  Nenhum artigo encontrado, parando.")
            break

        stop = False
        for i, (art_url, art_title) in enumerate(articles):
            raw_date = times[i] if i < len(times) else ""
            pub_date = parse_date(raw_date)

            if pub_date and pub_date < CUTOFF:
                print(f"  Artigo de {pub_date.date()} anterior a 2026, parando.")
                stop = True
                break

            title = re.sub(r"<[^>]+>", "", art_title).strip()
            ok = insert(conn, art_url, title, pub_date)
            if ok:
                total += 1
                print(f"  + {title[:80]}")

        if stop:
            break

        time.sleep(DELAY)

    conn.close()
    print(f"\nTotal inserido: {total}")


if __name__ == "__main__":
    main()
