"""
pipeline/import_instagram.py

Runs the Instagram scraper and imports results into raw_records.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def import_instagram(conn) -> int:
    _root = Path(__file__).resolve().parent.parent
    script = _root / "scripts" / "instaloader_fetch.py"

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, str(script), "--output", tmp_path],
            capture_output=True, text=True, timeout=600,
        )
        if result.stdout:
            logger.info("Instagram scraper: %s", result.stdout.strip())
        if result.stderr:
            logger.warning("Instagram scraper stderr: %s", result.stderr.strip())
        if result.returncode != 0:
            logger.error("Instagram scraper failed (exit %d)", result.returncode)
            return 0

        records = []
        with open(tmp_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not records:
        logger.info("No Instagram posts to import.")
        return 0

    inserted = 0
    with conn.cursor() as cur:
        for rec in records:
            cur.execute(
                """
                INSERT INTO raw_records (source, url, title, body, published_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING
                """,
                (
                    "instagram",
                    rec.get("url", ""),
                    rec.get("title", "")[:500],
                    rec.get("body", ""),
                    rec.get("published_at"),
                ),
            )
            if cur.rowcount:
                inserted += 1
    conn.commit()
    logger.info("import_instagram: %d new posts inserted.", inserted)
    return inserted
