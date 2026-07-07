-- fact_orders.sql
-- ===============
-- PURPOSE:
--   The central FACT table in our star schema.
--   One row per ORDER — captures what happened (order placed, status, timing).
--
-- STAR SCHEMA ROLE:
--   Fact tables are at the CENTER of the star schema.
--   They contain FOREIGN KEYS to all dimension tables (customer, date, etc.)
--   and NUMERIC MEASURES (revenue, quantities, counts).
--
--   The "star" shape comes from the fact table in the middle with dimension
--   tables radiating outward like star points.
--
-- INCREMENTAL MODEL:
--   Using {{ config(materialized='incremental') }} means dbt only processes
--   NEW rows each run (orders since last run), not the entire history.
--   This is critical for performance at scale (millions of orders).
--
--   The unique_key='order_id' tells dbt how to UPSERT (insert or update).
--
-- GRAIN: One row per order_id

{{
    config(
        materialized='incremental',
        schema='marts',
        unique_key='order_id',
        on_schema_change='fail',
        description='Fact table at order grain — one row per order with all key metrics'
    )
}}

with orders as (
    select * from {{ ref('stg_orders') }}
    
    -- INCREMENTAL FILTER: on subsequent runs, only process orders
    -- created since the last time this model ran.
    -- This is wrapped in an {% if %} so it only applies for incremental runs.
    {% if is_incremental() %}
        -- is_incremental() is a dbt built-in that returns True when updating existing table
        where order_date > (select max(order_date) from {{ this }})
    {% endif %}
),

-- Aggregate order items to get order-level totals
order_totals as (
    select
        order_id,
        count(order_item_id)           as item_count,
        sum(quantity)                  as total_quantity,
        sum(total_price)::numeric(12,2) as items_revenue,
        avg(unit_price)::numeric(10,2)  as avg_item_price
    from {{ ref('stg_order_items') }}
    group by order_id
),

-- Get payment info per order
order_payments as (
    select
        order_id,
        sum(payment_value)::numeric(12,2)  as total_paid,
        max(payment_type)                   as primary_payment_type,  -- Main payment method
        max(installments)                   as max_installments,
        count(payment_id)                   as payment_count
    from {{ ref('stg_payments') }}
    where is_approved = true
    group by order_id
),

-- Get review info per order
order_reviews as (
    select
        order_id,
        review_score,
        review_date
    from {{ source('staging', 'reviews') }}
),

-- Assemble the final fact table
final as (
    select
        -- ── Surrogate / Natural Keys ─────────────────────────────────────
        o.order_id,
        o.customer_id,
        
        -- Foreign key to dim_date (integer YYYYMMDD format for fast joins)
        to_char(o.order_date, 'YYYYMMDD')::integer           as date_key,
        o.order_day                                          as order_date,
        o.order_month                                        as order_month,
        
        -- ── Descriptive Attributes ───────────────────────────────────────
        o.order_status,
        o.is_delivered,
        o.is_cancelled,
        o.is_weekend_order,
        o.delivery_date,
        o.estimated_delivery,
        
        -- ── Measures (numeric facts) ─────────────────────────────────────
        coalesce(ot.item_count, 0)                           as item_count,
        coalesce(ot.total_quantity, 0)                       as total_quantity,
        coalesce(ot.items_revenue, 0)                        as items_revenue,
        o.freight_value                                      as freight_value,
        
        -- Total order value = product revenue + freight
        coalesce(ot.items_revenue, 0) + o.freight_value      as total_order_value,
        
        -- Amount actually paid (from payment records)
        coalesce(op.total_paid, 0)                           as total_paid,
        
        -- ── Payment Attributes ───────────────────────────────────────────
        op.primary_payment_type,
        coalesce(op.max_installments, 1)                     as max_installments,
        coalesce(op.payment_count, 0)                        as payment_count,
        
        -- ── Delivery Performance ─────────────────────────────────────────
        o.days_to_deliver,
        o.was_late,
        
        -- ── Customer Satisfaction ────────────────────────────────────────
        rev.review_score,
        (rev.review_score >= 4)::boolean                     as is_positive_review,
        (rev.review_score <= 2)::boolean                     as is_negative_review,
        
        -- Metadata
        current_timestamp                                    as dbt_updated_at

    from orders o
    left join order_totals  ot  using (order_id)
    left join order_payments op  using (order_id)
    left join order_reviews  rev using (order_id)
)

select * from final
