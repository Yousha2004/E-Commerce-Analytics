-- fact_sales.sql
-- ==============
-- PURPOSE:
--   Revenue-level fact table at ITEM GRAIN (one row per order_item).
--   This is the primary table for all revenue, product, and seller analytics.
--
-- WHY TWO FACT TABLES?
--   fact_orders → answers "How many orders? What's the order status distribution?"
--   fact_sales  → answers "What's our revenue? Which products sell best?"
--
--   fact_sales is at a LOWER grain (order_item vs order) so it can answer
--   product-level questions that fact_orders cannot.
--
-- GRAIN: One row per order_item_id

{{
    config(
        materialized='incremental',
        schema='marts',
        unique_key='order_item_id',
        description='Revenue fact table at order-item grain — the primary table for product and revenue analytics'
    )
}}

with order_items as (
    select * from {{ ref('stg_order_items') }}
),

orders as (
    select
        order_id,
        customer_id,
        order_date,
        order_day,
        order_month,
        order_year,
        order_status,
        is_delivered,
        is_cancelled,
        freight_value,
        days_to_deliver,
        was_late,
        is_weekend_order
    from {{ ref('stg_orders') }}
    
    {% if is_incremental() %}
        where order_date > (
            select max(o.order_date)
            from {{ this }} fs
            join {{ ref('stg_orders') }} o using (order_id)
        )
    {% endif %}
),

products as (
    select product_id, product_name, category_id, price as list_price, cost_price, price_tier
    from {{ ref('stg_products') }}
),

categories as (
    select category_id, category_name, department
    from {{ source('staging', 'categories') }}
),

-- Estimate the portion of freight charged per item
-- (distribute freight proportionally by item value)
freight_allocated as (
    select
        oi.order_item_id,
        o.freight_value * (oi.total_price / nullif(sum(oi.total_price) over (partition by oi.order_id), 0))
            as allocated_freight
    from order_items oi
    join orders o using (order_id)
),

final as (
    select
        -- ── Keys ────────────────────────────────────────────────────────
        oi.order_item_id,
        oi.order_id,
        oi.product_id,
        oi.seller_id,
        o.customer_id,
        
        -- Date foreign key
        to_char(o.order_date, 'YYYYMMDD')::integer           as date_key,
        o.order_day                                          as order_date,
        o.order_month,
        o.order_year,
        
        -- ── Product Info ────────────────────────────────────────────────
        p.product_name,
        p.category_id,
        c.category_name,
        c.department,
        p.price_tier,
        
        -- ── Order Context ────────────────────────────────────────────────
        o.order_status,
        o.is_delivered,
        o.is_cancelled,
        o.is_weekend_order,
        o.days_to_deliver,
        o.was_late,
        
        -- ── Revenue Measures ─────────────────────────────────────────────
        oi.quantity,
        oi.unit_price                                        as selling_price,
        p.list_price,
        p.cost_price,
        oi.total_price                                       as gross_revenue,
        
        -- Estimated cost of goods sold for items sold
        (p.cost_price * oi.quantity)::numeric(12,2)         as estimated_cogs,
        
        -- Gross profit = revenue - COGS
        (oi.total_price - coalesce(p.cost_price * oi.quantity, 0))::numeric(12,2) as gross_profit,
        
        -- Gross margin %
        case
            when oi.total_price > 0 and p.cost_price is not null
            then round(
                (oi.total_price - p.cost_price * oi.quantity) / oi.total_price * 100, 2
            )
            else null
        end as gross_margin_pct,
        
        -- Discount applied (difference between list price and actual price)
        ((p.list_price - oi.unit_price) * oi.quantity)::numeric(10,2) as discount_amount,
        
        -- Allocated shipping revenue
        coalesce(fa.allocated_freight, 0)::numeric(8,2)     as allocated_freight,
        
        -- Total with freight
        (oi.total_price + coalesce(fa.allocated_freight, 0))::numeric(12,2) as net_revenue,
        
        -- Metadata
        current_timestamp                                    as dbt_updated_at

    from order_items oi
    join orders     o  using (order_id)
    join products   p  using (product_id)
    left join categories c using (category_id)
    left join freight_allocated fa using (order_item_id)
)

select * from final
