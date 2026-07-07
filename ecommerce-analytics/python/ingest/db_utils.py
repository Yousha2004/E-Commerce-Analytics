"""
db_utils.py
===========
PURPOSE:
    Shared database connection utilities used by all Python scripts.
    
WHY A SEPARATE FILE?
    Instead of copy-pasting the database connection code into every script,
    we put it in one place. If you change the password or host, you only
    update it here. This is the DRY principle (Don't Repeat Yourself).

    In production systems, credentials are NEVER hardcoded. They come from
    environment variables or secret managers (AWS Secrets Manager, Vault).
    We use python-dotenv to load a .env file for local development.

HOW CONNECTION POOLING WORKS:
    Instead of opening/closing a database connection for every query (slow!),
    SQLAlchemy keeps a "pool" of open connections. Queries reuse these connections.
    This is critical for performance when Airflow runs many tasks.
"""

import io
import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from loguru import logger
from psycopg2 import sql as pg_sql

# Load .env file from project root (contains DB_HOST, DB_PASSWORD, etc.)
load_dotenv()


def get_db_url() -> str:
    """
    Builds the PostgreSQL connection URL from environment variables.
    
    URL format: postgresql+psycopg2://user:password@host:port/database
    
    Environment variables (set in .env file or Docker environment):
        DB_HOST     — hostname (default: localhost)
        DB_PORT     — port (default: 5432)
        DB_NAME     — database name
        DB_USER     — username
        DB_PASSWORD — password
    """
    host     = os.getenv("DB_HOST", "localhost")
    port     = os.getenv("DB_PORT", "5432")
    name     = os.getenv("DB_NAME", "ecommerce_dw")
    user     = os.getenv("DB_USER", "ecommerce_user")
    password = os.getenv("DB_PASSWORD", "ecommerce_pass")
    
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def get_engine(pool_size: int = 5, echo: bool = False):
    """
    Creates and returns a SQLAlchemy engine with connection pooling.
    
    Args:
        pool_size: Number of persistent connections in the pool (default: 5)
        echo:      If True, prints every SQL query (useful for debugging)
    
    Returns:
        SQLAlchemy Engine object
    
    WHAT IS AN ENGINE?
        The engine is the "gateway" to your database. It handles:
        - Authentication
        - Connection pooling
        - Query execution
        - Transaction management
    """
    url = get_db_url()
    engine = create_engine(
        url,
        pool_size=pool_size,
        max_overflow=10,       # Allow 10 extra connections above pool_size
        pool_pre_ping=True,    # Test connection health before using it
        echo=echo,
    )
    logger.debug(f"Database engine created for: {url.split('@')[1]}")  # Don't log password
    return engine


def get_session(engine=None):
    """
    Returns a SQLAlchemy session for ORM-style operations.
    Use as a context manager:
        with get_session() as session:
            session.execute(...)
    """
    if engine is None:
        engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def test_connection() -> bool:
    """
    Tests the database connection and prints the PostgreSQL version.
    Run this first to verify your setup is working.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.scalar()
            logger.success(f"Database connection successful!")
            logger.info(f"PostgreSQL version: {version}")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        logger.info("Make sure PostgreSQL is running: docker-compose up -d postgres")
        return False


def bulk_load_dataframe(
    df: pd.DataFrame,
    table_name: str,
    engine=None,
    schema: str = "raw",
    if_exists: str = "replace",
    index: bool = False,
) -> None:
    """
    Bulk-load a pandas DataFrame into PostgreSQL using PostgreSQL COPY.
    This is much faster than pandas.to_sql for large datasets.
    """
    if engine is None:
        engine = get_engine()

    try:
        with engine.begin() as conn:
            if if_exists == "replace":
                conn.exec_driver_sql(
                    f'DROP TABLE IF EXISTS "{schema}"."{table_name}"'
                )
            elif if_exists != "append":
                raise ValueError(f"Unsupported if_exists value: {if_exists}")

            columns = [str(col) for col in df.columns]
            quoted_columns = [f'"{col.replace(chr(34), chr(34) * 2)}"' for col in columns]
            column_defs = ", ".join([f"{col} TEXT" for col in quoted_columns])

            conn.exec_driver_sql(
                f'CREATE TABLE IF NOT EXISTS "{schema}"."{table_name}" ({column_defs})'
            )

            buffer = io.StringIO()
            df.to_csv(buffer, index=index, header=True)
            buffer.seek(0)

            with conn.connection.cursor() as cur:
                cur.copy_expert(
                    f'COPY "{schema}"."{table_name}" ({", ".join(quoted_columns)}) FROM STDIN WITH CSV HEADER',
                    buffer,
                )

        logger.success(f"Loaded {len(df):,} rows into {schema}.{table_name} via COPY")
    except Exception as exc:
        logger.exception(f"Failed to bulk load into {schema}.{table_name}: {exc}")
        raise


def create_schema_if_not_exists(schema_name: str, engine=None) -> None:
    """
    Creates a PostgreSQL schema (namespace) if it doesn't already exist.
    
    WHY MULTIPLE SCHEMAS?
    We organize our database into layers:
        raw      → Original data as-is from CSV files
        staging  → Cleaned and validated data
        marts    → Final analytical models (facts and dimensions)
    
    This mirrors the medallion architecture (Bronze → Silver → Gold).
    """
    if engine is None:
        engine = get_engine()
    
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name};"))
        conn.commit()
        logger.info(f"Schema '{schema_name}' ready.")


if __name__ == "__main__":
    # Run this file directly to test your database connection
    test_connection()
