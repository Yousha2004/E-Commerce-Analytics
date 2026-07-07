-- dim_date.sql
-- ============
-- PURPOSE:
--   Creates a "date dimension" — a table with one row for every calendar
--   day and many attributes (day name, week number, quarter, is_holiday, etc.)
--
-- WHY DO WE NEED A DATE DIMENSION?
--   In analytics, you almost always need to:
--     - "Show sales by month" → need month names in right order
--     - "Compare this quarter to last quarter" → need quarter numbers
--     - "Sales on weekdays vs weekends" → need day-of-week
--
--   Without a date dimension, you'd need complex date functions in EVERY query.
--   With a date dimension, you just JOIN to it:
--     JOIN marts.dim_date d ON d.date_day = orders.order_date::date
--     WHERE d.quarter = 'Q4'
--
-- THIS IS THE "SPINE" OF TIME-SERIES ANALYTICS.
--
-- IMPLEMENTATION: Uses generate_series() to create one row per day.
--   generate_series(start, end, interval '1 day') is a PostgreSQL function
--   that generates a sequence of values — like range() in Python.

{{
    config(
        materialized='table',
        schema='marts',
        description='Calendar date dimension spanning 2020-2026'
    )
}}

with date_spine as (
    -- Generate one row per day from Jan 1 2020 to Dec 31 2026
    -- This covers our full dataset range with headroom
    select
        generate_series(
            '2020-01-01'::date,
            '2026-12-31'::date,
            interval '1 day'
        )::date as date_day
),

date_attributes as (
    select
        -- Primary key: the date itself (used for JOINs)
        date_day,
        
        -- Integer surrogate key (YYYYMMDD format — faster for large fact table joins)
        to_char(date_day, 'YYYYMMDD')::integer              as date_key,
        
        -- ── Year attributes ─────────────────────────────────
        extract(year from date_day)::integer                as year,
        
        -- ── Quarter attributes ───────────────────────────────
        extract(quarter from date_day)::integer             as quarter_number,
        'Q' || extract(quarter from date_day)::integer      as quarter_name,
        extract(year from date_day)::integer || '-Q' || 
            extract(quarter from date_day)::integer         as year_quarter,   -- e.g. "2023-Q4"
        
        -- ── Month attributes ─────────────────────────────────
        extract(month from date_day)::integer               as month_number,
        to_char(date_day, 'Month')                          as month_name,     -- "January"
        to_char(date_day, 'Mon')                            as month_name_short, -- "Jan"
        to_char(date_day, 'YYYY-MM')                        as year_month,     -- "2023-11"
        date_trunc('month', date_day)::date                 as first_day_of_month,
        (date_trunc('month', date_day) + interval '1 month - 1 day')::date as last_day_of_month,
        
        -- ── Week attributes ───────────────────────────────────
        extract(week from date_day)::integer                as week_number,    -- ISO week 1-53
        date_trunc('week', date_day)::date                  as first_day_of_week,
        
        -- ── Day attributes ────────────────────────────────────
        extract(day from date_day)::integer                 as day_of_month,   -- 1-31
        extract(doy from date_day)::integer                 as day_of_year,    -- 1-366
        extract(dow from date_day)::integer                 as day_of_week,    -- 0=Sunday, 6=Saturday
        to_char(date_day, 'Day')                            as day_name,       -- "Monday   "
        to_char(date_day, 'Dy')                             as day_name_short, -- "Mon"
        
        -- ── Boolean flags (very useful for WHERE clauses) ─────
        (extract(dow from date_day) in (0, 6))::boolean     as is_weekend,
        (extract(dow from date_day) not in (0, 6))::boolean as is_weekday,
        
        -- First/last day of period flags
        (extract(day from date_day) = 1)::boolean           as is_first_day_of_month,
        (date_day = date_trunc('week', date_day)::date)::boolean as is_first_day_of_week,
        (extract(doy from date_day) = 1)::boolean           as is_first_day_of_year,
        
        -- ── Relative to "today" ─────────────────────────────────
        -- Useful for "last 30 days", "last 90 days" filters in dashboards
        (current_date - date_day)::integer                  as days_ago,
        
        -- Season (Northern Hemisphere)
        case
            when extract(month from date_day) in (12, 1, 2)  then 'Winter'
            when extract(month from date_day) in (3,  4, 5)  then 'Spring'
            when extract(month from date_day) in (6,  7, 8)  then 'Summer'
            else 'Fall'
        end                                                 as season,
        
        -- E-commerce seasons (marketing/business view)
        case
            when to_char(date_day, 'MM-DD') between '11-25' and '11-30' then 'Black Friday Week'
            when to_char(date_day, 'MM-DD') between '12-01' and '12-31' then 'Holiday Season'
            when to_char(date_day, 'MM-DD') between '01-01' and '01-15' then 'New Year Sales'
            when to_char(date_day, 'MM-DD') between '02-10' and '02-14' then "Valentine's Week"
            else 'Regular'
        end                                                 as ecommerce_season

    from date_spine
)

select * from date_attributes
order by date_day
