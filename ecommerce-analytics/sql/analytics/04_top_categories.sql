-- 04_top_categories.sql — Category Revenue Breakdown
SELECT
    department,
    category_name,
    ROUND(SUM(fs.gross_revenue), 2)                         AS total_revenue,
    ROUND(SUM(fs.gross_profit),  2)                         AS total_profit,
    ROUND(SUM(fs.gross_profit) / NULLIF(SUM(fs.gross_revenue), 0) * 100, 2) AS margin_pct,
    COUNT(DISTINCT fs.order_id)                             AS total_orders,
    COUNT(DISTINCT fs.product_id)                           AS products_sold,
    ROUND(AVG(fs.selling_price), 2)                         AS avg_price,
    ROUND(SUM(fs.gross_revenue) / SUM(SUM(fs.gross_revenue)) OVER () * 100, 2) AS revenue_share_pct,
    RANK() OVER (ORDER BY SUM(fs.gross_revenue) DESC)       AS revenue_rank
FROM marts.fact_sales fs
JOIN marts.dim_products dp USING (product_id)
WHERE fs.is_delivered = TRUE
GROUP BY department, category_name
ORDER BY total_revenue DESC;
