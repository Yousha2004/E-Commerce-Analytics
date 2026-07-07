-- stg_products.sql
with source as (
    select * from {{ source('staging', 'products') }}
),

renamed as (
    select
        product_id,
        category_id,
        product_name,
        description,
        
        price::numeric(10,2)        as price,
        cost_price::numeric(10,2)   as cost_price,
        
        -- Gross margin percentage: (price - cost) / price * 100
        case
            when price > 0 and cost_price is not null
            then round(((price - cost_price) / price * 100)::numeric, 2)
            else null
        end                         as gross_margin_pct,
        
        -- Price tier (useful for segmentation)
        case
            when price < 25   then 'Budget'
            when price < 100  then 'Mid-Range'
            when price < 500  then 'Premium'
            else 'Luxury'
        end                         as price_tier,
        
        weight_g::integer           as weight_g,
        length_cm::integer          as length_cm,
        height_cm::integer          as height_cm,
        width_cm::integer           as width_cm,
        stock_quantity::integer     as stock_quantity,
        is_active::boolean          as is_active,
        
        -- Volume in cubic centimeters (for shipping cost estimation)
        (length_cm * height_cm * width_cm)::bigint as volume_cm3

    from source
    where product_id is not null
      and price > 0
)

select * from renamed


-- stg_sellers.sql (inline as separate file)
