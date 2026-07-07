-- dim_products.sql
{{
    config(materialized='table', schema='marts',
           description='Product dimension with category info and sales metrics')
}}

with products as (
    select * from {{ ref('stg_products') }}
),

categories as (
    select * from {{ source('staging', 'categories') }}
),

-- Sales performance per product
product_sales as (
    select
        oi.product_id,
        count(distinct oi.order_id)       as total_orders,
        sum(oi.quantity)                  as total_units_sold,
        sum(oi.total_price)::numeric(14,2) as total_revenue,
        avg(oi.unit_price)::numeric(10,2)  as avg_selling_price,
        avg(r.review_score)::numeric(4,2)  as avg_review_score,
        count(r.review_id)                 as review_count
    from {{ ref('stg_order_items') }} oi
    left join {{ ref('stg_orders') }} o using (order_id)
    left join {{ source('staging', 'reviews') }} r using (order_id)
    where o.order_status != 'cancelled'
    group by oi.product_id
),

enriched as (
    select
        p.product_id,
        p.product_name,
        p.description,
        p.category_id,
        c.category_name,
        c.department,

        p.price                              as list_price,
        p.cost_price,
        p.gross_margin_pct,
        p.price_tier,

        p.weight_g,
        p.length_cm,
        p.height_cm,
        p.width_cm,
        p.volume_cm3,
        p.stock_quantity,
        p.is_active,

        -- Sales metrics
        coalesce(ps.total_orders, 0)        as total_orders,
        coalesce(ps.total_units_sold, 0)    as total_units_sold,
        coalesce(ps.total_revenue, 0)       as total_revenue,
        ps.avg_selling_price,
        ps.avg_review_score,
        coalesce(ps.review_count, 0)        as review_count,

        -- Popularity rank (1 = best selling)
        rank() over (order by coalesce(ps.total_revenue, 0) desc) as revenue_rank,
        rank() over (order by coalesce(ps.total_units_sold, 0) desc) as units_rank

    from products p
    left join categories c using (category_id)
    left join product_sales ps using (product_id)
)

select * from enriched


