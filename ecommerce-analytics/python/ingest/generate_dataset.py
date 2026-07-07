"""
generate_dataset.py
===================
PURPOSE:
    Generates a realistic synthetic e-commerce dataset with 7 CSV files.
    Uses Faker to create realistic names, addresses, and text.
    Uses numpy/random for realistic statistical distributions.

WHY SYNTHETIC DATA?
    Real e-commerce data (like Amazon sales) is confidential.
    A well-generated synthetic dataset is just as impressive for a portfolio
    because it tests the same pipeline with realistic patterns:
    - Seasonal sales peaks (November/December)
    - Power-law product popularity (a few products sell much more)
    - Geographic clustering (metro areas buy more)

HOW TO RUN:
    python python/ingest/generate_dataset.py

OUTPUT:
    Creates 7 CSV files in data/raw/
"""

import os
import random
import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta
from loguru import logger

# ── Configuration ──────────────────────────────────────────────────────────────
# Set seed so the dataset is reproducible (same data every time you run)
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker("en_US")
Faker.seed(SEED)

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")

# Dataset sizes — tuned to feel realistic at portfolio scale
NUM_CUSTOMERS = 5_000
NUM_SELLERS   = 200
NUM_CATEGORIES = 32
NUM_PRODUCTS  = 1_500
NUM_ORDERS    = 12_000   # Each order links to 1+ order items
NUM_REVIEWS   = 8_000

# Date range for the dataset (rolling 2 years ending today)
END_DATE = datetime.now()
START_DATE = END_DATE - timedelta(days=730)

# Brazilian-style state codes (common e-commerce dataset style, like Olist)
STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "CE", "PE", "GO",
          "ES", "AM", "PA", "MA", "PB", "MT", "MS", "RN", "AL", "SE"]

# Weighted states — São Paulo has far more customers than smaller states
STATE_WEIGHTS = [0.35, 0.15, 0.12, 0.08, 0.07, 0.06, 0.04, 0.03, 0.03, 0.02,
                 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.005, 0.005, 0.005]

ORDER_STATUSES = ["delivered", "shipped", "processing", "cancelled", "pending"]
STATUS_WEIGHTS = [0.72, 0.10, 0.08, 0.06, 0.04]  # Most orders are delivered

PAYMENT_TYPES = ["credit_card", "boleto", "debit_card", "voucher"]
PAYMENT_WEIGHTS = [0.60, 0.20, 0.15, 0.05]


# ── Helper Functions ────────────────────────────────────────────────────────────

def random_date(start: datetime, end: datetime) -> datetime:
    """Return a random datetime between start and end."""
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def seasonal_date(start: datetime, end: datetime) -> datetime:
    """
    Generate a date biased toward holiday seasons (Nov-Dec and Jan-Feb).
    Uses a weighted random month selection to simulate real e-commerce patterns.
    """
    # Monthly weights: higher in Nov (11) and Dec (12) for holiday season
    month_weights = [0.07, 0.06, 0.07, 0.07, 0.08, 0.07,
                     0.07, 0.08, 0.08, 0.09, 0.11, 0.15]
    
    # Pick a year that falls inside the rolling data window
    year = random.choice(range(START_DATE.year, END_DATE.year + 1))
    # Pick month with seasonal bias
    month = random.choices(range(1, 13), weights=month_weights)[0]
    # Pick day within month
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    day = random.randint(1, max_day)
    hour = random.randint(6, 23)
    minute = random.randint(0, 59)
    
    dt = datetime(year, month, day, hour, minute)
    # Clip to our date range
    return min(max(dt, start), end)


# ── Generator Functions ─────────────────────────────────────────────────────────

def generate_categories(n: int) -> pd.DataFrame:
    """
    Creates product categories and departments.
    Similar to real e-commerce category trees (Electronics > Smartphones).
    """
    departments = ["Electronics", "Home & Garden", "Fashion", "Sports",
                   "Books", "Beauty", "Toys", "Food & Grocery", "Automotive"]
    
    category_names = [
        "Smartphones", "Laptops", "Headphones", "Cameras", "Tablets",
        "Furniture", "Kitchen Appliances", "Bedding", "Garden Tools", "Lighting",
        "Men's Clothing", "Women's Clothing", "Shoes", "Watches", "Bags",
        "Fitness Equipment", "Outdoor Gear", "Cycling", "Team Sports",
        "Fiction Books", "Non-Fiction", "Children's Books", "Textbooks",
        "Skincare", "Makeup", "Hair Care", "Fragrances",
        "Action Figures", "Board Games", "Baby Toys",
        "Car Accessories", "Motor Oil"
    ]
    
    dept_map = {
        "Smartphones": "Electronics", "Laptops": "Electronics", 
        "Headphones": "Electronics", "Cameras": "Electronics", "Tablets": "Electronics",
        "Furniture": "Home & Garden", "Kitchen Appliances": "Home & Garden",
        "Bedding": "Home & Garden", "Garden Tools": "Home & Garden", "Lighting": "Home & Garden",
        "Men's Clothing": "Fashion", "Women's Clothing": "Fashion", "Shoes": "Fashion",
        "Watches": "Fashion", "Bags": "Fashion",
        "Fitness Equipment": "Sports", "Outdoor Gear": "Sports",
        "Cycling": "Sports", "Team Sports": "Sports",
        "Fiction Books": "Books", "Non-Fiction": "Books",
        "Children's Books": "Books", "Textbooks": "Books",
        "Skincare": "Beauty", "Makeup": "Beauty", "Hair Care": "Beauty", "Fragrances": "Beauty",
        "Action Figures": "Toys", "Board Games": "Toys", "Baby Toys": "Toys",
        "Car Accessories": "Automotive", "Motor Oil": "Automotive",
    }
    
    rows = []
    for i, name in enumerate(category_names[:n], start=1):
        rows.append({
            "category_id": f"CAT{i:04d}",
            "category_name": name,
            "department": dept_map.get(name, "Other"),
        })
    
    return pd.DataFrame(rows)


def generate_sellers(n: int) -> pd.DataFrame:
    """
    Creates seller profiles. Sellers are like third-party marketplace vendors.
    Each seller has a city, state, and zip code (like Amazon's seller directory).
    """
    rows = []
    for i in range(1, n + 1):
        state = random.choices(STATES, weights=STATE_WEIGHTS)[0]
        rows.append({
            "seller_id":   f"SEL{i:05d}",
            "seller_name": fake.company(),
            "city":        fake.city(),
            "state":       state,
            "zip_code":    fake.zipcode(),
            "email":       fake.company_email(),
            "phone":       fake.phone_number()[:20],
            "created_at":  random_date(datetime(2020, 1, 1), START_DATE).isoformat(),
        })
    return pd.DataFrame(rows)


def generate_customers(n: int) -> pd.DataFrame:
    """
    Creates customer profiles. Includes geographic data for the map dashboard.
    Customers have a signup_date (before they can place orders).
    """
    rows = []
    for i in range(1, n + 1):
        state = random.choices(STATES, weights=STATE_WEIGHTS)[0]
        signup = random_date(datetime(2021, 1, 1), START_DATE + timedelta(days=30))
        rows.append({
            "customer_id":    f"CUST{i:07d}",
            "first_name":     fake.first_name(),
            "last_name":      fake.last_name(),
            "email":          fake.unique.email(),
            "city":           fake.city(),
            "state":          state,
            "zip_code":       fake.zipcode(),
            "signup_date":    signup.date().isoformat(),
            "is_active":      random.choices([True, False], weights=[0.85, 0.15])[0],
        })
    return pd.DataFrame(rows)


def generate_products(n: int, categories: pd.DataFrame) -> pd.DataFrame:
    """
    Creates product listings. 
    Prices follow a log-normal distribution (most products are cheap,
    a few are expensive — just like real marketplaces).
    """
    category_ids = categories["category_id"].tolist()
    
    # Product name templates by category
    adjectives = ["Premium", "Pro", "Essential", "Ultra", "Classic", "Smart", "Mini"]
    
    rows = []
    for i in range(1, n + 1):
        cat_id = random.choice(category_ids)
        cat_name = categories.loc[categories["category_id"] == cat_id, "category_name"].values[0]
        
        # Log-normal price: most items $10-$200, some up to $2000
        base_price = np.random.lognormal(mean=3.5, sigma=1.2)
        price = round(min(max(base_price, 5.0), 2500.0), 2)
        
        # Cost is 40-70% of price (realistic gross margin)
        cost = round(price * random.uniform(0.40, 0.70), 2)
        
        rows.append({
            "product_id":      f"PROD{i:06d}",
            "category_id":     cat_id,
            "product_name":    f"{random.choice(adjectives)} {cat_name} {fake.word().title()}",
            "description":     fake.sentence(nb_words=12),
            "price":           price,
            "cost_price":      cost,
            "weight_g":        random.randint(50, 30_000),
            "length_cm":       random.randint(5, 100),
            "height_cm":       random.randint(2, 60),
            "width_cm":        random.randint(5, 80),
            "stock_quantity":  random.randint(0, 500),
            "is_active":       random.choices([True, False], weights=[0.92, 0.08])[0],
            "created_at":      random_date(datetime(2020, 1, 1), START_DATE).isoformat(),
        })
    return pd.DataFrame(rows)


def generate_orders_and_items(
    n_orders: int,
    customers: pd.DataFrame,
    sellers: pd.DataFrame,
    products: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Creates orders and order_items (the line items inside each order).
    
    WHY TWO TABLES?
    One order can have multiple products. We separate this into:
    - orders: one row per order (header info like date, status, customer)
    - order_items: one row per product within an order (qty, price, seller)
    
    This is the standard "order header / order line" pattern in databases.
    """
    customer_ids = customers["customer_id"].tolist()
    seller_ids   = sellers["seller_id"].tolist()
    product_ids  = products["product_id"].tolist()
    
    # Power-law product popularity: product 1 is 100x more popular than product 1000
    product_pop = np.array([1 / (i ** 0.7) for i in range(1, len(product_ids) + 1)])
    product_pop /= product_pop.sum()  # Normalize to probabilities
    
    orders = []
    items  = []
    item_counter = 1
    
    for i in range(1, n_orders + 1):
        order_id   = f"ORD{i:08d}"
        customer   = random.choice(customer_ids)
        order_date = seasonal_date(START_DATE, END_DATE)
        status     = random.choices(ORDER_STATUSES, weights=STATUS_WEIGHTS)[0]
        
        # Delivery date is 2-15 days after order date (if delivered)
        if status == "delivered":
            delivery_date = (order_date + timedelta(days=random.randint(2, 15))).isoformat()
        else:
            delivery_date = None
        
        freight = round(random.uniform(5.0, 80.0), 2)
        
        orders.append({
            "order_id":           order_id,
            "customer_id":        customer,
            "order_date":         order_date.isoformat(),
            "order_status":       status,
            "delivery_date":      delivery_date,
            "freight_value":      freight,
            "estimated_delivery": (order_date + timedelta(days=random.randint(5, 20))).isoformat(),
        })
        
        # Each order has 1-5 items (most have 1-2)
        n_items = random.choices([1, 2, 3, 4, 5], weights=[0.55, 0.25, 0.10, 0.07, 0.03])[0]
        
        # Sample products using popularity weights (no duplicates per order)
        chosen_products = np.random.choice(
            product_ids, size=min(n_items, len(product_ids)),
            replace=False, p=product_pop
        )
        
        for prod_id in chosen_products:
            seller  = random.choice(seller_ids)
            prod_price = products.loc[products["product_id"] == prod_id, "price"].values[0]
            quantity   = random.choices([1, 2, 3, 4], weights=[0.70, 0.20, 0.07, 0.03])[0]
            # Small random price variation (discount codes, dynamic pricing)
            actual_price = round(prod_price * random.uniform(0.85, 1.05), 2)
            
            items.append({
                "order_item_id":  f"ITEM{item_counter:09d}",
                "order_id":       order_id,
                "product_id":     prod_id,
                "seller_id":      seller,
                "quantity":       quantity,
                "unit_price":     actual_price,
                "total_price":    round(actual_price * quantity, 2),
            })
            item_counter += 1
    
    return pd.DataFrame(orders), pd.DataFrame(items)


def generate_payments(orders: pd.DataFrame) -> pd.DataFrame:
    """
    Creates payment records. Each order has at least one payment.
    Some orders are split across multiple payment methods
    (e.g. part credit card, part voucher).
    """
    rows = []
    pay_counter = 1
    
    for _, order in orders.iterrows():
        order_id = order["order_id"]
        
        # 10% of orders have split payment
        if random.random() < 0.10:
            n_payments = 2
        else:
            n_payments = 1
        
        for j in range(n_payments):
            pay_type = random.choices(PAYMENT_TYPES, weights=PAYMENT_WEIGHTS)[0]
            # Installments only for credit card
            installments = random.choice([1, 2, 3, 6, 12]) if pay_type == "credit_card" else 1
            # Approximate amount (we don't have order total easily, use random in range)
            amount = round(random.uniform(20.0, 1200.0), 2)
            
            rows.append({
                "payment_id":       f"PAY{pay_counter:09d}",
                "order_id":         order_id,
                "payment_sequence": j + 1,
                "payment_type":     pay_type,
                "installments":     installments,
                "payment_value":    amount,
                "payment_status":   "approved" if order["order_status"] != "cancelled" else "refunded",
            })
            pay_counter += 1
    
    return pd.DataFrame(rows)


def generate_reviews(orders: pd.DataFrame, n: int) -> pd.DataFrame:
    """
    Creates product reviews. Only delivered orders get reviews.
    Score distribution is skewed positive (most customers give 4-5 stars).
    """
    delivered = orders[orders["order_status"] == "delivered"]["order_id"].tolist()
    sample_size = min(n, len(delivered))
    reviewed_orders = random.sample(delivered, sample_size)
    
    # Score weights: 5-star is most common, 1-star is next (bimodal)
    score_weights = [0.08, 0.05, 0.10, 0.27, 0.50]  # 1,2,3,4,5 stars
    
    positive_titles = ["Great product!", "Love it!", "Highly recommend", "Exceeded expectations", "Perfect"]
    neutral_titles  = ["It's okay", "As described", "Works fine", "Decent quality"]
    negative_titles = ["Disappointed", "Not as expected", "Poor quality", "Wouldn't recommend"]
    
    rows = []
    for i, order_id in enumerate(reviewed_orders, start=1):
        score = random.choices([1, 2, 3, 4, 5], weights=score_weights)[0]
        
        if score >= 4:
            title = random.choice(positive_titles)
            comment = fake.sentence(nb_words=random.randint(8, 25))
        elif score == 3:
            title = random.choice(neutral_titles)
            comment = fake.sentence(nb_words=random.randint(5, 15))
        else:
            title = random.choice(negative_titles)
            comment = fake.sentence(nb_words=random.randint(10, 30))
        
        rows.append({
            "review_id":      f"REV{i:08d}",
            "order_id":       order_id,
            "review_score":   score,
            "comment_title":  title,
            "comment_text":   comment,
            "review_date":    random_date(START_DATE, END_DATE).date().isoformat(),
        })
    
    return pd.DataFrame(rows)


# ── Main Execution ──────────────────────────────────────────────────────────────

def main():
    logger.info("Starting dataset generation...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Generate in dependency order (categories → products → orders → ...)
    logger.info("Generating categories...")
    categories = generate_categories(NUM_CATEGORIES)
    
    logger.info(f"Generating {NUM_SELLERS} sellers...")
    sellers = generate_sellers(NUM_SELLERS)
    
    logger.info(f"Generating {NUM_CUSTOMERS} customers...")
    customers = generate_customers(NUM_CUSTOMERS)
    
    logger.info(f"Generating {NUM_PRODUCTS} products...")
    products = generate_products(NUM_PRODUCTS, categories)
    
    logger.info(f"Generating {NUM_ORDERS} orders and order items...")
    orders, order_items = generate_orders_and_items(NUM_ORDERS, customers, sellers, products)
    
    logger.info("Generating payments...")
    payments = generate_payments(orders)
    
    logger.info(f"Generating {NUM_REVIEWS} reviews...")
    reviews = generate_reviews(orders, NUM_REVIEWS)
    
    # Save all files
    files = {
        "categories.csv":   categories,
        "sellers.csv":      sellers,
        "customers.csv":    customers,
        "products.csv":     products,
        "orders.csv":       orders,
        "order_items.csv":  order_items,
        "payments.csv":     payments,
        "reviews.csv":      reviews,
    }
    
    for filename, df in files.items():
        path = os.path.join(OUTPUT_DIR, filename)
        df.to_csv(path, index=False)
        logger.success(f"Saved {len(df):,} rows → {path}")
    
    # Print summary stats
    logger.info("\n" + "=" * 50)
    logger.info("DATASET SUMMARY")
    logger.info("=" * 50)
    for filename, df in files.items():
        logger.info(f"  {filename:<25} {len(df):>8,} rows  |  {df.shape[1]:>2} columns")
    
    total_revenue = order_items["total_price"].sum() + orders["freight_value"].sum()
    logger.info(f"\n  Approximate total GMV: ${total_revenue:,.2f}")
    logger.info(f"  Date range: {orders['order_date'].min()[:10]} → {orders['order_date'].max()[:10]}")
    logger.success("\nDataset generation complete!")


if __name__ == "__main__":
    main()
