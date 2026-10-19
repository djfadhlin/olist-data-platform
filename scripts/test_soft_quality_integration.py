
import pandas as pd

from olist.soft_quality import run_all_soft_rules


def main():
    print("=== SOFT QUALITY INTEGRATION TEST ===")

    tables = {
        "olist_orders_dataset": pd.DataFrame({
            "order_id": ["o1", "o2"],
            "order_status": ["delivered", "shipped"],
            "order_purchase_timestamp": [
                "2018-01-01 10:00:00",
                "2018-01-02 10:00:00",
            ],
            "order_approved_at": [
                "2018-01-01 11:00:00",
                "2018-01-02 11:00:00",
            ],
            "order_delivered_carrier_date": [
                "2018-01-02 10:00:00",
                None,
            ],
            "order_delivered_customer_date": [
                None,
                None,
            ],
        }),
        "olist_geolocation_dataset": pd.DataFrame({
            "geolocation_lat": [-23.5, 10.0],
            "geolocation_lng": [-46.6, -46.0],
        }),
        "olist_order_items_dataset": pd.DataFrame({
            "order_id": ["o1"],
            "price": ["100.00"],
            "freight_value": ["10.00"],
        }),
        "olist_order_payments_dataset": pd.DataFrame({
            "order_id": ["o1"],
            "payment_value": ["110.00"],
        }),
        "olist_order_reviews_dataset": pd.DataFrame({
            "order_id": ["o1"],
            "review_id": ["r1"],
        }),
    }

    flags = run_all_soft_rules(tables)

    print(flags.to_string(index=False))

    counts = flags.groupby("rule_id").size().to_dict()

    assert counts == {
        "S01": 1,
        "S04": 1,
        "S06": 1,
        "S07": 1,
    }

    assert len(flags) == 4
    assert set(flags["source_table"]) == {
        "olist_orders_dataset",
        "olist_geolocation_dataset",
    }

    print("\nCounts:", counts)
    print("Soft quality integration test: PASS")


if __name__ == "__main__":
    main()
