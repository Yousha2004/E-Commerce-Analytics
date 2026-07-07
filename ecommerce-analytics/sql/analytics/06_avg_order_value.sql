-- 06_avg_order_value.sql — Average Order Value (AOV) Analysis
-- AOV = Total Revenue / Total Orders (key e-commerce KPI)
SELECT
    d.year_month,
    d.year,
    d.month_name_short,
    COUNT(DISTINCT fo.order_id)                              AS order_count,
    ROUND(SUM(fo.total_order_value), 2)                      AS total_revenue,
    ROUND(AVG(fo.total_order_value), 2)                      AS avg_order_value,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fo.total_order_value), 2) AS median_order_value,
    ROUND(AVG(fo.item_count), 2)                             AS avg_items_per_order,
    ROUND(AVG(fo.total_quantity), 2)                         AS avg_units_per_order,
    -- AOV by payment type
    ROUND(AVG(CASE WHEN fo.primary_payment_type = 'credit_card' THEN fo.total_order_value END), 2) AS aov_credit_card,
    ROUND(AVG(CASE WHEN fo.primary_payment_type = 'boleto'      THEN fo.total_order_value END), 2) AS aov_boleto
FROM marts.fact_orders fo
JOIN marts.dim_date d ON d.date_day = fo.order_date
WHERE fo.is_delivered = TRUE
GROUP BY d.year_month, d.year, d.month_name_short
ORDER BY d.year_month;
