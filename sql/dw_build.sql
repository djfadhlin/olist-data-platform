
-- T4: Olist PostgreSQL dimensional warehouse
-- Full rebuild, executed within one Python-managed transaction.
-- WARNING: Replaces the dw schema. Build marts only after DW.

DROP SCHEMA IF EXISTS dw CASCADE;
CREATE SCHEMA dw;

-- =========================================================
-- DIMENSION 1: DATE
-- Grain: one calendar day
-- =========================================================

CREATE TABLE dw.dim_date AS
SELECT
    d::date AS date_key,
    EXTRACT(YEAR FROM d)::integer AS year,
    EXTRACT(MONTH FROM d)::integer AS month,
    EXTRACT(DAY FROM d)::integer AS day,
    EXTRACT(QUARTER FROM d)::integer AS quarter,
    EXTRACT(ISODOW FROM d)::integer AS iso_weekday,
    date_trunc('month', d)::date AS month_start,
    (
        d::date >= DATE '2017-01-01'
        AND d::date < DATE '2018-09-01'
    ) AS is_complete_month
FROM generate_series(
    TIMESTAMP '2016-01-01',
    TIMESTAMP '2020-12-31',
    INTERVAL '1 day'
) AS s(d);

ALTER TABLE dw.dim_date
    ADD CONSTRAINT pk_dim_date PRIMARY KEY (date_key);

-- =========================================================
-- DIMENSION 2: GEOLOCATION
-- Grain: one ZIP prefix
-- Invalid Brazilian coordinates are excluded.
-- UNKNOWN preserves FK for missing ZIP prefixes.
-- =========================================================

CREATE TABLE dw.dim_geo AS
WITH valid_geo AS (
    SELECT
        geolocation_zip_code_prefix AS zip_code_prefix,
        geolocation_lat,
        geolocation_lng,
        NULLIF(BTRIM(geolocation_city), '') AS city,
        NULLIF(BTRIM(geolocation_state), '') AS state
    FROM raw.olist_geolocation_dataset
    WHERE geolocation_zip_code_prefix IS NOT NULL
      AND geolocation_lat BETWEEN -34 AND 5
      AND geolocation_lng BETWEEN -74 AND -35
),
aggregated AS (
    SELECT
        zip_code_prefix,
        AVG(geolocation_lat) AS latitude,
        AVG(geolocation_lng) AS longitude,
        MODE() WITHIN GROUP (ORDER BY city) AS city,
        MODE() WITHIN GROUP (ORDER BY state) AS state,
        COUNT(*)::bigint AS source_points
    FROM valid_geo
    GROUP BY zip_code_prefix
)
SELECT
    zip_code_prefix::varchar AS geo_key,
    zip_code_prefix::varchar AS zip_code_prefix,
    latitude,
    longitude,
    city,
    state,
    source_points,
    FALSE AS is_unknown
FROM aggregated

UNION ALL

SELECT
    'UNKNOWN'::varchar,
    NULL::varchar,
    NULL::double precision,
    NULL::double precision,
    'Unknown'::text,
    'Unknown'::varchar,
    0::bigint,
    TRUE;

ALTER TABLE dw.dim_geo
    ADD CONSTRAINT pk_dim_geo PRIMARY KEY (geo_key);

-- =========================================================
-- DIMENSION 3: CUSTOMER
-- Grain: one real person (customer_unique_id)
-- SCD Type 1: choose latest order-specific customer attrs.
-- =========================================================

CREATE TABLE dw.dim_customer AS
WITH chosen AS (
    SELECT DISTINCT ON (c.customer_unique_id)
        c.customer_unique_id,
        c.customer_id AS latest_customer_id,
        c.customer_zip_code_prefix,
        c.customer_city,
        c.customer_state,
        o.order_purchase_timestamp AS latest_purchase_at
    FROM raw.olist_customers_dataset AS c
    LEFT JOIN raw.olist_orders_dataset AS o
        ON o.customer_id = c.customer_id
    WHERE c.customer_unique_id IS NOT NULL
    ORDER BY
        c.customer_unique_id,
        o.order_purchase_timestamp DESC NULLS LAST,
        c.customer_id DESC
)
SELECT
    x.customer_unique_id,
    x.latest_customer_id,
    x.customer_zip_code_prefix,
    x.customer_city AS city,
    x.customer_state AS state,
    COALESCE(g.geo_key, 'UNKNOWN')::varchar AS geo_key,
    x.latest_purchase_at
FROM chosen AS x
LEFT JOIN dw.dim_geo AS g
    ON g.geo_key = x.customer_zip_code_prefix;

ALTER TABLE dw.dim_customer
    ADD CONSTRAINT pk_dim_customer
    PRIMARY KEY (customer_unique_id);

ALTER TABLE dw.dim_customer
    ADD CONSTRAINT fk_customer_geo
    FOREIGN KEY (geo_key)
    REFERENCES dw.dim_geo (geo_key);

-- =========================================================
-- DIMENSION 4: PRODUCT
-- Grain: one product_id
-- Fix source typo: lenght -> length.
-- =========================================================

CREATE TABLE dw.dim_product AS
WITH translation AS (
    SELECT
        product_category_name,
        MIN(NULLIF(BTRIM(product_category_name_english), ''))
            AS category_english
    FROM raw.product_category_name_translation
    GROUP BY product_category_name
)
SELECT
    p.product_id,
    p.product_category_name AS category_original,
    COALESCE(
        t.category_english,
        NULLIF(BTRIM(p.product_category_name), ''),
        'unknown'
    ) AS category_english,
    p.product_name_lenght AS product_name_length,
    p.product_description_lenght AS product_description_length,
    p.product_photos_qty,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm
FROM raw.olist_products_dataset AS p
LEFT JOIN translation AS t
    ON t.product_category_name = p.product_category_name;

ALTER TABLE dw.dim_product
    ADD CONSTRAINT pk_dim_product PRIMARY KEY (product_id);

-- =========================================================
-- DIMENSION 5: SELLER
-- Grain: one seller_id
-- =========================================================

CREATE TABLE dw.dim_seller AS
SELECT
    s.seller_id,
    s.seller_zip_code_prefix,
    s.seller_city AS city,
    s.seller_state AS state,
    COALESCE(g.geo_key, 'UNKNOWN')::varchar AS geo_key
FROM raw.olist_sellers_dataset AS s
LEFT JOIN dw.dim_geo AS g
    ON g.geo_key = s.seller_zip_code_prefix;

ALTER TABLE dw.dim_seller
    ADD CONSTRAINT pk_dim_seller PRIMARY KEY (seller_id);

ALTER TABLE dw.dim_seller
    ADD CONSTRAINT fk_seller_geo
    FOREIGN KEY (geo_key)
    REFERENCES dw.dim_geo (geo_key);

-- =========================================================
-- FACT 1: ORDER HEADER
-- Grain: one order_id, including incomplete orders
-- =========================================================

CREATE TABLE dw.fact_order AS
WITH item_totals AS (
    SELECT
        order_id,
        COUNT(*)::integer AS item_count,
        SUM(price)::numeric AS item_value,
        SUM(freight_value)::numeric AS freight_value
    FROM raw.olist_order_items_dataset
    GROUP BY order_id
),
payment_totals AS (
    SELECT
        order_id,
        COUNT(*)::integer AS payment_count,
        SUM(payment_value)::numeric AS payment_value
    FROM raw.olist_order_payments_dataset
    GROUP BY order_id
)
SELECT
    o.order_id,
    c.customer_unique_id,
    o.customer_id AS source_customer_id,
    c.geo_key AS customer_geo_key,
    c.state AS customer_state,
    o.order_status,

    o.order_purchase_timestamp,
    o.order_purchase_timestamp::date AS purchase_date_key,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    o.order_estimated_delivery_date::date AS estimated_date_key,

    CASE
        WHEN o.order_status <> 'delivered'
          OR o.order_delivered_customer_date IS NULL
          OR o.order_estimated_delivery_date IS NULL
        THEN NULL
        ELSE (
            o.order_delivered_customer_date::date
            > o.order_estimated_delivery_date::date
        )
    END AS is_late,

    CASE
        WHEN o.order_delivered_customer_date IS NOT NULL
         AND o.order_purchase_timestamp IS NOT NULL
        THEN (
            EXTRACT(
                EPOCH FROM (
                    o.order_delivered_customer_date
                    - o.order_purchase_timestamp
                )
            ) / 86400.0
        )::numeric
        ELSE NULL
    END AS delivery_days,

    COALESCE(i.item_count, 0)::integer AS item_count,
    COALESCE(p.payment_count, 0)::integer AS payment_count,
    COALESCE(i.item_value, 0)::numeric AS item_value,
    COALESCE(i.freight_value, 0)::numeric AS freight_value,
    COALESCE(p.payment_value, 0)::numeric AS payment_value,

    (i.order_id IS NULL) AS has_no_items,
    (p.order_id IS NULL) AS has_no_payment
FROM raw.olist_orders_dataset AS o
JOIN raw.olist_customers_dataset AS source_customer
    ON source_customer.customer_id = o.customer_id
JOIN dw.dim_customer AS c
    ON c.customer_unique_id =
       source_customer.customer_unique_id
LEFT JOIN item_totals AS i
    ON i.order_id = o.order_id
LEFT JOIN payment_totals AS p
    ON p.order_id = o.order_id;

ALTER TABLE dw.fact_order
    ADD CONSTRAINT pk_fact_order PRIMARY KEY (order_id);

ALTER TABLE dw.fact_order
    ADD CONSTRAINT fk_order_customer
    FOREIGN KEY (customer_unique_id)
    REFERENCES dw.dim_customer (customer_unique_id);

ALTER TABLE dw.fact_order
    ADD CONSTRAINT fk_order_geo
    FOREIGN KEY (customer_geo_key)
    REFERENCES dw.dim_geo (geo_key);

ALTER TABLE dw.fact_order
    ADD CONSTRAINT fk_order_purchase_date
    FOREIGN KEY (purchase_date_key)
    REFERENCES dw.dim_date (date_key);

ALTER TABLE dw.fact_order
    ADD CONSTRAINT fk_order_estimated_date
    FOREIGN KEY (estimated_date_key)
    REFERENCES dw.dim_date (date_key);

-- =========================================================
-- FACT 2: ORDER ITEM
-- Grain: (order_id, order_item_id)
-- =========================================================

CREATE TABLE dw.fact_order_item AS
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    i.shipping_limit_date,
    i.price,
    i.freight_value,
    (i.price + i.freight_value)::numeric
        AS item_total_value
FROM raw.olist_order_items_dataset AS i;

ALTER TABLE dw.fact_order_item
    ADD CONSTRAINT pk_fact_order_item
    PRIMARY KEY (order_id, order_item_id);

ALTER TABLE dw.fact_order_item
    ADD CONSTRAINT fk_item_order
    FOREIGN KEY (order_id)
    REFERENCES dw.fact_order (order_id);

ALTER TABLE dw.fact_order_item
    ADD CONSTRAINT fk_item_product
    FOREIGN KEY (product_id)
    REFERENCES dw.dim_product (product_id);

ALTER TABLE dw.fact_order_item
    ADD CONSTRAINT fk_item_seller
    FOREIGN KEY (seller_id)
    REFERENCES dw.dim_seller (seller_id);

-- =========================================================
-- FACT 3: PAYMENT
-- Grain: (order_id, payment_sequential)
-- =========================================================

CREATE TABLE dw.fact_payment AS
SELECT
    p.order_id,
    p.payment_sequential,
    p.payment_type,
    p.payment_installments,
    p.payment_value
FROM raw.olist_order_payments_dataset AS p;

ALTER TABLE dw.fact_payment
    ADD CONSTRAINT pk_fact_payment
    PRIMARY KEY (order_id, payment_sequential);

ALTER TABLE dw.fact_payment
    ADD CONSTRAINT fk_payment_order
    FOREIGN KEY (order_id)
    REFERENCES dw.fact_order (order_id);

-- =========================================================
-- FACT 4: REVIEW
-- Grain: one reviewed order
-- Rule: most recent answer timestamp,
-- then most recent review creation, then review_id.
-- Record total source reviews for each order.
-- =========================================================

CREATE TABLE dw.fact_review AS
WITH ranked AS (
    SELECT
        r.*,
        COUNT(*) OVER (
            PARTITION BY r.order_id
        )::integer AS review_count,
        ROW_NUMBER() OVER (
            PARTITION BY r.order_id
            ORDER BY
                r.review_answer_timestamp DESC NULLS LAST,
                r.review_creation_date DESC NULLS LAST,
                r.review_id DESC
        ) AS review_rank
    FROM raw.olist_order_reviews_dataset AS r
)
SELECT
    order_id,
    review_id,
    review_score,
    review_comment_title,
    review_comment_message,
    review_creation_date,
    review_answer_timestamp,
    review_count
FROM ranked
WHERE review_rank = 1;

ALTER TABLE dw.fact_review
    ADD CONSTRAINT pk_fact_review PRIMARY KEY (order_id);

ALTER TABLE dw.fact_review
    ADD CONSTRAINT fk_review_order
    FOREIGN KEY (order_id)
    REFERENCES dw.fact_order (order_id);

-- =========================================================
-- Query performance indexes
-- =========================================================

CREATE INDEX idx_fact_order_purchase
    ON dw.fact_order (purchase_date_key);

CREATE INDEX idx_fact_order_status
    ON dw.fact_order (order_status);

CREATE INDEX idx_fact_order_customer
    ON dw.fact_order (customer_unique_id);

CREATE INDEX idx_item_product
    ON dw.fact_order_item (product_id);

CREATE INDEX idx_item_seller
    ON dw.fact_order_item (seller_id);

CREATE INDEX idx_payment_order
    ON dw.fact_payment (order_id);

ANALYZE dw.dim_date;
ANALYZE dw.dim_geo;
ANALYZE dw.dim_customer;
ANALYZE dw.dim_product;
ANALYZE dw.dim_seller;
ANALYZE dw.fact_order;
ANALYZE dw.fact_order_item;
ANALYZE dw.fact_payment;
ANALYZE dw.fact_review;
