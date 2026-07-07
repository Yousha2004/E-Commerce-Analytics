import pandas as pd
import pytest
import sys
from pathlib import Path

# Add python transform directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python" / "transform"))
from clean_data import clean_products, clean_customers, clean_orders

def test_clean_products():
    """
    Test that the clean_products function correctly:
    - Drops duplicates
    - Caps price at 3000
    - Fixes cost_price > price
    - Fills null stock with 0
    """
    raw_data = pd.DataFrame({
        "product_id": ["P1", "P1", "P2", "P3", "P4"],
        "price": [10.0, 10.0, 5000.0, 100.0, 50.0],
        "cost_price": [5.0, 5.0, 2000.0, 150.0, None], # P3 has cost > price
        "stock_quantity": [10, 10, None, 5, -5],
        "weight_g": [100, 100, 200, 300, 400],
        "is_active": ["true", "true", "0", "false", None],
        "product_name": [" A ", " A ", "B", "C", "D"]
    })
    
    cleaned = clean_products(raw_data)
    
    # Check duplicates dropped (P1 is duplicate)
    assert len(cleaned) == 4
    
    # Check price capping (P2 was 5000)
    assert cleaned.loc[cleaned["product_id"] == "P2", "price"].iloc[0] == 3000.0
    
    # Check cost fix (P3 cost was 150, price 100. Should become 60% of 100 = 60)
    assert cleaned.loc[cleaned["product_id"] == "P3", "cost_price"].iloc[0] == 60.0
    
    # Check stock fill (P2 was null, P4 was -5 -> should be clipped to 0)
    assert cleaned.loc[cleaned["product_id"] == "P2", "stock_quantity"].iloc[0] == 0
    assert cleaned.loc[cleaned["product_id"] == "P4", "stock_quantity"].iloc[0] == 0
    
    # Check booleans
    assert cleaned.loc[cleaned["product_id"] == "P1", "is_active"].iloc[0] == True
    assert cleaned.loc[cleaned["product_id"] == "P2", "is_active"].iloc[0] == False
    assert cleaned.loc[cleaned["product_id"] == "P4", "is_active"].iloc[0] == True # default


def test_clean_customers():
    """
    Test customer cleaning handles emails and duplicates correctly.
    """
    raw_data = pd.DataFrame({
        "customer_id": ["C1", "C2", "C3", "C4"],
        "email": ["valid@test.com", "invalid-email", "dup@test.com", "dup@test.com"],
        "signup_date": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-01"], # C4 signed up before C3
        "first_name": [" a ", "b", "c", "d"],
        "last_name": ["e", "f", "g", "h"],
        "city": [None, "NY", "SF", "SF"],
        "state": ["CA", "NY", "CA", "CA"],
        "is_active": [True, True, True, True]
    })
    
    cleaned = clean_customers(raw_data)
    
    # Invalid email (C2) should be dropped
    assert "C2" not in cleaned["customer_id"].values
    
    # Duplicate email (C3, C4): Should keep the earliest signup (C4)
    assert "C4" in cleaned["customer_id"].values
    assert "C3" not in cleaned["customer_id"].values
    
    # Null city (C1) should be "Unknown"
    assert cleaned.loc[cleaned["customer_id"] == "C1", "city"].iloc[0] == "Unknown"
    
    # Name stripping/title casing
    assert cleaned.loc[cleaned["customer_id"] == "C1", "first_name"].iloc[0] == "A"
