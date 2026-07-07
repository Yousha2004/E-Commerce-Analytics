"""
clean_data.py
=============
PURPOSE:
    Transforms raw data from the 'raw' schema into clean, validated data
    in the 'staging' schema. This is the "T" in ETL.

WHAT CLEANING IS DONE?
    1. Type casting — convert strings to proper dates, booleans, decimals
    2. Null handling — fill, impute, or drop missing values
    3. Duplicate removal — identify and remove exact duplicate rows
    4. Value validation — flag/remove records with impossible values
    5. String normalization — trim whitespace, standardize case
    6. Referential integrity — ensure foreign keys actually exist
    
WHY CLEAN IN PYTHON VS SQL?
    We clean in Python here (for explicitness in learning).
    In production, dbt handles most cleaning in SQL — it's faster
    and more maintainable. But Python is great for:
    - Complex ML-based imputation
    - Custom business rule validation
    - Processing binary/non-SQL file formats

HOW TO RUN:
    python python/transform/clean_data.py
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger

# Import shared database utilities
sys.path.insert(0, str(Path(__file__).parent.parent / "ingest"))
from db_utils import get_engine, create_schema_if_not_exists, bulk_load_dataframe

RAW_SCHEMA     = "raw"
STAGING_SCHEMA = "staging"


# ── Cleaning Functions — One per table ────────────────────────────────────────

def clean_categories(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the categories table.
    Categories are mostly static reference data, so cleaning is minimal.
    """
    logger.info("Cleaning categories...")
    original_count = len(df)
    
    # Strip whitespace from string columns
    df["category_name"] = df["category_name"].str.strip()
    df["department"]    = df["department"].str.strip()
    
    # Remove duplicates (same category_id should be unique)
    df = df.drop_duplicates(subset=["category_id"])
    
    # Remove rows where category_name is null
    df = df.dropna(subset=["category_name"])
    
    logger.info(f"  Categories: {original_count} → {len(df)} rows")
    return df


def clean_customers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean customer records.
    
    KEY DECISIONS:
    - Email validation: keep rows with @ and .  in email
    - Missing city: fill with 'Unknown' (don't drop — losing customers is bad)
    - Duplicate emails: keep the most recently signed up record
    - signup_date: parse as date, drop rows where it's unparseable
    """
    logger.info("Cleaning customers...")
    original_count = len(df)
    
    # Parse dates — coerce turns unparseable dates to NaT (null)
    df["signup_date"] = pd.to_datetime(df.get("signup_date"), errors="coerce")
    
    # Drop rows with invalid signup dates
    null_dates = df["signup_date"].isna().sum()
    if null_dates > 0:
        logger.warning(f"  Dropping {null_dates} customers with invalid signup_date")
    df = df.dropna(subset=["signup_date"])
    
    # Normalize string columns
    for col in ["first_name", "last_name", "city", "state"]:
        df[col] = df.get(col, pd.Series(["" for _ in range(len(df))], index=df.index)).astype(str).str.strip().str.title()
    
    df["email"] = df.get("email", pd.Series(["" for _ in range(len(df))], index=df.index)).astype(str).str.strip().str.lower()
    
    # Validate emails (simple check: must contain @ and .)
    valid_email_mask = df["email"].str.contains(r"@.*\.", regex=True, na=False)
    invalid_emails = (~valid_email_mask).sum()
    if invalid_emails > 0:
        logger.warning(f"  Removing {invalid_emails} records with invalid emails")
    df = df[valid_email_mask]
    
    # Handle missing city (fill don't drop — city is not critical)
    df["city"] = df["city"].fillna("Unknown")
    df["city"] = df["city"].replace("None", "Unknown")
    
    # Remove duplicates: same customer_id appears twice → keep first
    df = df.drop_duplicates(subset=["customer_id"], keep="first")
    
    # If same email appears twice (different IDs), keep the earliest signup
    df = df.sort_values("signup_date").drop_duplicates(subset=["email"], keep="first")
    
    # Normalize boolean
    df["is_active"] = df.get("is_active", pd.Series([True for _ in range(len(df))], index=df.index)).astype(str).str.lower().map(
        {"true": True, "false": False, "1": True, "0": False}
    ).fillna(True)  # Default to active if unknown
    
    logger.info(f"  Customers: {original_count} → {len(df)} rows")
    return df


def clean_sellers(df: pd.DataFrame) -> pd.DataFrame:
    """Clean seller records."""
    logger.info("Cleaning sellers...")
    original_count = len(df)
    
    df = df.drop_duplicates(subset=["seller_id"])
    df["seller_name"] = df["seller_name"].str.strip()
    df["state"] = df["state"].str.strip().str.upper()
    df["city"]  = df["city"].str.strip().str.title()
    df["email"] = df["email"].str.strip().str.lower()
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    
    logger.info(f"  Sellers: {original_count} → {len(df)} rows")
    return df


def clean_products(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean product records.
    
    KEY DECISIONS:
    - Negative prices: set to null then drop (data corruption)
    - price > 3000: cap at 3000 (likely data entry errors for most categories)
    - Missing stock: impute with 0 (safest assumption — don't oversell)
    """
    logger.info("Cleaning products...")
    original_count = len(df)
    
    df = df.drop_duplicates(subset=["product_id"])
    
    # Numeric columns: ensure correct dtype
    for col in ["price", "cost_price", "weight_g", "length_cm", "height_cm", "width_cm", "stock_quantity"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = pd.NA
    
    # Remove products with impossible prices
    df = df[df["price"].notna() & (df["price"] > 0)]
    
    # Cap extreme prices (outlier treatment)
    high_price_count = (df["price"] > 3000).sum()
    if high_price_count > 0:
        logger.warning(f"  Capping {high_price_count} products with price > $3000")
    df["price"] = df["price"].clip(upper=3000.0)
    
    # Ensure cost_price is less than price (data integrity)
    # If cost > price, set cost to 60% of price as a reasonable default
    invalid_cost_mask = df["cost_price"] >= df["price"]
    df.loc[invalid_cost_mask, "cost_price"] = df.loc[invalid_cost_mask, "price"] * 0.60
    
    # Fill missing stock with 0
    df["stock_quantity"] = df["stock_quantity"].fillna(0).clip(lower=0)
    
    # Normalize boolean
    df["is_active"] = df["is_active"].astype(str).str.lower().map(
        {"true": True, "false": False, "1": True, "0": False}
    ).fillna(True)
    
    # Fill missing weights (median imputation)
    median_weight = df["weight_g"].median()
    df["weight_g"] = df["weight_g"].fillna(median_weight)
    
    # String cleanup
    df["product_name"] = df["product_name"].str.strip()
    
    logger.info(f"  Products: {original_count} → {len(df)} rows")
    return df


def clean_orders(df: pd.DataFrame, valid_customer_ids: set, valid_seller_ids: set) -> pd.DataFrame:
    """
    Clean orders table.
    
    REFERENTIAL INTEGRITY CHECK:
    We check that every customer_id in orders actually exists in customers.
    Orphan orders (orders without a customer) are invalid data that would
    break JOIN queries downstream.
    """
    logger.info("Cleaning orders...")
    original_count = len(df)
    
    df = df.drop_duplicates(subset=["order_id"])
    
    # Parse dates
    df["order_date"]         = pd.to_datetime(df["order_date"],         errors="coerce")
    df["delivery_date"]      = pd.to_datetime(df["delivery_date"],       errors="coerce")
    df["estimated_delivery"] = pd.to_datetime(df["estimated_delivery"], errors="coerce")
    
    # Drop orders with invalid order dates (can't analyze without a date)
    df = df.dropna(subset=["order_date"])
    
    # Normalize status values
    valid_statuses = {"delivered", "shipped", "processing", "cancelled", "pending"}
    df["order_status"] = df["order_status"].str.strip().str.lower()
    df = df[df["order_status"].isin(valid_statuses)]
    
    # Freight value: fill negatives/nulls with median
    df["freight_value"] = pd.to_numeric(df["freight_value"], errors="coerce")
    median_freight = df["freight_value"].median()
    df["freight_value"] = df["freight_value"].fillna(median_freight).clip(lower=0)
    
    # Referential integrity: drop orders referencing non-existent customers
    before = len(df)
    df = df[df["customer_id"].isin(valid_customer_ids)]
    orphans = before - len(df)
    if orphans > 0:
        logger.warning(f"  Dropped {orphans} orders with invalid customer_id")
    
    logger.info(f"  Orders: {original_count} → {len(df)} rows")
    return df


def clean_order_items(df: pd.DataFrame, valid_order_ids: set, valid_product_ids: set) -> pd.DataFrame:
    """Clean order items — the revenue-critical table."""
    logger.info("Cleaning order_items...")
    original_count = len(df)
    
    df = df.drop_duplicates(subset=["order_item_id"])
    
    # Numeric columns
    for col in ["quantity", "unit_price", "total_price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # Remove items with invalid prices or quantities
    df = df[(df["unit_price"] > 0) & (df["quantity"] > 0)]
    
    # Recalculate total_price to ensure consistency
    # (source data may have rounding errors)
    df["total_price"] = (df["unit_price"] * df["quantity"]).round(2)
    
    # Referential integrity
    before = len(df)
    df = df[df["order_id"].isin(valid_order_ids)]
    df = df[df["product_id"].isin(valid_product_ids)]
    orphans = before - len(df)
    if orphans > 0:
        logger.warning(f"  Dropped {orphans} order_items with invalid foreign keys")
    
    logger.info(f"  Order items: {original_count} → {len(df)} rows")
    return df


def clean_payments(df: pd.DataFrame, valid_order_ids: set) -> pd.DataFrame:
    """Clean payment records."""
    logger.info("Cleaning payments...")
    original_count = len(df)
    
    df = df.drop_duplicates(subset=["payment_id"])
    
    df["payment_value"] = pd.to_numeric(df["payment_value"], errors="coerce")
    df["installments"]  = pd.to_numeric(df["installments"],  errors="coerce").fillna(1).astype(int)
    
    # Remove payments with zero or negative amounts
    df = df[df["payment_value"] > 0]
    
    # Valid payment types
    valid_types = {"credit_card", "boleto", "debit_card", "voucher"}
    df["payment_type"] = df["payment_type"].str.strip().str.lower()
    df = df[df["payment_type"].isin(valid_types)]
    
    # Referential integrity
    df = df[df["order_id"].isin(valid_order_ids)]
    
    logger.info(f"  Payments: {original_count} → {len(df)} rows")
    return df


def clean_reviews(df: pd.DataFrame, valid_order_ids: set) -> pd.DataFrame:
    """Clean review records."""
    logger.info("Cleaning reviews...")
    original_count = len(df)
    
    df = df.drop_duplicates(subset=["review_id"])
    
    # Score must be 1-5
    df["review_score"] = pd.to_numeric(df["review_score"], errors="coerce")
    df = df[df["review_score"].between(1, 5)]
    df["review_score"] = df["review_score"].astype(int)
    
    df["review_date"] = pd.to_datetime(df["review_date"], errors="coerce")
    
    # Clean text fields
    df["comment_title"] = df["comment_title"].str.strip().fillna("")
    df["comment_text"]  = df["comment_text"].str.strip().fillna("")
    
    # Referential integrity
    df = df[df["order_id"].isin(valid_order_ids)]
    
    logger.info(f"  Reviews: {original_count} → {len(df)} rows")
    return df


# ── Data Quality Report ────────────────────────────────────────────────────────

def generate_quality_report(raw_counts: dict, clean_counts: dict) -> None:
    """Print a summary comparing raw vs cleaned row counts."""
    logger.info("\n" + "=" * 60)
    logger.info("DATA QUALITY REPORT")
    logger.info("=" * 60)
    logger.info(f"{'Table':<20} {'Raw':>10} {'Clean':>10} {'Dropped':>10} {'Drop %':>8}")
    logger.info("-" * 60)
    
    for table in raw_counts:
        raw   = raw_counts[table]
        clean = clean_counts.get(table, 0)
        dropped = raw - clean
        pct = (dropped / raw * 100) if raw > 0 else 0
        logger.info(f"  {table:<18} {raw:>10,} {clean:>10,} {dropped:>10,} {pct:>7.1f}%")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("PHASE 1: DATA CLEANING & STAGING")
    logger.info("=" * 60)
    
    engine = get_engine()
    create_schema_if_not_exists(STAGING_SCHEMA, engine)
    
    # Load all raw tables into Pandas DataFrames
    def load_table(table_name: str) -> pd.DataFrame:
        return pd.read_sql(f"SELECT * FROM {RAW_SCHEMA}.{table_name}", engine)
    
    logger.info("Loading raw tables from PostgreSQL...")
    raw = {
        "categories": load_table("categories"),
        "sellers":     load_table("sellers"),
        "customers":   load_table("customers"),
        "products":    load_table("products"),
        "orders":      load_table("orders"),
        "order_items": load_table("order_items"),
        "payments":    load_table("payments"),
        "reviews":     load_table("reviews"),
    }
    raw_counts = {k: len(v) for k, v in raw.items()}
    
    # Clean each table (order matters — parents before children for ref integrity)
    clean_cats     = clean_categories(raw["categories"])
    clean_sellers  = clean_sellers(raw["sellers"])
    clean_custs    = clean_customers(raw["customers"])
    clean_prods    = clean_products(raw["products"])
    
    valid_customer_ids = set(clean_custs["customer_id"])
    valid_product_ids  = set(clean_prods["product_id"])
    valid_seller_ids   = set(clean_sellers["seller_id"])
    
    clean_ords  = clean_orders(raw["orders"], valid_customer_ids, valid_seller_ids)
    valid_order_ids = set(clean_ords["order_id"])
    
    clean_items = clean_order_items(raw["order_items"], valid_order_ids, valid_product_ids)
    clean_pays  = clean_payments(raw["payments"], valid_order_ids)
    clean_revs  = clean_reviews(raw["reviews"], valid_order_ids)
    
    # Save cleaned tables to staging schema
    cleaned = {
        "categories": clean_cats,
        "sellers":    clean_sellers,
        "customers":  clean_custs,
        "products":   clean_prods,
        "orders":     clean_ords,
        "order_items":clean_items,
        "payments":   clean_pays,
        "reviews":    clean_revs,
    }
    
    logger.info("\nSaving cleaned data to staging schema...")
    for table_name, df in cleaned.items():
        # Add cleaning metadata
        df["_cleaned_at"] = pd.Timestamp.now()
        bulk_load_dataframe(
            df=df,
            table_name=table_name,
            engine=engine,
            schema=STAGING_SCHEMA,
            if_exists="replace",
            index=False,
        )
        logger.success(f"  Saved staging.{table_name}: {len(df):,} rows")
    
    # Print quality report
    clean_counts = {k: len(v) for k, v in cleaned.items()}
    generate_quality_report(raw_counts, clean_counts)
    
    logger.success("\nData cleaning complete!")


if __name__ == "__main__":
    main()
