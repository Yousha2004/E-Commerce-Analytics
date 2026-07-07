-- ============================================================
-- 03_top_products.sql — Top Products by Revenue
-- ============================================================
-- BUSINESS QUESTION: Which products drive the most revenue?
-- What's our product concentration (does 20% of products make 80% of revenue)?
--
-- PARETO ANALYSIS: The 80/20 rule often applies to e-commerce.
-- We use cumulative revenue % to find the "vital few" products.
-- ============================================================

WITH product_revenue AS (
    SELECT
        fs.product_id,
        dp.product_name,
        dp.category_name,
        dp.department,
        dp.price_tier,
        dp.list_price,
        
        ROUND(SUM(fs.gross_revenue), 2)                     AS total_revenue,
        ROUND(SUM(fs.gross_profit),  2)                     AS total_profit,
        ROUND(SUM(fs.estimated_cogs), 2)                    AS total_cogs,
        SUM(fs.quantity)                                    AS total_units_sold,
        COUNT(DISTINCT fs.order_id)                         AS total_orders,
        COUNT(DISTINCT fs.customer_id)                      AS unique_buyers,
        ROUND(AVG(fs.selling_price), 2)                     AS avg_selling_price,
        ROUND(AVG(dp.avg_review_score), 2)                  AS avg_rating

    FROM marts.fact_sales   fs
    JOIN marts.dim_products dp USING (product_id)
    WHERE fs.is_delivered = TRUE
    GROUP BY
        fs.product_id, dp.product_name, dp.category_name,
        dp.department, dp.price_tier, dp.list_price, dp.avg_review_score
),

ranked AS (
    SELECT
        *,
        -- Revenue rank (1 = top seller)
        RANK() OVER (ORDER BY total_revenue DESC)           AS revenue_rank,
        
        -- Revenue share of total
        ROUND(
            total_revenue / SUM(total_revenue) OVER () * 100,
            3
        )                                                   AS revenue_share_pct,
        
        -- Cumulative revenue % (for Pareto analysis)
        ROUND(
            SUM(total_revenue) OVER (ORDER BY total_revenue DESC
                ROWS UNBOUNDED PRECEDING)
            / SUM(total_revenue) OVER () * 100,
            2
        )                                                   AS cumulative_revenue_pct,
        
        -- Margin %
        ROUND(total_profit / NULLIF(total_revenue, 0) * 100, 2) AS margin_pct

    FROM product_revenue
)

SELECT
    revenue_rank,
    product_id,
    product_name,
    category_name,
    department,
    price_tier,
    list_price,
    avg_selling_price,
    total_revenue,
    total_profit,
    margin_pct,
    total_units_sold,
    total_orders,
    unique_buyers,
    avg_rating,
    revenue_share_pct,
    cumulative_revenue_pct,
    
    -- Pareto classification
    CASE
        WHEN cumulative_revenue_pct <= 80 THEN 'Top 80% Revenue'
        WHEN cumulative_revenue_pct <= 95 THEN 'Mid Tier'
        ELSE 'Long Tail'
    END AS pareto_tier

FROM ranked
ORDER BY revenue_rank
LIMIT 50;  -- Top 50 products
