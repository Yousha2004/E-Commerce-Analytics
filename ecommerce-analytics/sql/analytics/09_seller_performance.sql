-- 09_seller_performance.sql — Seller Scorecard
-- Ranks sellers by revenue, fulfillment rate, and customer satisfaction
SELECT
    ds.seller_id,
    ds.seller_name,
    ds.state,
    ds.seller_tier,
    ds.revenue_rank,
    ROUND(SUM(fs.gross_revenue), 2)                           AS total_revenue,
    ROUND(SUM(fs.gross_profit),  2)                           AS total_profit,
    ROUND(SUM(fs.gross_profit) / NULLIF(SUM(fs.gross_revenue), 0) * 100, 2) AS margin_pct,
    COUNT(DISTINCT fs.order_id)                               AS total_orders,
    COUNT(DISTINCT fs.product_id)                             AS products_listed,
    ROUND(AVG(ds.avg_review_score), 2)                        AS avg_rating,
    ROUND(ds.fulfillment_rate_pct, 1)                         AS fulfillment_rate_pct,
    -- Revenue per order
    ROUND(SUM(fs.gross_revenue) / NULLIF(COUNT(DISTINCT fs.order_id), 0), 2) AS revenue_per_order,
    -- Performance score (composite: 40% revenue rank + 30% rating + 30% fulfillment)
    ROUND(
        (1 - ds.revenue_rank::numeric / MAX(ds.revenue_rank) OVER ()) * 0.4
        + (COALESCE(ds.avg_review_score, 3) / 5.0) * 0.3
        + (COALESCE(ds.fulfillment_rate_pct, 0) / 100.0) * 0.3,
        4
    ) * 100                                                   AS composite_score
FROM marts.fact_sales   fs
JOIN marts.dim_sellers  ds USING (seller_id)
WHERE fs.is_delivered = TRUE
GROUP BY ds.seller_id, ds.seller_name, ds.state, ds.seller_tier,
         ds.revenue_rank, ds.avg_review_score, ds.fulfillment_rate_pct
ORDER BY total_revenue DESC
LIMIT 50;
