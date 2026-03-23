"""
pipeline/exporter.py

Exports casos table to CSV.
"""

import csv
import logging

logger = logging.getLogger(__name__)


def export_csv(conn, output_path: str = "export.csv") -> int:
    """
    Export all rows from casos table to a CSV file ordered by published_at DESC.
    Returns the number of rows exported.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM casos ORDER BY published_at DESC")
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]

    if not rows:
        logger.info("No casos found to export.")
        # Write empty CSV with headers only
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=col_names)
            writer.writeheader()
        return 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=col_names)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(zip(col_names, row)))

    logger.info("Exported %d casos to %s", len(rows), output_path)
    return len(rows)
