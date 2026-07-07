"""
architecture_diagram.py
=======================
PURPOSE:
    Generates the architecture diagram for the README using the Python 'diagrams' library.
    
HOW TO RUN:
    pip install diagrams
    python docs/architecture_diagram.py
    (Note: requires Graphviz installed on your system: https://graphviz.org/download/)
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.workflow import Airflow
from diagrams.custom import Custom
from diagrams.onprem.analytics import Dbt
from diagrams.programming.python import Python
from diagrams.onprem.client import Users

# Note: Custom icons would normally be used for Power BI / Streamlit / CSV
# Using standard nodes where possible to avoid missing image errors

def generate_diagram():
    with Diagram("E-Commerce Analytics Platform", show=False, filename="architecture", direction="LR"):
        
        user = Users("Data Team / Stakeholders")
        
        with Cluster("Phase 1: Ingestion (Python)"):
            csv = Python("Raw CSV Data")
            ingest = Python("Load & Clean Scripts")
            csv >> ingest
            
        with Cluster("Data Warehouse (PostgreSQL)"):
            with Cluster("Raw Layer"):
                db_raw = PostgreSQL("Raw Schema")
            with Cluster("Staging Layer"):
                db_staging = PostgreSQL("Staging Schema")
            with Cluster("Analytical Layer (Star Schema)"):
                db_marts = PostgreSQL("Marts Schema")
                
            ingest >> Edge(label="pandas.to_sql") >> db_raw
            db_raw >> Edge(label="clean_data.py") >> db_staging
            
        with Cluster("Phase 3: Transformation (dbt)"):
            dbt = Dbt("dbt Models")
            
        db_staging >> Edge(label="staging models") >> dbt
        dbt >> Edge(label="incremental facts & dims") >> db_marts
        
        with Cluster("Phase 2: Orchestration"):
            airflow = Airflow("Apache Airflow\n(Daily DAGs)")
            airflow >> Edge(color="firebrick", style="dashed") >> ingest
            airflow >> Edge(color="firebrick", style="dashed") >> dbt
            
        with Cluster("Phase 5: Machine Learning"):
            ml = Python("Random Forest\nSales Forecasting")
            
        with Cluster("Phase 6: BI & Dashboards"):
            powerbi = Python("Streamlit / Power BI\nDashboards")
            sql = Python("SQL Analytics")
            
        db_marts >> Edge(label="SQL queries") >> sql
        db_marts >> Edge(label="DirectQuery") >> powerbi
        db_marts >> Edge(label="Historical Sales") >> ml
        ml >> Edge(label="Forecasts") >> powerbi
        
        powerbi >> user
        sql >> user

if __name__ == "__main__":
    try:
        generate_diagram()
        print("Diagram generated successfully at architecture.png")
    except Exception as e:
        print(f"Failed to generate diagram: {e}")
        print("Ensure 'diagrams' package and Graphviz are installed.")
