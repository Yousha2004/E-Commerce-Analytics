"""
train_model.py
==============
PURPOSE:
    Trains a Machine Learning model to forecast future daily sales (revenue).
    This script is the production version of our ML training pipeline.
    
    It reads historical sales data from the data warehouse, performs
    feature engineering (adding lag features and rolling averages),
    trains a Random Forest Regressor, and saves the trained model to disk.

MODEL:
    RandomForestRegressor (from scikit-learn).
    Why? It handles non-linear relationships well (like day-of-week effects)
    and is robust to outliers without needing extensive scaling.

HOW TO RUN:
    python python/ml/train_model.py
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
from loguru import logger
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Import DB utils
sys.path.insert(0, str(Path(__file__).parent.parent / "ingest"))
from db_utils import get_engine

# Output directory for the saved model
MODEL_DIR = Path(__file__).parent.parent.parent / "models"
MODEL_PATH = MODEL_DIR / "sales_forecasting_rf.joblib"


def load_daily_sales_data() -> pd.DataFrame:
    """
    Fetches aggregated daily sales from the data warehouse.
    We join fact_sales with dim_date to get clean calendar features.
    """
    logger.info("Fetching historical daily sales from data warehouse...")
    engine = get_engine()
    
    query = """
        SELECT
            d.date_day,
            d.year,
            d.month_number,
            d.day_of_week,
            d.day_of_month,
            d.is_weekend,
            
            -- Target variable (what we want to predict)
            SUM(fs.gross_revenue) AS daily_revenue,
            
            -- Other potential features
            COUNT(DISTINCT fs.order_id) AS total_orders
        FROM marts.fact_sales fs
        JOIN marts.dim_date d ON fs.date_key = d.date_key
        WHERE fs.is_delivered = TRUE
        GROUP BY 1, 2, 3, 4, 5, 6
        ORDER BY d.date_day
    """
    
    df = pd.read_sql(query, engine)
    df["date_day"] = pd.to_datetime(df["date_day"])
    df.set_index("date_day", inplace=True)
    
    logger.info(f"Loaded {len(df)} days of historical data")
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Feature Engineering: Creating new columns that help the model learn patterns.
    
    TIME-SERIES FEATURES:
    - Lag 7: What were sales exactly one week ago?
    - Lag 14: What were sales exactly two weeks ago?
    - Rolling 7-day mean: What is the short-term trend?
    """
    logger.info("Engineering time-series features...")
    df = df.copy()
    
    # Lag features (past values)
    df["lag_1"] = df["daily_revenue"].shift(1)
    df["lag_7"] = df["daily_revenue"].shift(7)
    df["lag_14"]= df["daily_revenue"].shift(14)
    
    # Rolling window features (trends)
    df["rolling_mean_7d"] = df["daily_revenue"].shift(1).rolling(window=7).mean()
    df["rolling_std_7d"]  = df["daily_revenue"].shift(1).rolling(window=7).std()
    
    # Drop rows with NaN values created by shifting/rolling
    df.dropna(inplace=True)
    
    logger.info(f"Features created. Dataset shape after dropping NaNs: {df.shape}")
    return df


def train_model():
    """
    Main training pipeline.
    """
    print("=" * 60)
    print("PHASE 5: ML MODEL TRAINING (SALES FORECASTING)")
    print("=" * 60)
    
    # 1. Load and prepare data
    raw_df = load_daily_sales_data()
    
    if len(raw_df) < 30:
        logger.error("Not enough historical data to train a model. Need at least 30 days.")
        sys.exit(1)
        
    df = engineer_features(raw_df)
    
    # 2. Define features (X) and target (y)
    target = "daily_revenue"
    
    # Exclude target and non-predictive columns from features
    # 'total_orders' is excluded because we won't know tomorrow's orders today!
    features = [col for col in df.columns if col not in [target, "total_orders"]]
    
    X = df[features]
    y = df[target]
    
    # 3. Train-Test Split (Time-Series Split)
    # Never use random train_test_split for time-series! It causes data leakage.
    # We train on the past, test on the future (last 30 days).
    test_days = 30
    X_train, X_test = X.iloc[:-test_days], X.iloc[-test_days:]
    y_train, y_test = y.iloc[:-test_days], y.iloc[-test_days:]
    
    logger.info(f"Training on {len(X_train)} days, evaluating on {len(X_test)} days")
    
    # 4. Train the Random Forest Model
    logger.info("Training RandomForestRegressor...")
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1  # Use all CPU cores
    )
    
    model.fit(X_train, y_train)
    
    # 5. Evaluate the Model
    logger.info("Evaluating model on test set (unseen future data)...")
    y_pred = model.predict(X_test)
    
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    print("\n--- Model Performance on Last 30 Days ---")
    print(f"MAE  (Mean Absolute Error): ${mae:,.2f}")
    print(f"RMSE (Root Mean Sq Error) : ${rmse:,.2f}")
    print(f"R²   (Explained Variance) : {r2:.4f} (Higher is better, max 1.0)")
    print("-----------------------------------------")
    
    # Feature Importance (what drives sales?)
    importances = pd.Series(model.feature_importances_, index=features).sort_values(ascending=False)
    print("\nTop 5 Most Important Features:")
    for feature, imp in importances.head(5).items():
        print(f"  - {feature:<20} {imp:.2%}")
    
    # 6. Save the model to disk
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    logger.success(f"\nModel saved successfully to {MODEL_PATH}")
    
    # Also save the features list so the evaluation script knows what to use
    joblib.dump(features, MODEL_DIR / "model_features.joblib")


if __name__ == "__main__":
    train_model()
