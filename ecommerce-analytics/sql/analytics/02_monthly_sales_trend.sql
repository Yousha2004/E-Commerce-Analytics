-- ============================================================
-- 02_monthly_sales_trend.sql
-- ============================================================
-- BUSINESS QUESTION: How do our sales trend month over month?
-- Which months are peaks and which are troughs?
--
-- This query powers the "Sales Trend" line chart in Power BI/Streamlit.
--
-- TECHNIQUE: Rolling 3-month average (moving average)
--   A moving average smooths out weekly noise so you can see the trend.
--   Formula: avg of current month + 2 previous months.
-- ============================================================

WITH monthly_metrics AS (
    SELECT
        d.year_month,
        d.year,
        d.month_number,
        d.month_name_short,
        d.first_day_of_month                                AS month_start,
        
        -- Revenue metrics
        ROUND(SUM(fs.gross_revenue), 2)                     AS gross_revenue,
        ROUND(SUM(fs.gross_profit),  2)                     AS gross_profit,
        
        -- Order metrics
        COUNT(DISTINCT fs.order_id)                         AS order_count,
        COUNT(DISTINCT fs.customer_id)                      AS unique_customers,
        COUNT(fs.order_item_id)                             AS items_sold,
        
        -- Average order value
        ROUND(SUM(fs.gross_revenue) / NULLIF(COUNT(DISTINCT fs.order_id), 0), 2) AS avg_order_value,
        
        -- Average selling price per item
        ROUND(AVG(fs.selling_price), 2)                     AS avg_item_price

    FROM marts.fact_sales   fs
    JOIN marts.dim_date     d  ON d.date_day = fs.order_date
    WHERE fs.is_delivered = TRUE
    GROUP BY d.year_month, d.year, d.month_number, d.month_name_short, d.first_day_of_month
),

with_growth AS (
    SELECT
        year_month,
        year,
        month_number,
        month_name_short,
        month_start,
        gross_revenue,
        gross_profit,
        order_count,
        unique_customers,
        items_sold,
        avg_order_value,
        avg_item_price,
        
        -- Previous month's revenue (LAG)
        LAG(gross_revenue) OVER (ORDER BY year_month)       AS prev_month_revenue,
        
        -- Month-over-Month growth %
        ROUND(
            (gross_revenue - LAG(gross_revenue) OVER (ORDER BY year_month))
            / NULLIF(LAG(gross_revenue) OVER (ORDER BY year_month), 0) * 100,
            2
        )                                                   AS mom_growth_pct,
        
        -- 3-Month Rolling Average (smooth the trend line)
        ROUND(
            AVG(gross_revenue) OVER (
                ORDER BY year_month
                ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
            ),
            2
        )                                                   AS rolling_3m_avg_revenue,
        
        -- Cumulative revenue this year (year-to-date)
        ROUND(
            SUM(gross_revenue) OVER (
                PARTITION BY year
                ORDER BY year_month
                ROWS UNBOUNDED PRECEDING
            ),
            2
        )                                                   AS ytd_revenue,
        
        -- Month rank within year (1 = best month of year by revenue)
        RANK() OVER (
            PARTITION BY year
            ORDER BY gross_revenue DESC
        )                                                   AS rank_within_year

    FROM monthly_metrics
)

SELECT
    year_month,
    year,
    month_number,
    month_name_short,
    month_start,
    gross_revenue,
    gross_profit,
    ROUND(gross_profit / NULLIF(gross_revenue, 0) * 100, 2) AS margin_pct,
    order_count,
    unique_customers,
    items_sold,
    avg_order_value,
    prev_month_revenue,
    mom_growth_pct,
    rolling_3m_avg_revenue,
    ytd_revenue,
    rank_within_year,
    
    -- Is this month above or below the rolling average?
    CASE
        WHEN gross_revenue >= rolling_3m_avg_revenue THEN 'Above Trend'
        ELSE 'Below Trend'
    END AS trend_indicator

FROM with_growth
ORDER BY year_month;
