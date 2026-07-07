"""
load_raw.py
===========
PURPOSE:
    Reads CSV files from data/raw/ and loads them into PostgreSQL
    under the 'raw' schema. This is Phase 1 — getting raw data
    into the database exactly as-is (no transformations yet).

WHY LOAD RAW DATA FIRST?
    The ELT (Extract-Load-Transform) pattern loads data first, then
    transforms it in the database using SQL/dbt. This is the modern
    approach because:
    1. You never lose the original data (can re-process anytime)
    2. Databases are optimized for transformations (faster than Python)
    3. Raw data is preserved for auditing and debugging

HOW IT WORKS:
    CSV files → Pandas DataFrame → SQLAlchemy → PostgreSQL (raw schema)
    
    pandas.to_sql() handles the bulk insert efficiently using
    psycopg2's copy_from under the hood.

HOW TO RUN:
    python python/ingest/load_raw.py

PREREQUISITES:
    - PostgreSQL running (docker-compose up -d postgres)
    - .env file with database credentials
    - CSV files in data/raw/ (run generate_dataset.py first)
"""

import os
import sys
import time
import pandas as pd
from pathlib import Path
from loguru import logger

# Add parent directory to path so we can import db_utils
sys.path.insert(0, str(Path(__file__).parent))
from db_utils import get_engine, create_schema_if_not_exists, bulk_load_dataframe

# ── Configuration ──────────────────────────────────────────────────────────────
RAW_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "raw"
RAW_SCHEMA   = "raw"

# Mapping: CSV filename → PostgreSQL table name (in raw schema)
# We define explicit column types so Pandas doesn't guess wrong
TABLE_CONFIGS = {
    "categories.csv": {
        "table_name": "categories",
        "dtypes": {
            "category_id": str,
            "category_name": str,
            "department": str,
        }
    },
    "sellers.csv": {
        "table_name": "sellers",
        "dtypes": {
            "seller_id": str,
            "seller_name": str,
            "city": str,
            "state": str,
            "zip_code": str,
            "email": str,
            "phone": str,
            "created_at": str,
        }
    },
    "customers.csv": {
        "table_name": "customers",
        "dtypes": {
            "customer_id": str,
            "first_name": str,
            "last_name": str,
            "email": str,
            "city": str,
            "state": str,
            "zip_code": str,
            "signup_date": str,
            "is_active": str,
        }
    },
    "products.csv": {
        "table_name": "products",
        "dtypes": {
            "product_id": str,
            "category_id": str,
            "product_name": str,
            "description": str,
        }
    },
    "orders.csv": {
        "table_name": "orders",
        "dtypes": {
            "order_id": str,
            "customer_id": str,
            "order_date": str,
            "order_status": str,
            "delivery_date": str,
            "estimated_delivery": str,
        }
    },
    "order_items.csv": {
        "table_name": "order_items",
        "dtypes": {
            "order_item_id": str,
            "order_id": str,
            "product_id": str,
            "seller_id": str,
        }
    },
    "payments.csv": {
        "table_name": "payments",
        "dtypes": {
            "payment_id": str,
            "order_id": str,
            "payment_type": str,
            "payment_status": str,
        }
    },
    "reviews.csv": {
        "table_name": "reviews",
        "dtypes": {
            "review_id": str,
            "order_id": str,
            "comment_title": str,
            "comment_text": str,
            "review_date": str,
        }
    },
}


def load_csv_to_postgres(
    filepath: Path,
    table_name: str,
    engine,
    schema: str = "raw",
    chunk_size: int = 5000,
    dtype_overrides: dict = None,
) -> int:
    """
    Loads a single CSV file into a PostgreSQL table.
    
    Args:
        filepath:        Path to the CSV file
        table_name:      PostgreSQL table name (without schema prefix)
        engine:          SQLAlchemy engine
        schema:          PostgreSQL schema to load into (default: "raw")
        chunk_size:      Number of rows to insert per batch (tuned for performance)
        dtype_overrides: Force specific column types when reading CSV
    
    Returns:
        Number of rows loaded
    
    WHY CHUNK SIZE?
        Loading 50,000 rows in one INSERT would use a lot of RAM.
        Chunking loads 5,000 rows at a time — a good balance of speed vs memory.
        
    WHY if_exists="replace"?
        On every pipeline run, we drop and recreate the raw tables.
        This ensures idempotency (running the pipeline twice gives same result).
        In production, you might use "append" with deduplication logic instead.
    """
    logger.info(f"Loading {filepath.name} → {schema}.{table_name}")
    start_time = time.time()
    
    # Read CSV
    df = pd.read_csv(filepath, dtype=dtype_overrides, low_memory=False)
    
    # Add metadata columns (data lineage — track when data was loaded)
    df["_loaded_at"] = pd.Timestamp.now()
    df["_source_file"] = filepath.name
    
    row_count = len(df)
    logger.debug(f"  Read {row_count:,} rows, {len(df.columns)} columns")
    
    # Load to PostgreSQL using PostgreSQL COPY (much faster than pandas.to_sql)
    bulk_load_dataframe(
        df=df,
        table_name=table_name,
        engine=engine,
        schema=schema,
        if_exists="replace",
        index=False,
    )
    
    elapsed = time.time() - start_time
    logger.success(f"  Loaded {row_count:,} rows in {elapsed:.1f}s")
    return row_count


def validate_row_counts(engine, schema: str = "raw") -> None:
    """
    After loading, query each table's row count and log it.
    This is a basic data quality check — if a table has 0 rows, something went wrong.
    
    In production, you'd also check:
    - Max/min values are in valid ranges
    - No completely null columns
    - Foreign key integrity (every order_id in order_items exists in orders)
    """
    from sqlalchemy import text
    
    logger.info("\n--- Row Count Validation ---")
    tables = ["categories", "sellers", "customers", "products",
              "orders", "order_items", "payments", "reviews"]
    
    with engine.connect() as conn:
        for table in tables:
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM {schema}.{table}")
            )
            count = result.scalar()
            status = "✓" if count > 0 else "✗ EMPTY TABLE!"
            logger.info(f"  {status} {schema}.{table}: {count:,} rows")


def main():
    """
    Main execution: load all CSV files → raw schema in PostgreSQL.
    """
    logger.info("=" * 60)
    logger.info("PHASE 1: RAW DATA INGESTION")
    logger.info("=" * 60)
    
    # Verify data directory exists
    if not RAW_DATA_DIR.exists():
        logger.error(f"Raw data directory not found: {RAW_DATA_DIR}")
        logger.info("Run generate_dataset.py first!")
        sys.exit(1)
    
    # Connect to database
    engine = get_engine()
    
    # Create raw schema if it doesn't exist
    create_schema_if_not_exists(RAW_SCHEMA, engine)
    
    # Load each CSV file
    total_rows = 0
    failed_tables = []
    
    for filename, config in TABLE_CONFIGS.items():
        filepath = RAW_DATA_DIR / filename
        
        if not filepath.exists():
            logger.warning(f"File not found: {filepath} — skipping")
            failed_tables.append(filename)
            continue
        
        try:
            rows = load_csv_to_postgres(
                filepath=filepath,
                table_name=config["table_name"],
                engine=engine,
                schema=RAW_SCHEMA,
                dtype_overrides=config.get("dtypes"),
            )
            total_rows += rows
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            failed_tables.append(filename)
    
    # Validate all tables loaded correctly
    validate_row_counts(engine, RAW_SCHEMA)
    
    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("INGESTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Total rows loaded: {total_rows:,}")
    logger.info(f"  Tables succeeded:  {len(TABLE_CONFIGS) - len(failed_tables)}")
    
    if failed_tables:
        logger.warning(f"  Failed tables: {', '.join(failed_tables)}")
        sys.exit(1)
    else:
        logger.success("Raw ingestion complete!")


if __name__ == "__main__":
    main()
