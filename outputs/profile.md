# Olist Data Profiling Report

Generated from source CSV by `python -m olist.profiling`.

## Ringkasan dan natural key

| Tabel | Baris | Kolom | Exact duplicates | Kandidat key | Duplicate key rows | Null key rows | Unik |
|---|---:|---:|---:|---|---:|---:|---|
| olist_customers_dataset | 99,441 | 5 | 0 | customer_id | 0 | 0 | Ya |
| olist_geolocation_dataset | 1,000,163 | 5 | 261,831 | geolocation_zip_code_prefix | 981,148 | 0 | Tidak |
| olist_order_items_dataset | 112,650 | 7 | 0 | order_id, order_item_id | 0 | 0 | Ya |
| olist_order_payments_dataset | 103,886 | 5 | 0 | order_id, payment_sequential | 0 | 0 | Ya |
| olist_order_reviews_dataset | 99,224 | 7 | 0 | review_id, order_id | 0 | 0 | Ya |
| olist_orders_dataset | 99,441 | 8 | 0 | order_id | 0 | 0 | Ya |
| olist_products_dataset | 32,951 | 9 | 0 | product_id | 0 | 0 | Ya |
| olist_sellers_dataset | 3,095 | 4 | 0 | seller_id | 0 | 0 | Ya |
| product_category_name_translation | 71 | 2 | 0 | product_category_name | 0 | 0 | Ya |

Catatan: key pada tabel reviews adalah kombinasi `(review_id, order_id)`; ZIP prefix bukan key unik di sumber geolocation.

## Missing values

### olist_customers_dataset

| Kolom | Null count | Null % |
|---|---:|---:|
| customer_id | 0 | 0.00% |
| customer_unique_id | 0 | 0.00% |
| customer_zip_code_prefix | 0 | 0.00% |
| customer_city | 0 | 0.00% |
| customer_state | 0 | 0.00% |

### olist_geolocation_dataset

| Kolom | Null count | Null % |
|---|---:|---:|
| geolocation_zip_code_prefix | 0 | 0.00% |
| geolocation_lat | 0 | 0.00% |
| geolocation_lng | 0 | 0.00% |
| geolocation_city | 0 | 0.00% |
| geolocation_state | 0 | 0.00% |

### olist_order_items_dataset

| Kolom | Null count | Null % |
|---|---:|---:|
| order_id | 0 | 0.00% |
| order_item_id | 0 | 0.00% |
| product_id | 0 | 0.00% |
| seller_id | 0 | 0.00% |
| shipping_limit_date | 0 | 0.00% |
| price | 0 | 0.00% |
| freight_value | 0 | 0.00% |

### olist_order_payments_dataset

| Kolom | Null count | Null % |
|---|---:|---:|
| order_id | 0 | 0.00% |
| payment_sequential | 0 | 0.00% |
| payment_type | 0 | 0.00% |
| payment_installments | 0 | 0.00% |
| payment_value | 0 | 0.00% |

### olist_order_reviews_dataset

| Kolom | Null count | Null % |
|---|---:|---:|
| review_id | 0 | 0.00% |
| order_id | 0 | 0.00% |
| review_score | 0 | 0.00% |
| review_comment_title | 87,656 | 88.34% |
| review_comment_message | 58,247 | 58.70% |
| review_creation_date | 0 | 0.00% |
| review_answer_timestamp | 0 | 0.00% |

### olist_orders_dataset

| Kolom | Null count | Null % |
|---|---:|---:|
| order_id | 0 | 0.00% |
| customer_id | 0 | 0.00% |
| order_status | 0 | 0.00% |
| order_purchase_timestamp | 0 | 0.00% |
| order_approved_at | 160 | 0.16% |
| order_delivered_carrier_date | 1,783 | 1.79% |
| order_delivered_customer_date | 2,965 | 2.98% |
| order_estimated_delivery_date | 0 | 0.00% |

### olist_products_dataset

| Kolom | Null count | Null % |
|---|---:|---:|
| product_id | 0 | 0.00% |
| product_category_name | 610 | 1.85% |
| product_name_lenght | 610 | 1.85% |
| product_description_lenght | 610 | 1.85% |
| product_photos_qty | 610 | 1.85% |
| product_weight_g | 2 | 0.01% |
| product_length_cm | 2 | 0.01% |
| product_height_cm | 2 | 0.01% |
| product_width_cm | 2 | 0.01% |

### olist_sellers_dataset

| Kolom | Null count | Null % |
|---|---:|---:|
| seller_id | 0 | 0.00% |
| seller_zip_code_prefix | 0 | 0.00% |
| seller_city | 0 | 0.00% |
| seller_state | 0 | 0.00% |

### product_category_name_translation

| Kolom | Null count | Null % |
|---|---:|---:|
| product_category_name | 0 | 0.00% |
| product_category_name_english | 0 | 0.00% |

## Timestamp ranges and validity

| Tabel | Kolom | Min | Max | Null sumber | Invalid non-null |
|---|---|---|---|---:|---:|
| olist_orders_dataset | order_purchase_timestamp | 2016-09-04 21:15:19 | 2018-10-17 17:30:18 | 0 | 0 |
| olist_orders_dataset | order_approved_at | 2016-09-15 12:16:38 | 2018-09-03 17:40:06 | 160 | 0 |
| olist_orders_dataset | order_delivered_carrier_date | 2016-10-08 10:34:01 | 2018-09-11 19:48:28 | 1,783 | 0 |
| olist_orders_dataset | order_delivered_customer_date | 2016-10-11 13:46:32 | 2018-10-17 13:22:46 | 2,965 | 0 |
| olist_orders_dataset | order_estimated_delivery_date | 2016-09-30 00:00:00 | 2018-11-12 00:00:00 | 0 | 0 |
| olist_order_items_dataset | shipping_limit_date | 2016-09-19 00:15:34 | 2020-04-09 22:35:08 | 0 | 0 |
| olist_order_reviews_dataset | review_creation_date | 2016-10-02 00:00:00 | 2018-08-31 00:00:00 | 0 | 0 |
| olist_order_reviews_dataset | review_answer_timestamp | 2016-10-07 18:32:28 | 2018-10-29 12:27:35 | 0 | 0 |

## Review key analysis

| Metrik | Hasil |
|---|---:|
| review_id_duplicate_rows | 814 |
| order_id_duplicate_rows | 551 |
| review_order_composite_duplicate_rows | 0 |
| orders_with_multiple_reviews | 547 |
| orders_with_review | 98,673 |
| max_reviews_per_order | 3 |

## Cross-table relationships

| Metrik | Hasil |
|---|---:|
| total_orders | 99,441 |
| orders_without_items | 775 |
| orders_without_payments | 1 |
| unique_customer_ids | 99,441 |
| unique_people | 96,096 |
| people_with_multiple_customer_ids | 2,997 |

## Order anomalies

| Metrik | Hasil |
|---|---:|
| delivered_without_delivery_date | 8 |
| delivery_before_carrier | 23 |
| approval_before_purchase | 0 |

## Geolocation anomalies

| Metrik | Hasil |
|---|---:|
| total_rows | 1,000,163 |
| unique_zip_prefixes | 19,015 |
| invalid_numeric_coordinates | 0 |
| outside_brazil_approx_bounds | 11,687 |
| latitude_min | -36.6053744107061 |
| latitude_max | 45.06593318269697 |
| longitude_min | -101.46676644931476 |
| longitude_max | 121.10539381057764 |

## Payment reconciliation

| Metrik | Hasil |
|---|---:|
| total_orders | 99,441 |
| orders_without_items | 775 |
| orders_without_payments | 1 |
| difference_gt_0_01 | 1,076 |
| difference_gt_1_00 | 1,022 |
| within_0_01 | 98,365 |
| treatment | missing totals compared as zero; missing flags counted separately |

## Catatan interpretasi

- Bounding box Brasil adalah pendekatan kasar, bukan batas negara yang presisi.
- Missing tanggal pada status non-delivered belum tentu merupakan error.
- Rekonsiliasi belum mengklasifikasikan penyebab selisih; itu dikerjakan pada mart.
- Nilai sumber tidak diubah atau dibuang oleh proses profiling.
