
-- T5: Olist Gold analytical marts
-- Rebuilt transactionally from dw and stream.
-- Revenue = product price of delivered orders; freight is separate.
-- Dates in monthly marts are purchase months.

DROP SCHEMA IF EXISTS mart CASCADE;
CREATE SCHEMA mart;

-- =========================================================
-- 1. Q1: MONTHLY SALES
-- Grain: purchase month x English category x customer state
-- Only delivered orders contribute revenue.
-- =========================================================

CREATE TABLE mart.monthly_sales AS
SELECT
    date_trunc('month', o.order_purchase_timestamp)::date
        AS month_start,
    p.category_english AS category,
    COALESCE(o.customer_state, 'UNKNOWN') AS customer_state,
    d.is_complete_month,
    COUNT(DISTINCT o.order_id)::bigint AS order_count,
    COUNT(*)::bigint AS item_count,
    SUM(i.price)::numeric(18,2) AS product_revenue_brl,
    SUM(i.freight_value)::numeric(18,2) AS freight_brl,
    SUM(i.item_total_value)::numeric(18,2)
        AS product_plus_freight_brl
FROM dw.fact_order_item i
JOIN dw.fact_order o
    ON o.order_id = i.order_id
JOIN dw.dim_product p
    ON p.product_id = i.product_id
JOIN dw.dim_date d
    ON d.date_key = o.purchase_date_key
WHERE o.order_status = 'delivered'
GROUP BY
    date_trunc('month', o.order_purchase_timestamp)::date,
    p.category_english,
    COALESCE(o.customer_state, 'UNKNOWN'),
    d.is_complete_month;

ALTER TABLE mart.monthly_sales
    ADD CONSTRAINT pk_monthly_sales
    PRIMARY KEY (month_start, category, customer_state);

CREATE INDEX idx_monthly_sales_month
    ON mart.monthly_sales(month_start);

-- =========================================================
-- 2. Q2: DELIVERY PERFORMANCE
-- Grain: purchase month x customer state
-- Late rate denominator = orders where is_late IS NOT NULL.
-- Reviews are at most one row per order.
-- =========================================================

CREATE TABLE mart.delivery_performance AS
SELECT
    date_trunc('month', o.order_purchase_timestamp)::date
        AS month_start,
    COALESCE(o.customer_state, 'UNKNOWN') AS customer_state,
    d.is_complete_month,
    COUNT(*)::bigint AS total_orders,
    COUNT(*) FILTER (
        WHERE o.order_status = 'delivered'
    )::bigint AS delivered_orders,
    COUNT(o.is_late)::bigint AS evaluable_orders,
    COUNT(*) FILTER (
        WHERE o.is_late IS TRUE
    )::bigint AS late_orders,
    COUNT(*) FILTER (
        WHERE o.is_late IS FALSE
    )::bigint AS on_time_orders,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE o.is_late IS TRUE
        ) / NULLIF(COUNT(o.is_late), 0),
        2
    ) AS late_rate_pct,
    ROUND(
        AVG(o.delivery_days) FILTER (
            WHERE o.order_status = 'delivered'
              AND o.delivery_days >= 0
        ),
        2
    ) AS avg_delivery_days,
    COUNT(r.review_score)::bigint AS reviewed_orders,
    ROUND(AVG(r.review_score), 3) AS avg_review_score,
    ROUND(
        AVG(r.review_score) FILTER (
            WHERE o.is_late IS FALSE
        ),
        3
    ) AS avg_review_on_time,
    ROUND(
        AVG(r.review_score) FILTER (
            WHERE o.is_late IS TRUE
        ),
        3
    ) AS avg_review_late
FROM dw.fact_order o
JOIN dw.dim_date d
    ON d.date_key = o.purchase_date_key
LEFT JOIN dw.fact_review r
    ON r.order_id = o.order_id
GROUP BY
    date_trunc('month', o.order_purchase_timestamp)::date,
    COALESCE(o.customer_state, 'UNKNOWN'),
    d.is_complete_month;

ALTER TABLE mart.delivery_performance
    ADD CONSTRAINT pk_delivery_performance
    PRIMARY KEY (month_start, customer_state);

-- =========================================================
-- 3. Q3: SELLER SCORECARD
-- Grain: seller_id
-- Aggregate items to seller-order before joining order/review.
-- Seller review represents the shared order review.
-- =========================================================

CREATE TABLE mart.seller_scorecard AS
WITH seller_orders AS (
    SELECT
        seller_id,
        order_id,
        COUNT(*)::bigint AS items_sold,
        SUM(price) AS product_value,
        SUM(freight_value) AS freight_value
    FROM dw.fact_order_item
    GROUP BY seller_id, order_id
)
SELECT
    s.seller_id,
    ds.state AS seller_state,
    ds.geo_key,
    COUNT(*)::bigint AS total_orders,
    COUNT(*) FILTER (
        WHERE o.order_status = 'delivered'
    )::bigint AS delivered_orders,
    SUM(s.items_sold)::bigint AS total_items,
    COALESCE(
        SUM(s.product_value) FILTER (
            WHERE o.order_status = 'delivered'
        ), 0
    )::numeric(18,2) AS delivered_product_revenue_brl,
    COALESCE(
        SUM(s.freight_value) FILTER (
            WHERE o.order_status = 'delivered'
        ), 0
    )::numeric(18,2) AS delivered_freight_brl,
    COUNT(o.is_late)::bigint AS evaluable_orders,
    COUNT(*) FILTER (
        WHERE o.is_late IS TRUE
    )::bigint AS late_orders,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE o.is_late IS TRUE
        ) / NULLIF(COUNT(o.is_late), 0),
        2
    ) AS late_rate_pct,
    ROUND(
        AVG(r.review_score), 3
    ) AS avg_review_score,
    (COUNT(o.is_late) >= 30) AS eligible_for_late_ranking
FROM seller_orders s
JOIN dw.fact_order o
    ON o.order_id = s.order_id
JOIN dw.dim_seller ds
    ON ds.seller_id = s.seller_id
LEFT JOIN dw.fact_review r
    ON r.order_id = s.order_id
GROUP BY
    s.seller_id,
    ds.state,
    ds.geo_key;

ALTER TABLE mart.seller_scorecard
    ADD CONSTRAINT pk_seller_scorecard PRIMARY KEY (seller_id);

-- =========================================================
-- 4. Q4: CUSTOMER RFM
-- Grain: customer_unique_id
-- Reference date = max purchase date of delivered orders + 1 day.
-- F uses fixed business thresholds, not raw quintiles.
-- =========================================================

CREATE TABLE mart.customer_rfm AS
WITH reference_date AS (
    SELECT
        MAX(order_purchase_timestamp::date) + 1
            AS as_of_date
    FROM dw.fact_order
    WHERE order_status = 'delivered'
),
customer_metrics AS (
    SELECT
        c.customer_unique_id,
        r.as_of_date,
        MAX(o.order_purchase_timestamp::date) FILTER (
            WHERE o.order_status = 'delivered'
        ) AS last_purchase_date,
        COUNT(o.order_id) FILTER (
            WHERE o.order_status = 'delivered'
        )::integer AS frequency,
        COALESCE(
            SUM(o.item_value) FILTER (
                WHERE o.order_status = 'delivered'
            ), 0
        )::numeric(18,2) AS monetary_brl
    FROM dw.dim_customer c
    CROSS JOIN reference_date r
    LEFT JOIN dw.fact_order o
        ON o.customer_unique_id = c.customer_unique_id
    GROUP BY
        c.customer_unique_id,
        r.as_of_date
),
scored AS (
    SELECT
        *,
        (as_of_date - last_purchase_date)::integer
            AS recency_days,
        CASE
            WHEN last_purchase_date IS NULL THEN 0
            WHEN (as_of_date - last_purchase_date) <= 30 THEN 5
            WHEN (as_of_date - last_purchase_date) <= 90 THEN 4
            WHEN (as_of_date - last_purchase_date) <= 180 THEN 3
            WHEN (as_of_date - last_purchase_date) <= 365 THEN 2
            ELSE 1
        END AS r_score,
        CASE
            WHEN frequency >= 3 THEN 5
            WHEN frequency = 2 THEN 3
            WHEN frequency = 1 THEN 1
            ELSE 0
        END AS f_score,
        CASE
            WHEN frequency = 0 THEN 0
            WHEN monetary_brl >= 500 THEN 5
            WHEN monetary_brl >= 250 THEN 4
            WHEN monetary_brl >= 100 THEN 3
            WHEN monetary_brl >= 50 THEN 2
            ELSE 1
        END AS m_score
    FROM customer_metrics
)
SELECT
    customer_unique_id,
    as_of_date,
    last_purchase_date,
    recency_days,
    frequency,
    monetary_brl,
    r_score,
    f_score,
    m_score,
    CASE
        WHEN frequency = 0 THEN 'NO_DELIVERED_ORDER'
        WHEN r_score >= 4 AND f_score >= 3 THEN 'CHAMPIONS'
        WHEN r_score >= 4 THEN 'RECENT'
        WHEN f_score >= 3 THEN 'LOYAL'
        WHEN r_score <= 2 THEN 'AT_RISK'
        ELSE 'REGULAR'
    END AS segment
FROM scored;

ALTER TABLE mart.customer_rfm
    ADD CONSTRAINT pk_customer_rfm
    PRIMARY KEY (customer_unique_id);

CREATE INDEX idx_customer_rfm_segment
    ON mart.customer_rfm(segment);

-- =========================================================
-- 5. STREAM FRESHNESS
-- Grain: minute of consumption (UTC timestamptz)
-- Uses unique valid events recorded in PostgreSQL.
-- =========================================================

CREATE TABLE mart.stream_freshness AS
SELECT
    date_trunc('minute', consumed_at)
        AS consumed_minute,
    COUNT(*)::bigint AS valid_unique_events,
    ROUND(
        AVG(EXTRACT(EPOCH FROM (
            consumed_at - produced_at
        )) * 1000.0)::numeric,
        2
    ) AS avg_freshness_ms,
    ROUND(
        (
            PERCENTILE_CONT(0.50) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (
                    consumed_at - produced_at
                )) * 1000.0
            )
        )::numeric,
        2
    ) AS p50_freshness_ms,
    ROUND(
        (
            PERCENTILE_CONT(0.95) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (
                    consumed_at - produced_at
                )) * 1000.0
            )
        )::numeric,
        2
    ) AS p95_freshness_ms,
    COUNT(*) FILTER (
        WHERE consumed_at < produced_at
    )::bigint AS negative_latency_events
FROM stream.order_events
WHERE produced_at IS NOT NULL
  AND consumed_at IS NOT NULL
GROUP BY date_trunc('minute', consumed_at);

ALTER TABLE mart.stream_freshness
    ADD CONSTRAINT pk_stream_freshness
    PRIMARY KEY (consumed_minute);

-- =========================================================
-- 6. PAYMENT RECONCILIATION
-- Grain: one order
-- Tolerance: BRL 0.01
-- Voucher / installment = investigation categories, not
-- proof that a financial discrepancy is fully explained.
-- =========================================================

CREATE TABLE mart.payment_reconciliation AS
WITH payment_features AS (
    SELECT
        order_id,
        BOOL_OR(
            LOWER(payment_type) = 'voucher'
        ) AS has_voucher,
        BOOL_OR(
            COALESCE(payment_installments, 0) > 1
        ) AS has_installments,
        STRING_AGG(
            DISTINCT payment_type,
            ', ' ORDER BY payment_type
        ) AS payment_types
    FROM dw.fact_payment
    GROUP BY order_id
),
base AS (
    SELECT
        o.order_id,
        o.order_status,
        o.has_no_items,
        o.has_no_payment,
        o.item_count,
        o.payment_count,
        o.item_value::numeric(18,2) AS item_value_brl,
        o.freight_value::numeric(18,2) AS freight_brl,
        (o.item_value + o.freight_value)::numeric(18,2)
            AS expected_total_brl,
        o.payment_value::numeric(18,2) AS paid_total_brl,
        (
            o.payment_value - o.item_value - o.freight_value
        )::numeric(18,2) AS difference_brl,
        COALESCE(p.has_voucher, FALSE) AS has_voucher,
        COALESCE(p.has_installments, FALSE)
            AS has_installments,
        p.payment_types
    FROM dw.fact_order o
    LEFT JOIN payment_features p
        ON p.order_id = o.order_id
)
SELECT
    *,
    CASE
        WHEN has_no_items THEN 'NO_ITEMS'
        WHEN has_no_payment THEN 'NO_PAYMENT'
        WHEN ABS(difference_brl) <= 0.01 THEN 'MATCH'
        WHEN has_voucher THEN 'VOUCHER_REVIEW'
        WHEN has_installments THEN 'INSTALLMENT_REVIEW'
        ELSE 'UNEXPLAINED'
    END AS reconciliation_class,
    (
        NOT has_no_items
        AND NOT has_no_payment
        AND ABS(difference_brl) <= 0.01
    ) AS is_matched
FROM base;

ALTER TABLE mart.payment_reconciliation
    ADD CONSTRAINT pk_payment_reconciliation
    PRIMARY KEY (order_id);

CREATE INDEX idx_payment_reconciliation_class
    ON mart.payment_reconciliation(reconciliation_class);

-- =========================================================
-- Query statistics
-- =========================================================

ANALYZE mart.monthly_sales;
ANALYZE mart.delivery_performance;
ANALYZE mart.seller_scorecard;
ANALYZE mart.customer_rfm;
ANALYZE mart.stream_freshness;
ANALYZE mart.payment_reconciliation;
