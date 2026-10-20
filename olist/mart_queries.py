
"""Shared SQL queries for T5 report and Jupyter dashboard.

All dashboard figures should originate from these queries
or directly from the corresponding mart tables.
"""

QUERIES = {
    "q1_monthly_revenue": """
        SELECT
            month_start,
            ROUND(SUM(product_revenue_brl), 2)
                AS product_revenue_brl,
            ROUND(SUM(freight_brl), 2)
                AS freight_brl,
            SUM(item_count)::bigint AS item_count
        FROM mart.monthly_sales
        WHERE is_complete_month
        GROUP BY month_start
        ORDER BY month_start
    """,

    "q1_top_categories": """
        SELECT
            category,
            ROUND(SUM(product_revenue_brl), 2)
                AS product_revenue_brl,
            SUM(item_count)::bigint AS item_count
        FROM mart.monthly_sales
        WHERE is_complete_month
        GROUP BY category
        ORDER BY product_revenue_brl DESC, category
        LIMIT 10
    """,

    "q2_delivery_summary": """
        SELECT
            SUM(delivered_orders)::bigint AS delivered_orders,
            SUM(evaluable_orders)::bigint AS evaluable_orders,
            SUM(late_orders)::bigint AS late_orders,
            ROUND(
                100.0 * SUM(late_orders)
                / NULLIF(SUM(evaluable_orders), 0),
                2
            ) AS late_rate_pct
        FROM mart.delivery_performance
        WHERE is_complete_month
    """,

    "q2_review_vs_lateness": """
        SELECT
            CASE
                WHEN is_late THEN 'LATE'
                ELSE 'ON_TIME'
            END AS delivery_group,
            COUNT(*)::bigint AS reviewed_orders,
            ROUND(AVG(r.review_score), 3)
                AS avg_review_score
        FROM dw.fact_order o
        JOIN dw.fact_review r
          ON r.order_id = o.order_id
        JOIN dw.dim_date d
          ON d.date_key = o.purchase_date_key
        WHERE o.is_late IS NOT NULL
          AND d.is_complete_month
        GROUP BY o.is_late
        ORDER BY delivery_group
    """,

    "q3_top_sellers": """
        SELECT
            seller_id,
            seller_state,
            delivered_orders,
            evaluable_orders,
            late_orders,
            late_rate_pct,
            avg_review_score,
            delivered_product_revenue_brl
        FROM mart.seller_scorecard
        WHERE eligible_for_late_ranking
        ORDER BY
            delivered_product_revenue_brl DESC,
            seller_id
        LIMIT 10
    """,

    "q4_rfm_segments": """
        SELECT
            segment,
            COUNT(*)::bigint AS customers,
            SUM(frequency)::bigint AS delivered_orders,
            ROUND(SUM(monetary_brl), 2)
                AS monetary_brl,
            ROUND(AVG(recency_days), 2)
                AS avg_recency_days
        FROM mart.customer_rfm
        GROUP BY segment
        ORDER BY customers DESC, segment
    """,

    "freshness_overview": """
        SELECT
            SUM(valid_unique_events)::bigint
                AS valid_unique_events,
            COUNT(*)::bigint AS observed_minutes,
            MIN(consumed_minute) AS first_minute,
            MAX(consumed_minute) AS last_minute,
            SUM(negative_latency_events)::bigint
                AS negative_latency_events
        FROM mart.stream_freshness
    """,

    "reconciliation_summary": """
        SELECT
            reconciliation_class,
            COUNT(*)::bigint AS orders,
            ROUND(
                SUM(ABS(difference_brl)), 2
            ) AS absolute_difference_brl,
            ROUND(SUM(difference_brl), 2)
                AS signed_difference_brl
        FROM mart.payment_reconciliation
        GROUP BY reconciliation_class
        ORDER BY orders DESC, reconciliation_class
    """,

    "reconciliation_match_rate": """
        SELECT
            COUNT(*)::bigint AS total_orders,
            COUNT(*) FILTER (
                WHERE is_matched
            )::bigint AS matched_orders,
            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE is_matched
                ) / NULLIF(COUNT(*), 0),
                3
            ) AS match_rate_pct,
            ROUND(
                SUM(ABS(difference_brl)) FILTER (
                    WHERE NOT is_matched
                ), 2
            ) AS unmatched_absolute_difference_brl,
            ROUND(
                SUM(ABS(difference_brl)) FILTER (
                    WHERE reconciliation_class = 'UNEXPLAINED'
                ), 2
            ) AS unexplained_absolute_difference_brl
        FROM mart.payment_reconciliation
    """,
}
