-- dim_sellers.sql
{{
    config(materialized='table', schema='marts',
           description='Seller dimension with performance metrics')
}}

with sellers as (
    select * from {{ ref('stg_sellers') }}
),

seller_metrics as (
    select
        oi.seller_id,
        count(distinct oi.order_id)                as total_orders,
        sum(oi.total_price)::numeric(14,2)         as total_revenue,
        avg(oi.total_price)::numeric(10,2)         as avg_order_value,
        count(distinct oi.product_id)              as unique_products_sold,
        avg(r.review_score)::numeric(4,2)          as avg_review_score,
        sum(case when o.order_status = 'delivered' then 1 else 0 end)::numeric
            / nullif(count(oi.order_id), 0) * 100  as fulfillment_rate_pct
    from {{ ref('stg_order_items') }} oi
    left join {{ ref('stg_orders') }} o using (order_id)
    left join {{ source('staging', 'reviews') }} r using (order_id)
    group by oi.seller_id
)

select
    s.seller_id,
    s.seller_name,
    s.city,
    s.state,
    s.zip_code,
    s.created_at,
    coalesce(sm.total_orders, 0)           as total_orders,
    coalesce(sm.total_revenue, 0)          as total_revenue,
    sm.avg_order_value,
    coalesce(sm.unique_products_sold, 0)   as unique_products_sold,
    sm.avg_review_score,
    sm.fulfillment_rate_pct,
    case
        when coalesce(sm.total_revenue, 0) >= 50000 then 'Platinum'
        when coalesce(sm.total_revenue, 0) >= 10000 then 'Gold'
        when coalesce(sm.total_revenue, 0) >= 1000  then 'Silver'
        else 'Bronze'
    end as seller_tier,
    rank() over (order by coalesce(sm.total_revenue, 0) desc) as revenue_rank

from sellers s
left join seller_metrics sm using (seller_id)
