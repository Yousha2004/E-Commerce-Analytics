"""
evaluate_model.py
=================
PURPOSE:
    Loads the trained Random Forest model and generates a plot of
    Predictions vs Actuals for the last 30 days.
    This provides visual confirmation that the model works.

OUTPUT:
    Saves a PNG graph to the docs/ directory.
"""

import sys
import os
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
from loguru import logger

from train_model import load_daily_sales_data, engineer_features

# Paths
MODEL_DIR = Path(__file__).parent.parent.parent / "models"
MODEL_PATH = MODEL_DIR / "sales_forecasting_rf.joblib"
FEATURES_PATH = MODEL_DIR / "model_features.joblib"
DOCS_DIR = Path(__file__).parent.parent.parent / "docs"


def evaluate():
    logger.info("Loading model for evaluation...")
    
    if not MODEL_PATH.exists():
        logger.error(f"Model file not found at {MODEL_PATH}")
        logger.info("Run python/ml/train_model.py first!")
        sys.exit(1)
        
    model = joblib.load(MODEL_PATH)
    features = joblib.load(FEATURES_PATH)
    
    # Load and prep data
    raw_df = load_daily_sales_data()
    df = engineer_features(raw_df)
    
    X = df[features]
    y = df["daily_revenue"]
    
    # We want to plot the last 60 days (30 train, 30 test) to show context
    plot_days = 60
    test_days = 30
    
    X_plot = X.iloc[-plot_days:]
    y_true = y.iloc[-plot_days:]
    
    # Predict all 60 days
    y_pred = model.predict(X_plot)
    
    # Create a DataFrame for plotting
    results = pd.DataFrame({
        "Actual Revenue": y_true,
        "Predicted Revenue": y_pred
    }, index=y_true.index)
    
    # --- Plotting ---
    logger.info("Generating predictions plot...")
    
    # Set style
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(14, 6))
    
    # Plot Actuals
    plt.plot(results.index, results["Actual Revenue"], label="Actual Revenue", marker='o', color='#1f77b4', linewidth=2)
    
    # Plot Predictions
    plt.plot(results.index, results["Predicted Revenue"], label="Predicted Revenue", marker='x', color='#ff7f0e', linewidth=2, linestyle='--')
    
    # Add a vertical line to separate Train and Test (unseen) data
    test_start_date = results.index[-test_days]
    plt.axvline(x=test_start_date, color='red', linestyle=':', label="Test Set Start (Unseen Data)")
    
    # Formatting
    plt.title("Sales Forecasting: Actual vs. Predicted Revenue (Last 60 Days)", fontsize=16, pad=15)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Daily Revenue ($)", fontsize=12)
    
    # Format y-axis as dollars
    current_values = plt.gca().get_yticks()
    plt.gca().set_yticklabels(['${:,.0f}'.format(x) for x in current_values])
    
    plt.legend(fontsize=12)
    plt.tight_layout()
    
    # Save the plot
    os.makedirs(DOCS_DIR, exist_ok=True)
    plot_path = DOCS_DIR / "forecast_evaluation.png"
    plt.savefig(plot_path, dpi=300)
    logger.success(f"Evaluation plot saved to: {plot_path}")
    
    # Optional: show plot if running interactively
    # plt.show()


if __name__ == "__main__":
    evaluate()
