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
        load_dotenv(override=False)
        logger.info("Loaded .env")
    except ImportError:
        logger.warning("python-dotenv not installed; relying on shell environment variables.")

    # 2. Connect to PostgreSQL
    try:
        import psycopg2  # type: ignore
    except ImportError:
        logger.error("psycopg2 is not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    db_host = os.getenv("POSTGRES_HOST") or "localhost"
    db_port = int(os.getenv("POSTGRES_PORT") or "5432")
    db_name = os.getenv("POSTGRES_DB") or "scrapshe"
    db_user = os.getenv("POSTGRES_USER") or "scrapshe"
    db_password = os.getenv("POSTGRES_PASSWORD") or "changeme"

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
        sys.path.insert(0, os.path.dirname(__file__))

        # 3. Import Instagram posts
        from import_instagram import import_instagram  # type: ignore
        ig_inserted = import_instagram(conn)
        logger.info("import_instagram: %d new raw_records inserted.", ig_inserted)

        # 4. Run cleaner
        from cleaner import process_raw_records  # type: ignore
        inserted = process_raw_records(conn)
        logger.info("process_raw_records: %d new casos inserted.", inserted)

        # 4b. Backfill bairro para casos existentes sem município
        from nlp import extract_bairro, classify_tipo, classify_relacao  # type: ignore

        # Backfill bairro
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, body_trecho FROM casos WHERE bairro IS NULL")
            rows = cur.fetchall()
        updated = 0
        for caso_id, title, body in rows:
            bairro = extract_bairro((title or "") + " " + (body or ""))
            if bairro:
                with conn.cursor() as cur:
                    cur.execute("UPDATE casos SET bairro = %s WHERE id = %s", (bairro, caso_id))
                updated += 1
        if updated:
            conn.commit()
            logger.info("backfill_bairro: %d casos atualizados.", updated)

        # Backfill tipo
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, body_trecho FROM casos WHERE tipo = 'desconhecido'")
            rows = cur.fetchall()
        updated_tipo = 0
        for caso_id, title, body in rows:
            tipo = classify_tipo((title or "") + " " + (body or ""))
            if tipo != "desconhecido":
                with conn.cursor() as cur:
                    cur.execute("UPDATE casos SET tipo = %s WHERE id = %s", (tipo, caso_id))
                updated_tipo += 1
        if updated_tipo:
            conn.commit()
            logger.info("backfill_tipo: %d casos atualizados.", updated_tipo)

        # Backfill relacao
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, body_trecho FROM casos WHERE relacao IS NULL OR relacao = 'desconhecido'")
            rows = cur.fetchall()
        updated_relacao = 0
        for caso_id, title, body in rows:
            relacao = classify_relacao((title or "") + " " + (body or ""))
            if relacao != "desconhecido":
                with conn.cursor() as cur:
                    cur.execute("UPDATE casos SET relacao = %s WHERE id = %s", (relacao, caso_id))
                updated_relacao += 1
        if updated_relacao:
            conn.commit()
            logger.info("backfill_relacao: %d casos atualizados.", updated_relacao)

        # Agrupamento cross-source: casos com mesma data + mesmo bairro de fontes diferentes
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE casos c
                SET caso_grupo_id = sub.min_id
                FROM (
                    SELECT MIN(id) as min_id, published_at, bairro
                    FROM casos
                    WHERE bairro IS NOT NULL AND published_at IS NOT NULL
                    GROUP BY published_at, bairro
                    HAVING COUNT(DISTINCT source) > 1
                ) sub
                WHERE c.published_at = sub.published_at
                  AND c.bairro = sub.bairro
                  AND c.id != sub.min_id
                  AND c.caso_grupo_id IS NULL
            """)
            agrupados = cur.rowcount
        conn.commit()
        if agrupados:
            logger.info("agrupamento: %d casos vinculados a um caso principal.", agrupados)

        # 5. Run exporter
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
