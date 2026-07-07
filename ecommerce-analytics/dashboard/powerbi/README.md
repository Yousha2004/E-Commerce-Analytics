# Power BI Integration Guide

While we provided a **Streamlit** dashboard in Python, Power BI is still the industry standard for enterprise BI. If you have Power BI Desktop installed (Windows only), here is exactly how to connect it to this project's PostgreSQL Data Warehouse.

## Step 1: Connect Power BI to PostgreSQL

1. Open Power BI Desktop.
2. Click **Get Data** -> **More...** -> search for **PostgreSQL database**.
3. Click **Connect**.
4. Enter the connection details:
   - **Server:** `localhost:5432`
   - **Database:** `ecommerce_dw`
5. Under Data Connectivity mode, select **DirectQuery** (best for large data) or **Import** (best for fast dashboards).
6. Enter credentials:
   - **User:** `ecommerce_user`
   - **Password:** `ecommerce_pass`
7. Click **Connect**.

## Step 2: Select the Mart Models

When the Navigator window opens, expand `ecommerce_dw` -> `marts`.
Check the following tables:
- `fact_sales`
- `fact_orders`
- `dim_date`
- `dim_customers`
- `dim_products`
- `dim_sellers`

Click **Load**.

## Step 3: Set up Relationships (Data Modeling)

Go to the **Model view** (third icon on the left). Ensure the relationships (lines) connect like a star:
- `fact_sales.date_key` -> `dim_date.date_key`
- `fact_sales.product_id` -> `dim_products.product_id`
- `fact_sales.customer_id` -> `dim_customers.customer_id`
- `fact_sales.seller_id` -> `dim_sellers.seller_id`

## Step 4: Create DAX Measures

Right-click the `fact_sales` table and select **New Measure**. Create these standard KPIs:

```dax
Total Revenue = SUM(fact_sales[gross_revenue])
```

```dax
Total Profit = SUM(fact_sales[gross_profit])
```

```dax
Profit Margin % = DIVIDE([Total Profit], [Total Revenue], 0)
```

```dax
Total Orders = DISTINCTCOUNT(fact_sales[order_id])
```

```dax
AOV = DIVIDE([Total Revenue], [Total Orders], 0)
```

## Step 5: Build Visualizations

Switch to the **Report view** and drag-and-drop your fields onto the canvas:

1. **KPI Cards:** Drag your DAX measures into Card visuals.
2. **Sales Trend:** Line chart. X-axis: `dim_date[year_month]`, Y-axis: `[Total Revenue]`.
3. **Top Products:** Bar chart. Y-axis: `dim_products[product_name]`, X-axis: `[Total Revenue]`.
4. **Customer Segments:** Donut chart. Legend: `dim_customers[customer_segment]`, Values: `Count of customer_id`.
5. **Geographic Map:** Map visual. Location: `dim_customers[state]`, Bubble size: `[Total Revenue]`.

You now have a fully functional Power BI dashboard connected directly to your dbt star schema!
