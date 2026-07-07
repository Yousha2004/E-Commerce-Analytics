-- 10_profit_analysis.sql — Profit & Margin Analysis by Category
-- BUSINESS QUESTION: Which categories are most/least profitable?
-- Where should we invest in growth? Which to exit?
WITH category_profit AS (
    SELECT
        dp.department,
        dp.category_name,
        dp.price_tier,
        COUNT(DISTINCT fs.order_id)                           AS orders,
        SUM(fs.quantity)                                      AS units_sold,
        ROUND(SUM(fs.gross_revenue), 2)                       AS revenue,
        ROUND(SUM(fs.estimated_cogs), 2)                      AS total_cogs,
        ROUND(SUM(fs.gross_profit),  2)                       AS gross_profit,
        ROUND(SUM(fs.discount_amount), 2)                     AS total_discounts,
        ROUND(AVG(fs.gross_margin_pct), 2)                    AS avg_margin_pct,
        ROUND(AVG(dp.avg_review_score), 2)                    AS avg_rating
    FROM marts.fact_sales   fs
    JOIN marts.dim_products dp USING (product_id)
    WHERE fs.is_delivered = TRUE
      AND fs.estimated_cogs > 0  -- Only items with known COGS
    GROUP BY dp.department, dp.category_name, dp.price_tier
)
SELECT
    department,
    category_name,
    price_tier,
    orders,
    units_sold,
    revenue,
    total_cogs,
    gross_profit,
    avg_margin_pct,
    total_discounts,
    avg_rating,
    -- Profit rank (1 = most profitable)
    RANK() OVER (ORDER BY gross_profit DESC)                  AS profit_rank,
    -- Revenue contribution
    ROUND(revenue / SUM(revenue) OVER () * 100, 2)            AS revenue_share_pct,
    -- Profit contribution
    ROUND(gross_profit / NULLIF(SUM(gross_profit) OVER (), 0) * 100, 2) AS profit_share_pct,
    -- BCG Matrix classification (Growth-Share Matrix)
    CASE
        WHEN avg_margin_pct >= 35 AND revenue >= 10000 THEN 'Star (High Margin, High Revenue)'
        WHEN avg_margin_pct >= 35 AND revenue <  10000 THEN 'Question Mark (High Margin, Low Revenue)'
        WHEN avg_margin_pct <  35 AND revenue >= 10000 THEN 'Cash Cow (Low Margin, High Revenue)'
        ELSE 'Dog (Low Margin, Low Revenue)'
    END AS bcg_classification
FROM category_profit
ORDER BY gross_profit DESC;
