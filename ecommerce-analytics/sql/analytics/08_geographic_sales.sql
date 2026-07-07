-- 08_geographic_sales.sql — Sales by State/City (Geographic Analysis)
-- Powers the filled map in the dashboard
SELECT
    dc.state,
    dc.city,
    COUNT(DISTINCT fo.order_id)                               AS order_count,
    COUNT(DISTINCT fo.customer_id)                            AS unique_customers,
    ROUND(SUM(fo.total_order_value), 2)                       AS total_revenue,
    ROUND(AVG(fo.total_order_value), 2)                       AS avg_order_value,
    ROUND(SUM(fo.total_order_value) / SUM(SUM(fo.total_order_value)) OVER () * 100, 2) AS revenue_share_pct,
    RANK() OVER (ORDER BY SUM(fo.total_order_value) DESC)     AS state_revenue_rank
FROM marts.fact_orders fo
JOIN marts.dim_customers dc USING (customer_id)
WHERE fo.is_delivered = TRUE
  AND dc.state IS NOT NULL
GROUP BY dc.state, dc.city
ORDER BY total_revenue DESC;
