
"""T5 Gold Marts integration tests.

Run:
    python -m pytest tests/test_marts.py -v
"""

import pytest


def scalar(db, sql):
    with db.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]


@pytest.mark.parametrize(
    "table",
    [
        "monthly_sales",
        "delivery_performance",
        "seller_scorecard",
        "customer_rfm",
        "stream_freshness",
        "payment_reconciliation",
    ],
)
def test_mart_exists_and_is_not_empty(db, table):
    count = scalar(
        db,
        f"SELECT COUNT(*) FROM mart.{table}",
    )
    assert count > 0


@pytest.mark.parametrize(
    "table,expected",
    [
        ("seller_scorecard", 3095),
        ("customer_rfm", 96096),
        ("payment_reconciliation", 99441),
    ],
)
def test_expected_mart_grain_counts(db, table, expected):
    assert scalar(
        db,
        f"SELECT COUNT(*) FROM mart.{table}",
    ) == expected


@pytest.mark.parametrize(
    "table",
    [
        "monthly_sales",
        "delivery_performance",
        "seller_scorecard",
        "customer_rfm",
        "stream_freshness",
        "payment_reconciliation",
    ],
)
def test_mart_has_primary_key(db, table):
    assert scalar(
        db,
        f"""
        SELECT COUNT(*)
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'mart'
          AND t.relname = '{table}'
          AND c.contype = 'p'
        """,
    ) == 1


def test_monthly_revenue_matches_fact_items(db):
    result = scalar(
        db,
        """
        WITH expected AS (
            SELECT SUM(i.price) AS revenue
            FROM dw.fact_order_item i
            JOIN dw.fact_order o
              ON o.order_id = i.order_id
            WHERE o.order_status = 'delivered'
        ),
        actual AS (
            SELECT SUM(product_revenue_brl) AS revenue
            FROM mart.monthly_sales
        )
        SELECT ABS(expected.revenue - actual.revenue)
        FROM expected CROSS JOIN actual
        """,
    )
    assert result <= 0.01


def test_delivery_late_rate_denominator(db):
    assert scalar(
        db,
        """
        SELECT COUNT(*)
        FROM mart.delivery_performance
        WHERE evaluable_orders <> late_orders + on_time_orders
        """,
    ) == 0


def test_delivery_totals_match_dw(db):
    assert scalar(
        db,
        """
        SELECT
            (SELECT SUM(evaluable_orders)
             FROM mart.delivery_performance)
            =
            (SELECT COUNT(*)
             FROM dw.fact_order
             WHERE is_late IS NOT NULL)
        """,
    ) is True


def test_seller_order_counts_not_item_counts(db):
    assert scalar(
        db,
        """
        WITH source AS (
            SELECT
                seller_id,
                COUNT(DISTINCT order_id) AS orders
            FROM dw.fact_order_item
            GROUP BY seller_id
        )
        SELECT COUNT(*)
        FROM source s
        JOIN mart.seller_scorecard m
          ON m.seller_id = s.seller_id
        WHERE m.total_orders <> s.orders
        """,
    ) == 0


def test_seller_ranking_minimum_sample(db):
    assert scalar(
        db,
        """
        SELECT COUNT(*)
        FROM mart.seller_scorecard
        WHERE eligible_for_late_ranking
          IS DISTINCT FROM (evaluable_orders >= 30)
        """,
    ) == 0


def test_rfm_one_row_per_person(db):
    assert scalar(
        db,
        """
        SELECT COUNT(*)
        FROM mart.customer_rfm r
        LEFT JOIN dw.dim_customer c
          ON c.customer_unique_id = r.customer_unique_id
        WHERE c.customer_unique_id IS NULL
        """,
    ) == 0


def test_rfm_frequency_scores(db):
    assert scalar(
        db,
        """
        SELECT COUNT(*)
        FROM mart.customer_rfm
        WHERE
            (frequency = 0 AND f_score <> 0)
            OR (frequency = 1 AND f_score <> 1)
            OR (frequency = 2 AND f_score <> 3)
            OR (frequency >= 3 AND f_score <> 5)
        """,
    ) == 0


def test_rfm_reference_date_matches_source(db):
    assert scalar(
        db,
        """
        SELECT COUNT(*)
        FROM mart.customer_rfm
        WHERE as_of_date IS DISTINCT FROM (
            SELECT MAX(order_purchase_timestamp::date) + 1
            FROM dw.fact_order
            WHERE order_status = 'delivered'
        )
        """,
    ) == 0


def test_freshness_event_count_matches_stream(db):
    assert scalar(
        db,
        """
        SELECT
            (SELECT SUM(valid_unique_events)
             FROM mart.stream_freshness)
            =
            (SELECT COUNT(*)
             FROM stream.order_events
             WHERE produced_at IS NOT NULL
               AND consumed_at IS NOT NULL)
        """,
    ) is True


def test_freshness_no_negative_latency(db):
    assert scalar(
        db,
        """
        SELECT COALESCE(
            SUM(negative_latency_events), 0
        )
        FROM mart.stream_freshness
        """,
    ) == 0


def test_reconciliation_one_row_per_order(db):
    assert scalar(
        db,
        """
        SELECT
            (SELECT COUNT(*)
             FROM mart.payment_reconciliation)
            =
            (SELECT COUNT(*)
             FROM dw.fact_order)
        """,
    ) is True


def test_reconciliation_match_rate_at_least_98(db):
    match_rate = scalar(
        db,
        """
        SELECT
            100.0 * COUNT(*) FILTER (WHERE is_matched)
            / NULLIF(COUNT(*), 0)
        FROM mart.payment_reconciliation
        """,
    )
    assert match_rate >= 98


def test_reconciliation_tolerance(db):
    assert scalar(
        db,
        """
        SELECT COUNT(*)
        FROM mart.payment_reconciliation
        WHERE reconciliation_class = 'MATCH'
          AND (
              ABS(difference_brl) > 0.01
              OR has_no_items
              OR has_no_payment
          )
        """,
    ) == 0


def test_reconciliation_classes_cover_all_orders(db):
    assert scalar(
        db,
        """
        SELECT COUNT(*)
        FROM mart.payment_reconciliation
        WHERE reconciliation_class IS NULL
           OR reconciliation_class NOT IN (
               'MATCH',
               'NO_ITEMS',
               'NO_PAYMENT',
               'VOUCHER_REVIEW',
               'INSTALLMENT_REVIEW',
               'UNEXPLAINED'
           )
        """,
    ) == 0
