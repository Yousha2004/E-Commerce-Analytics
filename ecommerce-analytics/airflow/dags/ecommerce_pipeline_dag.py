"""
ecommerce_pipeline_dag.py
=========================
PURPOSE:
    Main Apache Airflow DAG that orchestrates the entire e-commerce pipeline
    from synthetic data generation through raw loading, cleaning, dbt modeling,
    ML training, and validation.
"""

from datetime import datetime, timedelta
import os
import subprocess
import sys

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.trigger_rule import TriggerRule


default_args = {
    "owner": "ecommerce_team",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


dag = DAG(
    dag_id="ecommerce_pipeline",
    description="End-to-end ETL/ML pipeline: generate → load → clean → dbt → train → validate",
    default_args=default_args,
    schedule_interval="0 2 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["ecommerce", "etl", "ml", "daily"],
)

PYTHON_DIR = "/opt/airflow/python"
DBT_DIR = "/opt/airflow/dbt"
DATA_DIR = "/opt/airflow/data/raw"
MODELS_DIR = "/opt/airflow/models"
MODEL_PATH = os.path.join(MODELS_DIR, "sales_forecasting_rf.joblib")


def task_check_source_files(**context):
    """Verify required source CSV files are present."""
    required_files = [
        "categories.csv", "sellers.csv", "customers.csv", "products.csv",
        "orders.csv", "order_items.csv", "payments.csv", "reviews.csv",
    ]

    missing = []
    found = []
    for filename in required_files:
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            found.append(f"{filename} ({os.path.getsize(path):,} bytes)")
        else:
            missing.append(filename)

    print(f"✓ Found {len(found)} files")
    for item in found:
        print(f"  - {item}")

    if missing:
        print(f"\n✗ Missing {len(missing)} files")
        for item in missing:
            print(f"  - {item}")
        context["task_instance"].xcom_push(key="files_missing", value=True)
    else:
        context["task_instance"].xcom_push(key="files_missing", value=False)


def task_should_generate(**context):
    """Branch to generate data when source files are missing."""
    ti = context["task_instance"]
    files_missing = ti.xcom_pull(task_ids="check_source_files", key="files_missing")
    if files_missing:
        print("Files missing — generating dataset")
        return "generate_dataset"
    print("Files present — skipping generation")
    return "load_raw_data"


def task_generate_dataset(**context):
    """Generate a fresh rolling two-year synthetic dataset."""
    print("Generating synthetic e-commerce dataset...")
    result = subprocess.run(
        [sys.executable, f"{PYTHON_DIR}/ingest/generate_dataset.py"],
        capture_output=True,
        text=True,
        timeout=600,
        env={**os.environ, "PYTHONPATH": PYTHON_DIR},
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        raise RuntimeError("Dataset generation failed")


def task_load_raw_data(**context):
    """Load CSV files into PostgreSQL raw schema."""
    print("Loading raw CSV files into PostgreSQL...")
    result = subprocess.run(
        [sys.executable, f"{PYTHON_DIR}/ingest/load_raw.py"],
        capture_output=True,
        text=True,
        timeout=1200,
        env={**os.environ, "PYTHONPATH": PYTHON_DIR},
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        raise RuntimeError("Raw data loading failed")


def task_validate_raw_counts(**context):
    """Validate the raw tables before cleaning."""
    min_counts = {
        "categories": 10,
        "sellers": 50,
        "customers": 500,
        "products": 100,
        "orders": 1000,
        "order_items": 1000,
        "payments": 1000,
        "reviews": 100,
    }

    hook = PostgresHook(postgres_conn_id="postgres_ecommerce")
    failures = []
    for table, minimum in min_counts.items():
        actual = hook.get_first(f"SELECT COUNT(*) FROM raw.{table}")[0]
        print(f"  raw.{table}: {actual:,} rows (min: {minimum:,})")
        if actual < minimum:
            failures.append(f"raw.{table} has {actual} rows")

    if failures:
        raise ValueError("Raw data validation failed:\n" + "\n".join(failures))


def task_clean_and_stage(**context):
    """Clean the raw data and populate the staging schema."""
    print("Running cleaning pipeline...")
    result = subprocess.run(
        [sys.executable, f"{PYTHON_DIR}/transform/clean_data.py"],
        capture_output=True,
        text=True,
        timeout=1200,
        env={**os.environ, "PYTHONPATH": PYTHON_DIR},
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        raise RuntimeError("Data cleaning failed")


def task_validate_staging(**context):
    """Confirm staging data is ready for dbt transformations."""
    hook = PostgresHook(postgres_conn_id="postgres_ecommerce")
    critical_checks = [
        ("staging.orders", "order_id IS NULL OR customer_id IS NULL OR order_date IS NULL"),
        ("staging.order_items", "order_item_id IS NULL OR total_price <= 0"),
        ("staging.customers", "customer_id IS NULL OR email IS NULL"),
    ]

    failures = []
    for table, condition in critical_checks:
        count = hook.get_first(f"SELECT COUNT(*) FROM {table} WHERE {condition}")[0]
        print(f"  {table} bad rows: {count}")
        if count > 0:
            failures.append(f"{table}: {count} bad rows")

    orphans = hook.get_first("""
        SELECT COUNT(*) FROM staging.order_items oi
        WHERE NOT EXISTS (SELECT 1 FROM staging.orders o WHERE o.order_id = oi.order_id)
    """)[0]
    if orphans > 0:
        failures.append(f"staging.order_items orphan rows: {orphans}")

    if failures:
        raise ValueError("Staging validation failed:\n" + "\n".join(failures))


def task_run_dbt_build(**context):
    """Run the dbt build command for staging and marts models."""
    print("Running dbt build...")
    result = subprocess.run(
        ["dbt", "build", "--project-dir", DBT_DIR, "--profiles-dir", DBT_DIR],
        cwd=DBT_DIR,
        capture_output=True,
        text=True,
        timeout=1800,
        env={**os.environ, "PYTHONPATH": PYTHON_DIR},
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        raise RuntimeError("dbt build failed")


def task_train_ml_model(**context):
    """Train the sales forecasting model."""
    print("Training machine learning model...")
    result = subprocess.run(
        [sys.executable, f"{PYTHON_DIR}/ml/train_model.py"],
        capture_output=True,
        text=True,
        timeout=1800,
        env={**os.environ, "PYTHONPATH": PYTHON_DIR},
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        raise RuntimeError("ML training failed")


def task_validate_success(**context):
    """Validate the downstream outputs and model artifact."""
    hook = PostgresHook(postgres_conn_id="postgres_ecommerce")
    fact_sales_count = hook.get_first("SELECT COUNT(*) FROM marts.fact_sales")[0]
    dim_customer_count = hook.get_first("SELECT COUNT(*) FROM marts.dim_customers")[0]
    model_exists = os.path.exists(MODEL_PATH)

    print(f"  marts.fact_sales rows: {fact_sales_count:,}")
    print(f"  marts.dim_customers rows: {dim_customer_count:,}")
    print(f"  model artifact exists: {model_exists}")

    if fact_sales_count <= 0 or dim_customer_count <= 0 or not model_exists:
        raise ValueError("Pipeline validation failed: expected marts tables and ML model artifact")


with dag:
    start = EmptyOperator(task_id="start")

    check_files = PythonOperator(
        task_id="check_source_files",
        python_callable=task_check_source_files,
    )

    branch = BranchPythonOperator(
        task_id="should_generate_data",
        python_callable=task_should_generate,
    )

    generate = PythonOperator(
        task_id="generate_dataset",
        python_callable=task_generate_dataset,
    )

    load_raw = PythonOperator(
        task_id="load_raw_data",
        python_callable=task_load_raw_data,
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    validate_raw = PythonOperator(
        task_id="validate_raw_counts",
        python_callable=task_validate_raw_counts,
    )

    clean_stage = PythonOperator(
        task_id="clean_and_stage_data",
        python_callable=task_clean_and_stage,
    )

    validate_staging = PythonOperator(
        task_id="validate_staging_counts",
        python_callable=task_validate_staging,
    )

    run_dbt = PythonOperator(
        task_id="run_dbt_build",
        python_callable=task_run_dbt_build,
    )

    train_model = PythonOperator(
        task_id="train_ml_model",
        python_callable=task_train_ml_model,
    )

    validate_success = PythonOperator(
        task_id="validate_success",
        python_callable=task_validate_success,
    )

    end = EmptyOperator(
        task_id="end",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    start >> check_files >> branch
    branch >> generate >> load_raw
    branch >> load_raw
    load_raw >> validate_raw >> clean_stage >> validate_staging >> run_dbt >> train_model >> validate_success >> end
