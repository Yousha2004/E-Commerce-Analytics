-- stg_order_items.sql
with source as (
    select * from {{ source('staging', 'order_items') }}
),
renamed as (
    select
        order_item_id,
        order_id,
        product_id,
        seller_id,
        quantity::integer          as quantity,
        unit_price::numeric(10,2)  as unit_price,
        total_price::numeric(12,2) as total_price
    from source
    where order_item_id is not null
      and total_price > 0
)
select * from renamed
