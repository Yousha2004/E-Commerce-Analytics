-- stg_payments.sql
with source as (
    select * from {{ source('staging', 'payments') }}
),
renamed as (
    select
        payment_id,
        order_id,
        payment_sequence::integer      as payment_sequence,
        payment_type,
        installments::integer          as installments,
        payment_value::numeric(10,2)   as payment_value,
        payment_status,
        (payment_status = 'approved')::boolean as is_approved
    from source
    where payment_id is not null
      and payment_value > 0
)
select * from renamed
