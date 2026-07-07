# 🛒 E-Commerce Analytics Platform

An end-to-end Data Engineering, Analytics, and Machine Learning platform that automates the complete analytics pipeline for an e-commerce business.

The project demonstrates modern ELT architecture using Python, PostgreSQL, dbt, Apache Airflow, Streamlit, and Machine Learning to generate business insights and revenue forecasts.

---

# 🚀 Features

- Synthetic e-commerce dataset generation
- Automated ETL/ELT pipeline
- PostgreSQL Data Warehouse
- Data Cleaning & Validation
- dbt Transformations
- Star Schema Data Modeling
- Apache Airflow Orchestration
- Interactive Streamlit Dashboard
- Revenue Forecasting using Machine Learning
- Automated Data Quality Tests
- Dockerized Deployment

---

# 🏗️ Architecture

```text
                    Synthetic Data Generator
                              │
                              ▼
                     Raw CSV Dataset
                              │
                              ▼
                  PostgreSQL (Raw Schema)
                              │
                              ▼
                  Python Data Cleaning
                              │
                              ▼
                PostgreSQL (Staging Schema)
                              │
                              ▼
                      dbt Transformations
                              │
                              ▼
                   Analytics Mart Schema
                              │
          ┌───────────────────┴───────────────────┐
          ▼                                       ▼
   Machine Learning                     Streamlit Dashboard
 (Revenue Forecasting)              Business Intelligence
                              │
                              ▼
                      Business Insights
```

---

# 📂 Project Structure

```text
ecommerce-analytics/
│
├── airflow/
│   └── dags/
│
├── dashboard/
│   └── streamlit_app.py
│
├── database/
│   └── schema.sql
│
├── data/
│   ├── raw/
│   └── processed/
│
├── dbt/
│   ├── models/
│   ├── macros/
│   └── profiles.yml
│
├── python/
│   ├── ingest/
│   ├── transform/
│   └── ml/
│
├── tests/
│
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

# 🛠️ Tech Stack

### Languages

- Python
- SQL

### Data Engineering

- PostgreSQL
- dbt
- Apache Airflow
- Pandas
- SQLAlchemy

### Machine Learning

- Scikit-Learn
- Random Forest
- Joblib

### Dashboard

- Streamlit
- Plotly

### DevOps

- Docker
- Docker Compose

### Testing

- Pytest

---

# ⚙️ Pipeline Workflow

## 1️⃣ Dataset Generation

Generates realistic two years of e-commerce transactional data including

- Customers
- Products
- Categories
- Sellers
- Orders
- Order Items
- Payments
- Reviews

---

## 2️⃣ Raw Data Loading

Loads CSV files into PostgreSQL using optimized bulk loading.

---

## 3️⃣ Data Cleaning

Performs

- Null handling
- Duplicate removal
- Referential integrity checks
- Data validation
- Standardization

---

## 4️⃣ Data Modeling

Uses dbt to create

- Fact Tables
- Dimension Tables
- Analytics Mart

---

## 5️⃣ Machine Learning

Builds a Random Forest regression model to forecast future revenue using engineered time-series features.

---

## 6️⃣ Dashboard

Interactive dashboard providing

- Revenue Overview
- Sales Trends
- Product Performance
- Customer Analytics
- Geographic Insights
- Revenue Forecast

---

## 7️⃣ Orchestration

Apache Airflow automates the complete workflow:

```
Generate Dataset
      ↓
Load Raw Data
      ↓
Clean Data
      ↓
dbt Build
      ↓
Train ML Model
      ↓
Validate Pipeline
```

---

# 📊 Dashboard

The Streamlit dashboard provides

- KPI Cards
- Revenue Trends
- Category Analysis
- Product Insights
- Customer Segmentation
- Geographic Sales
- ML Revenue Forecast

---

# 🧠 Machine Learning

Algorithm

- Random Forest Regressor

Features

- Revenue history
- Time-based feature engineering
- Lag Features
- Rolling Statistics

Output

- 7-Day Revenue Forecast

---

# ✅ Data Quality

The project includes

- Unit Tests
- dbt Tests
- Schema Validation
- Referential Integrity Checks
- Automated Cleaning Rules

---

# 🐳 Running the Project

## Clone Repository

```bash
git clone https://github.com/<your-username>/ecommerce-analytics-platform.git

cd ecommerce-analytics-platform
```

---

## Start Docker

```bash
docker compose up -d
```

---

## Generate Dataset

```bash
python python/ingest/generate_dataset.py
```

---

## Load Raw Data

```bash
python python/ingest/load_raw.py
```

---

## Clean Data

```bash
python python/transform/clean_data.py
```

---

## Build dbt Models

```bash
cd dbt

dbt build
```

---

## Train Machine Learning Model

```bash
python python/ml/train_model.py
```

---

## Launch Dashboard

```bash
streamlit run dashboard/streamlit_app.py
```

---

# 📈 Future Improvements

- CI/CD Pipeline using GitHub Actions
- Cloud Deployment (AWS/GCP/Azure)
- Real-time Streaming with Kafka
- Docker Swarm / Kubernetes
- ML Experiment Tracking (MLflow)
- Data Drift Monitoring
- Automated Model Retraining

---

# 🎯 Skills Demonstrated

- Data Engineering
- Data Warehousing
- ETL / ELT Pipelines
- SQL Optimization
- Machine Learning
- Data Analytics
- Dashboard Development
- MLOps
- Airflow
- dbt
- Docker
- PostgreSQL
- Streamlit
