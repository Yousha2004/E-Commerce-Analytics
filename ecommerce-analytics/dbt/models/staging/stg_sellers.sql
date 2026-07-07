-- stg_sellers.sql
with source as (
    select * from {{ source('staging', 'sellers') }}
),
renamed as (
    select
        seller_id,
        seller_name,
        city,
        state,
        zip_code,
        email,
        phone,
        created_at::timestamp as created_at
    from source
    where seller_id is not null
)
select * from renamed
