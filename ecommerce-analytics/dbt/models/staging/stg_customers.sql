-- stg_customers.sql
with source as (
    select * from {{ source('staging', 'customers') }}
),

renamed as (
    select
        customer_id,
        
        -- Full name as a computed column
        first_name,
        last_name,
        first_name || ' ' || last_name                  as full_name,
        
        email,
        city,
        state,
        zip_code,
        
        signup_date::date                               as signup_date,
        is_active::boolean                              as is_active,
        
        -- Customer tenure: how many days since they signed up
        extract(day from (current_date - signup_date::date))::integer as days_since_signup,
        
        -- What year/month they signed up (useful for cohort analysis)
        date_trunc('month', signup_date::date)::date    as signup_cohort_month,
        extract(year from signup_date::date)::integer   as signup_year

    from source
    where customer_id is not null
      and email is not null
)

select * from renamed
