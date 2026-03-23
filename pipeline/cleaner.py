"""
pipeline/cleaner.py

Reads raw_records WHERE processed = FALSE, normalizes dates, deduplicates,
inserts into casos, marks raw_records as processed.
"""

import hashlib
import logging
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _normalize_date(value) -> Optional[str]:
    """Normalize various date representations to ISO 8601 string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
                    "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date().isoformat()
            except ValueError:
                continue
    return None


def _compute_dedup_hash(published_at_iso: Optional[str], body: Optional[str]) -> str:
    """SHA-256 of published_at date + first 100 chars of body."""
    date_part = published_at_iso or ""
    body_part = (body or "")[:100]
    raw = f"{date_part}{body_part}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def process_raw_records(conn) -> int:
    """
    Process unprocessed raw_records:
    - Normalize dates
    - Deduplicate via SHA-256 hash
    - Insert into casos
    - Mark raw_records.processed = TRUE
    Returns number of casos inserted.
    """
    inserted = 0
    skipped = 0

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source, url, title, body, published_at
            FROM raw_records
            WHERE processed = FALSE
            ORDER BY id
            """
        )
        rows = cur.fetchall()

    if not rows:
        logger.info("No unprocessed raw_records found.")
        return 0

    logger.info("Found %d unprocessed raw_records.", len(rows))

    for row in rows:
        raw_id, source, url, title, body, published_at = row

        published_at_iso = _normalize_date(published_at)
        dedup_hash = _compute_dedup_hash(published_at_iso, body)

        with conn.cursor() as cur:
            # Check if dedup_hash already exists
            cur.execute(
                "SELECT 1 FROM casos WHERE dedup_hash = %s LIMIT 1",
                (dedup_hash,)
            )
            exists = cur.fetchone()

        if exists:
            skipped += 1
            # Still mark as processed to avoid re-scanning
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE raw_records SET processed = TRUE WHERE id = %s",
                    (raw_id,)
                )
            conn.commit()
            continue

        body_trecho = (body or "")[:500]

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO casos
                    (raw_id, source, url, title, body_trecho, published_at, bairro, dedup_hash)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (raw_id, source, url, title, body_trecho, published_at_iso, None, dedup_hash)
            )
            cur.execute(
                "UPDATE raw_records SET processed = TRUE WHERE id = %s",
                (raw_id,)
            )
        conn.commit()
        inserted += 1

    total_processed = inserted + skipped
    if total_processed > 0:
        dup_rate = skipped / total_processed
        if dup_rate > 0.05:
            logger.warning(
                "High duplicate rate in this run: %.1f%% (%d/%d records were duplicates).",
                dup_rate * 100,
                skipped,
                total_processed,
            )

    logger.info(
        "process_raw_records complete: %d inserted, %d skipped (duplicates).",
        inserted,
        skipped,
    )
    return inserted
