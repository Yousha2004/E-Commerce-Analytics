"""
streamlit_app.py
================
PURPOSE:
    Interactive dashboard built with Streamlit and Plotly.
    Connects directly to the PostgreSQL data warehouse (marts schema).
    Includes Machine Learning forecasting.

HOW TO RUN:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import joblib
from pathlib import Path

# --- Page Config ---
st.set_page_config(
    page_title="E-Commerce Analytics",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Database Connection ---
@st.cache_resource
def get_db_engine():
    load_dotenv()
    user = os.getenv("DB_USER", "ecommerce_user")
    password = os.getenv("DB_PASSWORD", "ecommerce_pass")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    db = os.getenv("DB_NAME", "ecommerce_dw")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)

engine = get_db_engine()


def read_sql_with_engine(query: str):
    """Execute a SQL query through a SQLAlchemy connection."""
    with engine.connect() as conn:
        return pd.read_sql(query, conn)


# --- Data Loading (Cached for Performance) ---
@st.cache_data(ttl=3600)  # Cache data for 1 hour
def load_kpis():
    query = """
    SELECT 
        SUM(gross_revenue) AS total_revenue,
        COUNT(DISTINCT order_id) AS total_orders,
        COUNT(DISTINCT customer_id) AS total_customers,
        SUM(gross_revenue) / NULLIF(COUNT(DISTINCT order_id), 0) AS avg_order_value
    FROM marts.fact_sales
    WHERE is_delivered = TRUE
    """
    return read_sql_with_engine(query).iloc[0]

@st.cache_data(ttl=3600)
def load_monthly_trend():
    query = """
    SELECT d.year_month, SUM(fs.gross_revenue) AS revenue
    FROM marts.fact_sales fs
    JOIN marts.dim_date d ON fs.date_key = d.date_key
    WHERE fs.is_delivered = TRUE
    GROUP BY d.year_month, d.first_day_of_month
    ORDER BY d.first_day_of_month
    """
    return read_sql_with_engine(query)

@st.cache_data(ttl=3600)
def load_top_products():
    query = """
    SELECT p.product_name, SUM(fs.gross_revenue) AS revenue
    FROM marts.fact_sales fs
    JOIN marts.dim_products p USING (product_id)
    WHERE fs.is_delivered = TRUE
    GROUP BY p.product_name
    ORDER BY revenue DESC
    LIMIT 10
    """
    return read_sql_with_engine(query)

@st.cache_data(ttl=3600)
def load_customer_segments():
    query = """
    SELECT customer_segment, COUNT(customer_id) AS customer_count
    FROM marts.dim_customers
    GROUP BY customer_segment
    """
    return read_sql_with_engine(query)

@st.cache_data(ttl=3600)
def load_geo_sales():
    query = """
    SELECT c.state, SUM(f.total_order_value) AS revenue
    FROM marts.fact_orders f
    JOIN marts.dim_customers c USING (customer_id)
    WHERE f.is_delivered = TRUE AND c.state IS NOT NULL
    GROUP BY c.state
    """
    return read_sql_with_engine(query)


@st.cache_data(ttl=3600)
def generate_forecast(days_to_predict=7):
    """Loads model and generates future forecast based on last 30 days of data."""
    try:
        model_dir = Path(__file__).parent.parent / "models"
        model_path = model_dir / "sales_forecasting_rf.joblib"
        features_path = model_dir / "model_features.joblib"
        
        if not model_path.exists():
            return None, "Model file not found. Please train the model first."
            
        model = joblib.load(model_path)
        features_list = joblib.load(features_path)
        
        # Load last 45 days of data to compute lag features safely
        query = """
        SELECT d.date_day, SUM(fs.gross_revenue) AS daily_revenue
        FROM marts.fact_sales fs
        JOIN marts.dim_date d ON fs.date_key = d.date_key
        WHERE fs.is_delivered = TRUE
        GROUP BY d.date_day
        ORDER BY d.date_day DESC
        LIMIT 45
        """
        df = read_sql_with_engine(query)
        df['date_day'] = pd.to_datetime(df['date_day'])
        df = df.sort_values('date_day').set_index('date_day')
        
        if len(df) < 20:
            return None, "Not enough historical data to generate forecast."
            
        historical = df.copy()
        
        # Predict one day at a time iteratively to update lags
        predictions = []
        last_date = df.index[-1]
        
        for i in range(days_to_predict):
            # Compute features for the next day
            next_date = last_date + pd.Timedelta(days=1)
            
            # Need lag_1, lag_7, lag_14, rolling_mean_7d, rolling_std_7d
            # Let's extract values
            lag_1 = df['daily_revenue'].iloc[-1]
            lag_7 = df['daily_revenue'].iloc[-7] if len(df) >= 7 else lag_1
            lag_14 = df['daily_revenue'].iloc[-14] if len(df) >= 14 else lag_1
            
            rolling_mean_7d = df['daily_revenue'].iloc[-7:].mean()
            rolling_std_7d = df['daily_revenue'].iloc[-7:].std()
            
            # Create feature row exactly matching model training
            feature_row = pd.DataFrame([{
                'lag_1': lag_1,
                'lag_7': lag_7,
                'lag_14': lag_14,
                'rolling_mean_7d': rolling_mean_7d,
                'rolling_std_7d': rolling_std_7d
            }])
            
            # Reorder columns to match model training
            feature_row = feature_row[features_list]
            
            # Predict
            pred = model.predict(feature_row)[0]
            predictions.append({'date_day': next_date, 'daily_revenue': pred})
            
            # Add to df for next iteration's lags
            df.loc[next_date] = [pred]
            last_date = next_date
            
        pred_df = pd.DataFrame(predictions).set_index('date_day')
        return historical.tail(30), pred_df
        
    except Exception as e:
        return None, str(e)


# --- UI Layout ---

st.title("🛒 E-Commerce Analytics Platform")
st.markdown("Live dashboard connected to PostgreSQL Data Warehouse.")

# Load Data
with st.spinner("Loading data from warehouse..."):
    try:
        kpis = load_kpis()
        trend_df = load_monthly_trend()
        products_df = load_top_products()
        segments_df = load_customer_segments()
        geo_df = load_geo_sales()
        db_connected = True
    except Exception as e:
        st.error(f"Could not connect to database: {e}")
        st.info("Make sure Docker is running and data is loaded.")
        db_connected = False

if db_connected:
    tab1, tab2 = st.tabs(["Business Intelligence", "Machine Learning Forecast"])
    
    with tab1:
        # 1. KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Revenue", f"${kpis['total_revenue']:,.0f}")
        col2.metric("Total Orders", f"{kpis['total_orders']:,}")
        col3.metric("Total Customers", f"{kpis['total_customers']:,}")
        col4.metric("Avg Order Value", f"${kpis['avg_order_value']:,.2f}")
        
        st.markdown("---")
        
        # 2. Charts (Row 1)
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("Monthly Sales Trend")
            fig_trend = px.line(trend_df, x="year_month", y="revenue", markers=True, 
                                labels={"year_month": "Month", "revenue": "Revenue ($)"})
            fig_trend.update_layout(yaxis_tickformat="$,.0f")
            st.plotly_chart(fig_trend, use_container_width=True)
            
        with col_right:
            st.subheader("Customer Segments (RFM)")
            fig_seg = px.pie(segments_df, values="customer_count", names="customer_segment", hole=0.4)
            st.plotly_chart(fig_seg, use_container_width=True)

        # 3. Charts (Row 2)
        col_left2, col_right2 = st.columns(2)
        
        with col_left2:
            st.subheader("Top 10 Products by Revenue")
            fig_prod = px.bar(products_df, x="revenue", y="product_name", orientation='h',
                              labels={"product_name": "", "revenue": "Revenue ($)"})
            fig_prod.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat="$,.0f")
            st.plotly_chart(fig_prod, use_container_width=True)
            
        with col_right2:
            st.subheader("Revenue by State")
            fig_geo = px.bar(geo_df.sort_values('revenue', ascending=False).head(10), 
                             x="state", y="revenue",
                             labels={"state": "State", "revenue": "Revenue ($)"})
            fig_geo.update_layout(yaxis_tickformat="$,.0f")
            st.plotly_chart(fig_geo, use_container_width=True)

    with tab2:
        st.header("📈 7-Day Revenue Forecast")
        st.markdown("Uses a trained Random Forest Regressor to predict upcoming revenue based on historical lag features.")
        
        historical, forecast_or_error = generate_forecast(7)
        
        if isinstance(forecast_or_error, str):
            st.warning(forecast_or_error)
            st.info("Run `python python/ml/train_model.py` to generate the model artifact first.")
        else:
            pred_df = forecast_or_error
            
            fig = go.Figure()
            
            # Historical line
            fig.add_trace(go.Scatter(
                x=historical.index, 
                y=historical['daily_revenue'],
                mode='lines+markers',
                name='Historical Revenue',
                line=dict(color='#1f77b4', width=2)
            ))
            
            # Forecast line
            # Connect the last historical point to the first forecast point visually
            conn_x = [historical.index[-1], pred_df.index[0]]
            conn_y = [historical.iloc[-1]['daily_revenue'], pred_df.iloc[0]['daily_revenue']]
            
            fig.add_trace(go.Scatter(
                x=conn_x, 
                y=conn_y,
                mode='lines',
                showlegend=False,
                line=dict(color='#ff7f0e', width=2, dash='dash')
            ))
            
            fig.add_trace(go.Scatter(
                x=pred_df.index, 
                y=pred_df['daily_revenue'],
                mode='lines+markers',
                name='Predicted Revenue',
                line=dict(color='#ff7f0e', width=2, dash='dash')
            ))
            
            fig.update_layout(
                title="Historical vs Predicted Daily Revenue",
                xaxis_title="Date",
                yaxis_title="Revenue ($)",
                yaxis_tickformat="$,.0f",
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Show data table
            st.subheader("Predicted Values Table")
            display_df = pred_df.copy()
            display_df.index = display_df.index.strftime('%Y-%m-%d')
            display_df['daily_revenue'] = display_df['daily_revenue'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(display_df, use_container_width=True)
