-- ============================================================
-- 01_revenue_analysis.sql
-- ============================================================
-- BUSINESS QUESTION: What is our total revenue, and how is it
-- growing over time? Are we accelerating or decelerating?
--
-- KEY METRICS:
--   - Total GMV (Gross Merchandise Value): sum of all product revenue
--   - Net Revenue: GMV + freight - refunds/cancellations
--   - Year-over-Year (YoY) growth: compare current year vs last year
--   - Month-over-Month (MoM) growth: compare current month vs last month
--
-- WINDOW FUNCTIONS USED:
--   LAG() → Get the value from a previous row (e.g., last month's revenue)
--   This lets us compute % change without a self-join.
--   Syntax: LAG(column, offset) OVER (ORDER BY date_column)
-- ============================================================

-- ── Part 1: Overall Revenue Summary ──────────────────────────────────────────
WITH overall_summary AS (
    SELECT
        -- Total Gross Merchandise Value (all product revenue)
        SUM(gross_revenue)                              AS total_gmv,
        
        -- Net revenue (only delivered orders — exclude cancelled)
        SUM(CASE WHEN is_delivered THEN gross_revenue ELSE 0 END) AS net_revenue,
        
        -- Freight revenue (separate revenue stream)
        SUM(allocated_freight)                          AS freight_revenue,
        
        -- Estimated profit
        SUM(CASE WHEN is_delivered THEN gross_profit ELSE 0 END)  AS total_gross_profit,
        
        -- Overall margin
        ROUND(
            SUM(CASE WHEN is_delivered THEN gross_profit ELSE 0 END)
            / NULLIF(SUM(CASE WHEN is_delivered THEN gross_revenue ELSE 0 END), 0) * 100,
            2
        )                                               AS overall_margin_pct,
        
        COUNT(DISTINCT order_id)                        AS total_orders,
        COUNT(DISTINCT customer_id)                     AS unique_customers,
        
        -- Average Order Value
        ROUND(
            SUM(gross_revenue) / NULLIF(COUNT(DISTINCT order_id), 0),
            2
        )                                               AS avg_order_value

    FROM marts.fact_sales
    WHERE NOT is_cancelled
),

-- ── Part 2: Annual Revenue with YoY Growth ────────────────────────────────────
annual_revenue AS (
    SELECT
        order_year                                      AS year,
        SUM(gross_revenue)                              AS annual_revenue,
        SUM(gross_profit)                               AS annual_profit,
        COUNT(DISTINCT order_id)                        AS orders,
        COUNT(DISTINCT customer_id)                     AS customers
    FROM marts.fact_sales
    WHERE is_delivered = TRUE
    GROUP BY order_year
    ORDER BY order_year
),

annual_with_growth AS (
    SELECT
        year,
        annual_revenue,
        annual_profit,
        orders,
        customers,
        
        -- LAG gets last year's revenue
        LAG(annual_revenue) OVER (ORDER BY year)        AS prev_year_revenue,
        
        -- YoY growth = (current - previous) / previous * 100
        ROUND(
            (annual_revenue - LAG(annual_revenue) OVER (ORDER BY year))
            / NULLIF(LAG(annual_revenue) OVER (ORDER BY year), 0) * 100,
            2
        )                                               AS yoy_growth_pct,
        
        ROUND(annual_revenue / NULLIF(orders, 0), 2)   AS aov

    FROM annual_revenue
)

-- Return the overall summary first
SELECT 'OVERALL SUMMARY' AS report_section, NULL::integer AS year,
       total_gmv AS revenue, total_gross_profit AS profit,
       total_orders AS orders, overall_margin_pct AS margin_pct,
       NULL::numeric AS yoy_growth_pct
FROM overall_summary

UNION ALL

-- Then annual breakdown
SELECT 'ANNUAL BREAKDOWN' AS report_section, year,
       annual_revenue AS revenue, annual_profit AS profit,
       orders, ROUND(annual_profit / NULLIF(annual_revenue, 0) * 100, 2) AS margin_pct,
       yoy_growth_pct
FROM annual_with_growth
ORDER BY report_section DESC, year;
