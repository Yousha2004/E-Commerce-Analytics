-- dim_customers.sql
-- =================
-- PURPOSE:
--   Creates the Customer Dimension table — the "who" for all analysis.
--   Enriches customer data with behavioral metrics computed from orders.
--
-- STAR SCHEMA ROLE:
--   This is a DIMENSION table. It describes the people placing orders.
--   Fact tables (fact_orders, fact_sales) reference this via customer_id.
--
-- ENRICHMENT ADDED (beyond raw customer data):
--   - Total orders placed
--   - Total revenue spent
--   - Average order value
--   - First and last order dates
--   - Customer segment (RFM-based: High Value, At Risk, etc.)
--   - Days since last order (recency)

{{
    config(
        materialized='table',
        schema='marts',
        description='Customer dimension with behavioral enrichment and RFM segmentation'
    )
}}

with customers as (
    select * from {{ ref('stg_customers') }}
),

-- Compute order statistics per customer
order_stats as (
    select
        o.customer_id,
        
        -- Recency: when did they last order?
        max(o.order_date)::date                                         as last_order_date,
        min(o.order_date)::date                                         as first_order_date,
        
        -- Frequency: how many orders?
        count(distinct o.order_id)                                      as total_orders,
        count(distinct case when o.is_delivered then o.order_id end)    as delivered_orders,
        count(distinct case when o.is_cancelled then o.order_id end)    as cancelled_orders,
        
        -- Monetary: how much have they spent?
        sum(oi.total_price)::numeric(12,2)                              as total_revenue,
        avg(oi.total_price)::numeric(10,2)                              as avg_item_price,
        
        -- Average order value (total per order, not per item)
        (sum(oi.total_price) / nullif(count(distinct o.order_id), 0))::numeric(10,2) as avg_order_value,
        
        -- Is this a repeat customer?
        (count(distinct o.order_id) > 1)::boolean                      as is_repeat_customer

    from {{ ref('stg_orders') }} o
    left join {{ ref('stg_order_items') }} oi using (order_id)
    group by o.customer_id
),

-- Combine customer profile with behavioral data
enriched as (
    select
        c.customer_id,
        c.full_name,
        c.first_name,
        c.last_name,
        c.email,
        c.city,
        c.state,
        c.zip_code,
        c.signup_date,
        c.signup_cohort_month,
        c.signup_year,
        c.is_active,
        c.days_since_signup,
        
        -- Order metrics (NULLs for customers who haven't ordered yet)
        coalesce(os.total_orders, 0)       as total_orders,
        coalesce(os.delivered_orders, 0)   as delivered_orders,
        coalesce(os.cancelled_orders, 0)   as cancelled_orders,
        coalesce(os.total_revenue, 0)      as total_revenue,
        os.avg_order_value,
        os.first_order_date,
        os.last_order_date,
        os.is_repeat_customer,
        
        -- Recency in days
        case
            when os.last_order_date is not null
            then (current_date - os.last_order_date)::integer
            else null
        end as days_since_last_order,
        
        -- ── Customer Segment (simplified RFM) ──────────────────────────
        -- RFM = Recency, Frequency, Monetary
        -- This classifies customers into business-meaningful groups
        case
            when os.total_orders is null or os.total_orders = 0
                then 'Never Ordered'
            when os.total_revenue >= 500 and os.total_orders >= 5
                then 'Champions'      -- High spend, many orders = best customers
            when os.total_revenue >= 200 and os.total_orders >= 2
                then 'Loyal'          -- Good spend, repeat buyers
            when (current_date - os.last_order_date) <= 90
                then 'Recent'         -- Ordered in last 3 months
            when (current_date - os.last_order_date) <= 180
                then 'At Risk'        -- Hasn't ordered in 3-6 months
            else 'Churned'            -- No order in 6+ months
        end as customer_segment,
        
        -- ── Lifetime Value Tier ─────────────────────────────────────────
        case
            when coalesce(os.total_revenue, 0) >= 1000 then 'Platinum'
            when coalesce(os.total_revenue, 0) >= 300  then 'Gold'
            when coalesce(os.total_revenue, 0) >= 100  then 'Silver'
            when coalesce(os.total_revenue, 0) >  0    then 'Bronze'
            else 'No Purchases'
        end as ltv_tier

    from customers c
    left join order_stats os using (customer_id)
)

select * from enriched
