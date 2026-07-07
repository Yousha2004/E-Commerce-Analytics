-- ============================================================
-- 05_customer_retention.sql — Cohort Retention Analysis
-- ============================================================
-- BUSINESS QUESTION: Of customers who first purchased in month X,
-- what % came back and purchased again in subsequent months?
--
-- COHORT ANALYSIS is one of the most powerful analytics techniques.
-- It answers "how sticky are we?" — which is critical for subscription
-- and marketplace businesses.
--
-- HOW IT WORKS:
-- 1. For each customer, find their first order month (cohort month)
-- 2. Group all customers by their cohort month
-- 3. For each subsequent month, count how many from the cohort returned
-- 4. Retention % = (returned customers) / (original cohort size) * 100
-- ============================================================

WITH customer_cohorts AS (
    -- Step 1: Find each customer's first purchase month
    SELECT
        customer_id,
        DATE_TRUNC('month', MIN(order_date))::date   AS cohort_month
    FROM marts.fact_orders
    WHERE is_delivered = TRUE
    GROUP BY customer_id
),

customer_activities AS (
    -- Step 2: Get every month each customer made a purchase
    SELECT DISTINCT
        fo.customer_id,
        DATE_TRUNC('month', fo.order_date)::date     AS activity_month
    FROM marts.fact_orders fo
    WHERE fo.is_delivered = TRUE
),

cohort_data AS (
    -- Step 3: Join cohort month with activity months
    -- Calculate how many months after cohort the customer returned
    SELECT
        cc.cohort_month,
        ca.activity_month,
        
        -- "Month number" since first purchase (0 = first purchase month, 1 = one month later, etc.)
        EXTRACT(
            YEAR FROM AGE(ca.activity_month, cc.cohort_month)
        )::integer * 12 +
        EXTRACT(
            MONTH FROM AGE(ca.activity_month, cc.cohort_month)
        )::integer                                   AS months_since_first_order,
        
        COUNT(DISTINCT cc.customer_id)               AS cohort_customers

    FROM customer_cohorts cc
    JOIN customer_activities ca USING (customer_id)
    GROUP BY cc.cohort_month, ca.activity_month
),

cohort_sizes AS (
    -- Count total customers in each cohort (denominator for retention %)
    SELECT
        cohort_month,
        COUNT(DISTINCT customer_id)                  AS cohort_size
    FROM customer_cohorts
    GROUP BY cohort_month
)

SELECT
    cd.cohort_month,
    TO_CHAR(cd.cohort_month, 'YYYY-MM')              AS cohort_label,
    cs.cohort_size,
    cd.months_since_first_order,
    cd.cohort_customers                              AS returning_customers,
    
    -- RETENTION RATE: what % of the original cohort came back this month
    ROUND(
        cd.cohort_customers::numeric / NULLIF(cs.cohort_size, 0) * 100,
        1
    )                                                AS retention_rate_pct

FROM cohort_data      cd
JOIN cohort_sizes     cs USING (cohort_month)
WHERE cd.months_since_first_order <= 12  -- Show first 12 months of retention
  AND cd.cohort_month >= '2023-01-01'    -- Only 2023+ cohorts (complete data)
  AND cd.cohort_month <= CURRENT_DATE - INTERVAL '1 month'  -- Exclude incomplete current month
ORDER BY cd.cohort_month, cd.months_since_first_order;
