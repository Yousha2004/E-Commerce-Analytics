"""
dbt_run_dag.py
==============
PURPOSE:
    Airflow DAG that triggers dbt models AFTER the ingestion pipeline
    (ecommerce_pipeline) completes successfully.

HOW DAG DEPENDENCIES WORK IN AIRFLOW:
    We use ExternalTaskSensor to wait for the main pipeline DAG to finish.
    This is the Airflow way to create cross-DAG dependencies.
    
    Execution order:
    1. ecommerce_pipeline DAG runs at 2:00 AM (loads raw + staging)
    2. dbt_run_dag runs at 3:00 AM (builds marts from staging)
    
    WHY SEPARATE DAGS?
    - Each DAG can be triggered/retried independently
    - The dbt DAG can be re-run without re-ingesting raw data
    - Better observability in the Airflow UI

dbt COMMANDS EXPLAINED:
    dbt run  → Executes all SQL model files (creates/replaces tables/views)
    dbt test → Runs data quality tests defined in schema.yml
    dbt docs generate → Builds HTML documentation for all models
    
    The BashOperator runs these as shell commands because dbt is a
    command-line tool, not a Python library.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.trigger_rule import TriggerRule


default_args = {
    "owner": "ecommerce_team",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
    "execution_timeout": timedelta(hours=1),
}

dag = DAG(
    dag_id="ecommerce_dbt_run",
    description="Run dbt models after ingestion pipeline completes",
    default_args=default_args,
    schedule_interval="0 3 * * *",  # 1 hour after ingestion DAG (3:00 AM)
    catchup=False,
    max_active_runs=1,
    tags=["ecommerce", "dbt", "transformation"],
    doc_md="""
    ## dbt Model Execution DAG
    
    Triggered after the main ingestion pipeline. Runs all dbt models
    to build the analytical marts layer (facts + dimensions).
    
    **Models built:**
    - `marts.fact_orders` — Order-level facts
    - `marts.fact_sales` — Revenue facts with product/seller details
    - `marts.dim_customers` — Customer dimension
    - `marts.dim_products` — Product dimension  
    - `marts.dim_sellers` — Seller dimension
    - `marts.dim_date` — Date dimension (spine)
    
    **Tests run:** not_null, unique, accepted_values, relationships
    """,
)

# dbt project is mounted at /opt/airflow/dbt in the container
# (add this volume in docker-compose.yml)
DBT_PROJECT_DIR = "/opt/airflow/dbt"
DBT_PROFILES_DIR = "/opt/airflow/dbt"

with dag:
    
    # Wait for the ingestion DAG to finish on the same day
    wait_for_ingestion = ExternalTaskSensor(
        task_id="wait_for_ingestion_pipeline",
        external_dag_id="ecommerce_pipeline",
        external_task_id="end",
        execution_delta=timedelta(hours=1),  # ingestion runs 1 hour earlier
        timeout=3600,          # Wait up to 1 hour for it to finish
        mode="reschedule",     # Don't block a worker slot while waiting
        poke_interval=60,      # Check every 60 seconds
    )
    
    # Install dbt packages (defined in packages.yml)
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt deps --profiles-dir {DBT_PROFILES_DIR}",
    )
    
    # Run all dbt models
    # --select: run ALL models in the project
    # --target prod: use production connection profile
    dbt_run = BashOperator(
        task_id="dbt_run_all_models",
        bash_command=f"""
            cd {DBT_PROJECT_DIR} && 
            dbt run \
                --profiles-dir {DBT_PROFILES_DIR} \
                --target prod \
                --full-refresh \
                --select staging+ \
                2>&1
        """,
    )
    
    # Run data quality tests defined in schema.yml
    # Tests include: not_null, unique, accepted_values, relationships
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"""
            cd {DBT_PROJECT_DIR} && 
            dbt test \
                --profiles-dir {DBT_PROFILES_DIR} \
                --target prod \
                2>&1
        """,
    )
    
    # Generate documentation (HTML site with lineage graph)
    dbt_docs = BashOperator(
        task_id="dbt_generate_docs",
        bash_command=f"""
            cd {DBT_PROJECT_DIR} && 
            dbt docs generate \
                --profiles-dir {DBT_PROFILES_DIR} \
                --target prod \
                2>&1
        """,
    )
    
    # Final status task (shows green/red in Airflow UI)
    pipeline_complete = EmptyOperator(
        task_id="dbt_pipeline_complete",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )
    
    # Task execution order
    wait_for_ingestion >> dbt_deps >> dbt_run >> dbt_test >> dbt_docs >> pipeline_complete
