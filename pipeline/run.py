"""
pipeline/run.py

Pipeline entrypoint: loads .env, connects to PostgreSQL, runs cleaner and exporter.
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    # 1. Load .env
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
        logger.info("Loaded .env")
    except ImportError:
        logger.warning("python-dotenv not installed; relying on shell environment variables.")

    # 2. Connect to PostgreSQL
    try:
        import psycopg2  # type: ignore
    except ImportError:
        logger.error("psycopg2 is not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = int(os.getenv("POSTGRES_PORT", "5433"))
    db_name = os.getenv("POSTGRES_DB", "scrapshe")
    db_user = os.getenv("POSTGRES_USER", "scrapshe")
    db_password = os.getenv("POSTGRES_PASSWORD", "changeme")

    logger.info(
        "Connecting to PostgreSQL at %s:%s, database=%s, user=%s",
        db_host, db_port, db_name, db_user,
    )

    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password,
        )
    except psycopg2.OperationalError as exc:
        logger.error("Failed to connect to PostgreSQL: %s", exc)
        sys.exit(1)

    try:
        # 3. Run cleaner
        sys.path.insert(0, os.path.dirname(__file__))
        from cleaner import process_raw_records  # type: ignore
        inserted = process_raw_records(conn)
        logger.info("process_raw_records: %d new casos inserted.", inserted)

        # 4. Run exporter
        from exporter import export_csv  # type: ignore
        export_path = os.getenv("EXPORT_CSV_PATH", "export.csv")
        exported = export_csv(conn, output_path=export_path)
        logger.info("export_csv: %d rows written to %s.", exported, export_path)

    finally:
        # 5. Close connection
        conn.close()
        logger.info("Database connection closed.")


if __name__ == "__main__":
    main()
