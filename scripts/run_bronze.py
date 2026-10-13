import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from olist.bronze import ingest_all_files


ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = ROOT / "outputs" / "bronze_runs.jsonl"


def main():
    print("=== BRONZE INGESTION ===")

    started_at = datetime.now(timezone.utc).isoformat()
    start = perf_counter()

    results = ingest_all_files()

    elapsed = perf_counter() - start

    print("\n=== INGESTION SUMMARY ===")

    for result in results:
        print(f"{result['table']}: {result['status']}")

    print(f"\nTotal datasets: {len(results)}")
    print(f"Elapsed seconds: {elapsed:.2f}")

    # Catat hasil eksekusi yang berhasil.
    run_record = {
        "started_at": started_at,
        "elapsed_seconds": round(elapsed, 2),
        "total_datasets": len(results),
        "results": results,
    }

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with HISTORY_PATH.open("a", encoding="utf-8") as file:
        file.write(
            json.dumps(run_record, ensure_ascii=False) + "\n"
        )

    print("Run history saved:", HISTORY_PATH)


if __name__ == "__main__":
    main()