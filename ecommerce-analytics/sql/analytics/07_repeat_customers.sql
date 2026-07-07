-- 07_repeat_customers.sql — Repeat Purchase Analysis
-- BUSINESS QUESTION: What % of our customers buy more than once?
-- Repeat customers are ~5x cheaper to sell to than acquiring new ones.
WITH customer_order_counts AS (
    SELECT
        customer_id,
        COUNT(DISTINCT order_id)                              AS order_count,
        SUM(total_order_value)                                AS lifetime_value,
        MIN(order_date)                                       AS first_order,
        MAX(order_date)                                       AS last_order,
        ROUND((MAX(order_date) - MIN(order_date))::numeric / 30, 1) AS active_months
    FROM marts.fact_orders
    WHERE is_delivered = TRUE
    GROUP BY customer_id
),
segmented AS (
    SELECT *,
        CASE
            WHEN order_count = 1 THEN '1 Order'
            WHEN order_count = 2 THEN '2 Orders'
            WHEN order_count BETWEEN 3 AND 5 THEN '3-5 Orders'
            ELSE '6+ Orders'
        END AS purchase_frequency_segment,
        (order_count > 1)::boolean AS is_repeat_customer
    FROM customer_order_counts
)
SELECT
    purchase_frequency_segment,
    COUNT(customer_id)                                        AS customer_count,
    ROUND(COUNT(customer_id)::numeric / SUM(COUNT(customer_id)) OVER () * 100, 2) AS pct_of_customers,
    ROUND(AVG(lifetime_value), 2)                             AS avg_lifetime_value,
    ROUND(AVG(order_count), 2)                                AS avg_orders,
    ROUND(SUM(lifetime_value), 2)                             AS total_segment_revenue,
    ROUND(SUM(lifetime_value) / SUM(SUM(lifetime_value)) OVER () * 100, 2) AS pct_of_revenue
FROM segmented
GROUP BY purchase_frequency_segment
ORDER BY MIN(order_count);
