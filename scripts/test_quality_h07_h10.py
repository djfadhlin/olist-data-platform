import pandas as pd

from olist.quality import (
    check_h07_payment_value,
    check_h08_customers,
    check_h09_products,
    check_h10_reviews,
)


def main():
    print("=== HARD RULES H07-H10 TEST ===")

    payments = pd.DataFrame({
        "payment_value": ["10.00", "-1.00", "ABC", None]
    })
    h07 = check_h07_payment_value(payments)
    assert set(h07["source_row"]) == {1, 2, 3}
    assert set(h07["rule_id"]) == {"H07"}
    print("H07: PASS")

    customers = pd.DataFrame({
        "customer_id": ["c1", "c1", "c3", "", "c5"],
        "customer_unique_id": ["u1", "u2", None, "u4", "u5"],
    })
    h08 = check_h08_customers(customers)
    assert set(h08["source_row"]) == {1, 2, 3}
    assert set(h08["rule_id"]) == {"H08"}
    print("H08: PASS")

    products = pd.DataFrame({
        "product_id": ["p1", "p2", "p1", None, ""],
    })
    h09 = check_h09_products(products)
    assert set(h09["source_row"]) == {2, 3, 4}
    assert set(h09["rule_id"]) == {"H09"}
    print("H09: PASS")

    reviews = pd.DataFrame({
        "review_id": ["r1", "r1", "r2", "", "r4", "r5"],
        "order_id": ["o1", "o1", "o2", "o3", "o4", "o5"],
        "review_score": ["5", "4", "6", "3", "ABC", None],
    })
    h10 = check_h10_reviews(reviews)

    assert set(h10["source_row"]) == {1, 2, 3, 4, 5}
    assert len(h10) == 5
    assert set(h10["rule_id"]) == {"H10"}
    print("H10: PASS")

    print("\nALL HARD RULES H07-H10: PASS")


if __name__ == "__main__":
    main()