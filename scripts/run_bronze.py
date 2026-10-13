from time import perf_counter

from olist.bronze import ingest_all_files


def main():
    print("=== BRONZE INGESTION ===")

    start = perf_counter()

    results = ingest_all_files()

    elapsed = perf_counter() - start

    print("\n=== INGESTION SUMMARY ===")

    for result in results:
        print(f"{result['table']}: {result['status']}")

    print(f"\nTotal datasets: {len(results)}")
    print(f"Elapsed seconds: {elapsed:.2f}")


if __name__ == "__main__":
    main()