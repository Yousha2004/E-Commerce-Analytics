-- stg_orders.sql
-- ==============
-- PURPOSE:
--   Staging model for the orders table. Reads from the staging schema
--   (already cleaned by Python) and adds business-friendly column names,
--   computed columns, and type casts.
--
-- WHAT IS A STAGING MODEL IN dbt?
--   Staging models are the "entry point" for raw data into dbt.
--   They do LIGHT transformations:
--     - Rename columns to be consistent
--     - Cast types (string → date, string → boolean)
--     - Add simple computed columns
--   They do NOT do complex business logic or joins.
--
-- THIS MODEL BECOMES: a VIEW called staging_dbt.stg_orders
-- (no data stored — just a saved SELECT query)
--
-- JINJA2 SYNTAX:
--   {{ source('staging', 'orders') }} → resolves to staging.orders
--   This lets dbt track data lineage automatically.

with source as (
    -- Reference the 'orders' table from the 'staging' source
    -- (defined in schema.yml)
    select * from {{ source('staging', 'orders') }}
),

renamed as (
    select
        -- Primary key
        order_id,
        customer_id,

        -- Timestamps — ensure consistent timezone (UTC)
        order_date::timestamp                               as order_date,
        delivery_date::timestamp                           as delivery_date,
        estimated_delivery::timestamp                      as estimated_delivery,

        -- Status (already cleaned/validated in Python)
        order_status,

        -- Freight cost
        freight_value::numeric(8,2)                        as freight_value,

        -- ── Computed columns (business logic added here) ──────────
        
        -- Was the order actually delivered?
        (order_status = 'delivered')::boolean              as is_delivered,
        
        -- Was the order cancelled?
        (order_status = 'cancelled')::boolean              as is_cancelled,
        
        -- Days between order and delivery (NULL if not delivered)
        case
            when delivery_date is not null
            then extract(day from (delivery_date - order_date))
            else null
        end                                                as days_to_deliver,
        
        -- Was delivery late? (arrived after estimated date)
        case
            when delivery_date is not null and estimated_delivery is not null
            then (delivery_date > estimated_delivery)::boolean
            else null
        end                                                as was_late,
        
        -- Date parts for partitioning and filtering
        date_trunc('day',  order_date)::date               as order_day,
        date_trunc('week', order_date)::date               as order_week,
        date_trunc('month',order_date)::date               as order_month,
        extract(year  from order_date)::integer            as order_year,
        extract(month from order_date)::integer            as order_month_num,
        extract(dow   from order_date)::integer            as order_day_of_week,  -- 0=Sunday, 6=Saturday
        
        -- Is it a weekend order?
        (extract(dow from order_date) in (0, 6))::boolean  as is_weekend_order

    from source
    where order_id is not null
      and customer_id is not null
      and order_date is not null
)

select * from renamed
