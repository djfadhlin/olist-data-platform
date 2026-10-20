
#!/usr/bin/env python3
"""Single-entry CLI for the Olist Data Platform.

Examples:
    python pipeline.py --help
    python pipeline.py init
    python pipeline.py up
    python pipeline.py check
    python pipeline.py profile
    python pipeline.py bronze
    python pipeline.py silver
    python pipeline.py load
    python pipeline.py stream --verify-only
    python pipeline.py stream --recover
    python pipeline.py stream --run --limit 100
    python pipeline.py model
    python pipeline.py marts
    python pipeline.py test
    python pipeline.py status
    python pipeline.py inject
    python pipeline.py inject --scenario f01
    python pipeline.py inject --scenario f04 --yes
    python pipeline.py report
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

FAILURE_SCENARIOS = {
    "f01": "scripts.test_schema_drift",
    "f02": "scripts.failure_f02_duplicate_producer",
    "f03": "scripts.failure_f03_consumer_crash",
    "f04": "scripts.failure_f04_kafka_outage",
    "f05": "scripts.failure_f05_batch_rerun",
}

DISRUPTIVE_SCENARIOS = {"f04", "f05"}

REPORT_FILES = {
    "Bronze report": "outputs/bronze_report.md",
    "Silver DQ report": "outputs/silver/dq_report.md",
    "Raw load report": "outputs/load_report.md",
    "Streaming report": "outputs/stream_report.md",
    "Data Warehouse report": "outputs/dw_report.md",
    "Gold Marts report": "outputs/marts_report.md",
    "Failure injection report": "outputs/failure_tests.md",
    "T5 dashboard": "notebooks/olist_t5_dashboard.ipynb",
}


def heading(title):
    print(f"\n=== {title} ===", flush=True)


def run_command(command, *, check=True, timeout=None):
    """Execute a command from the project root."""

    command = [str(item) for item in command]

    print("\n>>> " + " ".join(command), flush=True)

    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        timeout=timeout,
    )


def run_module(module, *arguments, timeout=None):
    """Run one Python module using the active virtual environment."""

    return run_command(
        [
            PYTHON,
            "-B",
            "-m",
            module,
            *[str(arg) for arg in arguments],
        ],
        timeout=timeout,
    )


def run_pytest(*paths):
    command = [
        PYTHON,
        "-B",
        "-m",
        "pytest",
        *paths,
        "-q",
    ]
    run_command(command)


def compose(*arguments):
    return run_command(
        ["docker", "compose", *arguments]
    )


def module_exists(module):
    """Check whether a project module file is present."""

    return (ROOT / (module.replace(".", "/") + ".py")).is_file()


def require_module(module):
    if not module_exists(module):
        raise SystemExit(
            f"Required module not found: {module}\n"
            f"Expected: {ROOT / (module.replace('.', '/') + '.py')}"
        )


def run_steps(steps):
    """Run ordered modules, stopping immediately on failure."""

    for module, arguments in steps:
        require_module(module)
        run_module(module, *arguments)


def cmd_init(args):
    heading("T0 PROJECT INITIALIZATION")

    env_path = ROOT / ".env"
    example_candidates = [
        ROOT / ".env.example",
        ROOT / ".env.template",
        ROOT / "env.example",
    ]

    if env_path.exists():
        print(".env already exists; preserving current values.")
    else:
        example = next(
            (path for path in example_candidates if path.exists()),
            None,
        )

        if example is None:
            raise SystemExit(
                "Cannot initialize .env: no environment template found."
            )

        env_path.write_bytes(example.read_bytes())
        print(f"Created .env from {example.name}")
        print("Review the environment variables before proceeding.")

    required_directories = [
        "data/raw",
        "outputs",
        "outputs/silver",
        "outputs/gold",
        "notebooks",
    ]

    for directory in required_directories:
        (ROOT / directory).mkdir(
            parents=True,
            exist_ok=True,
        )

    print("Project directories: READY")
    print("T0 initialization: PASS")


def cmd_up(args):
    heading("T0 START DOCKER INFRASTRUCTURE")

    command = ["up", "-d"]

    if args.build:
        command.append("--build")

    compose(*command)
    compose("ps")

    print("\nDocker startup command completed.")
    print("Confirm all required services are healthy.")


def cmd_down(args):
    heading("T0 STOP DOCKER INFRASTRUCTURE")

    if args.volumes and not args.yes:
        raise SystemExit(
            "WARNING: --volumes deletes persistent Docker data.\n"
            "If you really intend to reset the environment, use:\n"
            "python pipeline.py down --volumes --yes"
        )

    command = ["down"]

    if args.volumes:
        command.append("-v")

    compose(*command)

    print("\nDocker services stopped.")

    if args.volumes:
        print("WARNING: Docker volumes were removed.")


def cmd_check(args):
    heading("T0 ENVIRONMENT CHECK")

    print(f"Project root: {ROOT}")
    print(f"Python executable: {PYTHON}")
    print(f"Python version: {sys.version.split()[0]}")

    env_path = ROOT / ".env"

    if not env_path.is_file():
        raise SystemExit(
            "Missing .env. Run: python pipeline.py init"
        )

    print(".env: FOUND")

    run_command(
        ["docker", "compose", "config", "--services"]
    )

    compose("ps")

    csv_files = sorted((ROOT / "data/raw").glob("*.csv"))
    print(f"\nSource CSV files: {len(csv_files)}")

    if len(csv_files) != 9:
        raise SystemExit(
            f"Expected 9 source CSV files, found {len(csv_files)}"
        )

    print("Environment check: PASS")
    print(
        "Note: this check validates configuration and file presence; "
        "individual service health must also be confirmed in Docker."
    )


def cmd_profile(args):
    heading("T1 DATA PROFILING")

    module = "scripts.profile_all"

    if not module_exists(module):
        candidates = [
            "scripts.run_profile",
            "scripts.profile_sources",
            "scripts.profile_data",
        ]

        module = next(
            (candidate for candidate in candidates
             if module_exists(candidate)),
            None,
        )

    if module is None:
        print("Available profiling-related scripts:")

        for path in sorted((ROOT / "scripts").glob("*profil*.py")):
            print(f"  {path}")

        raise SystemExit(
            "Profiling entrypoint was not found. "
            "Select the profiling module used in T1."
        )

    run_module(module)
    print("\nT1 profiling: PASS")


def cmd_bronze(args):
    heading("T2 BRONZE INGESTION")

    run_steps([
        ("scripts.run_bronze", ()),
        ("scripts.check_bronze_manifests", ()),
        ("scripts.generate_bronze_report", ()),
    ])

    print("\nT2 Bronze ingestion: PASS")


def cmd_silver(args):
    heading("T2 SILVER TRANSFORMATION")

    steps = [
        ("scripts.run_silver", ()),
        ("scripts.verify_silver_outputs", ()),
    ]

    if args.upload:
        steps.append(
            ("scripts.upload_silver", ())
        )

    run_steps(steps)

    print("\nT2 Silver transformation: PASS")


def cmd_load(args):
    heading("T2 RAW POSTGRESQL LOAD")

    run_steps([
        ("scripts.create_raw_tables", ()),
        ("scripts.verify_raw_schema", ()),
        ("scripts.load_raw", ()),
        ("scripts.verify_raw_counts", ()),
    ])

    print("\nT2 PostgreSQL Raw: PASS")


def cmd_stream(args):
    heading("T3 KAFKA STREAMING")

    if args.verify_only:
        run_module("scripts.verify_stream_status")
        print("\nT3 stream verification: PASS")
        return

    if args.recover:
        print(
            "Recovering missing final order events.",
            flush=True,
        )

        recovery_args = []

        if args.limit is not None:
            recovery_args.extend(
                ["--limit", str(args.limit)]
            )

        run_module(
            "scripts.replay_missing_final_events",
            *recovery_args,
        )

        print("\nRecovery events published.")
        print(
            "Consume the recovery events and verify status before "
            "claiming reconciliation is complete."
        )
        return

    if not args.run:
        raise SystemExit(
            "Choose --verify-only, --recover, or --run.\n"
            "Example: python pipeline.py stream --verify-only"
        )

    if args.limit is None:
        raise SystemExit(
            "For a streaming replay, specify --limit explicitly.\n"
            "Example: python pipeline.py stream --run --limit 100"
        )

    print(
        f"Replay limit: {args.limit} orders\n"
        f"Consumer idle timeout: {args.idle_seconds}s",
        flush=True,
    )

    # Ensure the streaming schema and Kafka topics exist.
    # CREATE IF NOT EXISTS style setup should be non-destructive.
    run_module("scripts.create_stream_tables")
    run_module("scripts.create_kafka_topics")

    consumer_command = [
        PYTHON,
        "-B",
        "-m",
        "scripts.consume_orders",
        "--idle-seconds",
        str(args.idle_seconds),
        "--batch-size",
        str(args.batch_size),
    ]

    producer_command = [
        PYTHON,
        "-B",
        "-m",
        "scripts.produce_orders",
        "--limit",
        str(args.limit),
        "--seed",
        str(args.seed),
    ]

    print(
        "\nStarting Kafka consumer...",
        flush=True,
    )

    consumer = subprocess.Popen(
        consumer_command,
        cwd=ROOT,
    )

    try:
        time.sleep(3)

        if consumer.poll() is not None:
            raise RuntimeError(
                "Consumer exited before producer started."
            )

        print(
            "\nStarting Kafka producer...",
            flush=True,
        )

        run_command(
            producer_command,
            timeout=args.timeout,
        )

        print(
            "\nWaiting for consumer...",
            flush=True,
        )

        try:
            exit_code = consumer.wait(
                timeout=args.timeout,
            )
        except subprocess.TimeoutExpired:
            consumer.terminate()
            try:
                consumer.wait(timeout=10)
            except subprocess.TimeoutExpired:
                consumer.kill()
                consumer.wait()

            raise TimeoutError(
                "Kafka consumer exceeded the configured timeout."
            )

        if exit_code != 0:
            raise RuntimeError(
                f"Kafka consumer failed with exit code {exit_code}"
            )

    finally:
        if consumer.poll() is None:
            consumer.terminate()

            try:
                consumer.wait(timeout=10)
            except subprocess.TimeoutExpired:
                consumer.kill()
                consumer.wait()

    run_module("scripts.verify_stream_status")

    print("\nT3 streaming replay and reconciliation: PASS")


def cmd_model(args):
    heading("T4 DATA WAREHOUSE")

    run_module("scripts.build_dw")

    run_pytest(
        "tests/test_dw_integrity.py",
    )

    print("\nT4 Data Warehouse: PASS")


def cmd_marts(args):
    heading("T5 GOLD MARTS")

    run_module("scripts.build_marts")

    run_pytest(
        "tests/test_marts.py",
    )

    print("\nT5 Gold Marts: PASS")


def cmd_test(args):
    heading("INTEGRITY TEST SUITE")

    run_pytest(
        "tests/test_dw_integrity.py",
        "tests/test_marts.py",
    )

    print("\nIntegrity test suite: PASS")


def cmd_status(args):
    heading("OLIST DATA PLATFORM STATUS")

    print(f"Project root: {ROOT}")
    print()

    found = 0

    for label, relative_path in REPORT_FILES.items():
        path = ROOT / relative_path
        exists = path.is_file()

        print(
            f"{'FOUND' if exists else 'MISSING':7} "
            f"{label}: {relative_path}"
        )

        if exists:
            found += 1

    print()
    print(
        f"Available reports/artifacts: "
        f"{found}/{len(REPORT_FILES)}"
    )

    print(
        "\nNote: file existence is not a substitute "
        "for runtime validation."
    )


def cmd_inject(args):
    """Run an explicitly selected failure-injection scenario."""

    scenario = args.scenario

    if scenario is None:
        heading("T6 FAILURE INJECTION")

        print("Available scenarios:")
        print("  f01  Missing source CSV column")
        print("  f02  Duplicate producer")
        print("  f03  Consumer crash before Kafka offset commit")
        print("  f04  Kafka broker outage during replay")
        print("  f05  Full batch rerun")
        print()
        print("Examples:")
        print("  python pipeline.py inject --scenario f01")
        print("  python pipeline.py inject --scenario f02")
        print("  python pipeline.py inject --scenario f03")
        print("  python pipeline.py inject --scenario f04 --yes")
        print("  python pipeline.py inject --scenario f05 --yes")
        print()
        print("WARNING:")
        print("  F02 publishes messages to the main Kafka topic.")
        print("  F04 temporarily stops the Kafka broker.")
        print("  F05 rebuilds the entire batch pipeline.")
        return

    module = FAILURE_SCENARIOS[scenario]

    if scenario in DISRUPTIVE_SCENARIOS and not args.yes:
        raise SystemExit(
            f"{scenario.upper()} requires explicit confirmation.\n"
            "F04 temporarily stops Kafka; "
            "F05 rebuilds batch tables.\n"
            f"Run: python pipeline.py inject "
            f"--scenario {scenario} --yes"
        )

    require_module(module)

    heading(f"T6 FAILURE INJECTION — {scenario.upper()}")

    run_module(module)

    print(
        f"\nT6 {scenario.upper()} injection: PASS",
        flush=True,
    )



def cmd_report(args):
    """Generate T6 failure report and evaluation evidence."""

    heading("T6 EVIDENCE REPORT GENERATION")

    # Jalankan dua generator secara berurutan.
    modules = (
        "scripts.generate_failure_report",
        "scripts.generate_evaluation_evidence",
    )

    for module in modules:
        require_module(module)
        run_module(module)

    # Pastikan kedua file benar-benar berhasil dibuat.
    required_reports = (
        ROOT / "outputs" / "failure_tests.md",
        ROOT / "EVALUATION_EVIDENCE.md",
    )

    for report_path in required_reports:
        if not report_path.is_file():
            raise SystemExit(
                f"Report was not created: {report_path}"
            )

        print(f"Verified: {report_path}")

    print("\nT6 evidence reports: PASS")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Olist Data Platform CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    p = sub.add_parser(
        "init",
        help="Prepare local environment and directories",
    )
    p.set_defaults(func=cmd_init)

    p = sub.add_parser(
        "up",
        help="Start Docker infrastructure",
    )
    p.add_argument(
        "--build",
        action="store_true",
        help="Rebuild local Docker images",
    )
    p.set_defaults(func=cmd_up)

    p = sub.add_parser(
        "down",
        help="Stop Docker infrastructure",
    )
    p.add_argument(
        "-v",
        "--volumes",
        action="store_true",
        help="Delete Docker volumes (destructive)",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive volume deletion",
    )
    p.set_defaults(func=cmd_down)

    p = sub.add_parser(
        "check",
        help="Check environment and source files",
    )
    p.set_defaults(func=cmd_check)

    p = sub.add_parser(
        "profile",
        help="Run source profiling",
    )
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser(
        "bronze",
        help="Ingest source CSV files into Bronze MinIO",
    )
    p.set_defaults(func=cmd_bronze)

    p = sub.add_parser(
        "silver",
        help="Transform and verify Silver Parquet outputs",
    )
    p.add_argument(
        "--upload",
        action="store_true",
        help="Upload Silver outputs to MinIO",
    )
    p.set_defaults(func=cmd_silver)

    p = sub.add_parser(
        "load",
        help="Load Silver Parquet into PostgreSQL Raw",
    )
    p.set_defaults(func=cmd_load)

    p = sub.add_parser(
        "stream",
        help="Run or verify Kafka streaming",
    )

    mode = p.add_mutually_exclusive_group()

    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify all current statuses against Raw",
    )
    mode.add_argument(
        "--recover",
        action="store_true",
        help="Publish missing final order events",
    )
    mode.add_argument(
        "--run",
        action="store_true",
        help="Run producer and consumer",
    )

    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Number of source orders for replay/recovery",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic producer fault-injection seed",
    )
    p.add_argument(
        "--idle-seconds",
        type=float,
        default=10,
        help="Consumer idle timeout in seconds",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Maximum Kafka records per consumer poll",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Maximum time for producer/consumer in seconds",
    )

    p.set_defaults(func=cmd_stream)

    p = sub.add_parser(
        "model",
        help="Build and validate the T4 star schema",
    )
    p.set_defaults(func=cmd_model)

    p = sub.add_parser(
        "marts",
        help="Build and validate T5 Gold Marts",
    )
    p.set_defaults(func=cmd_marts)

    p = sub.add_parser(
        "test",
        help="Run DW and Gold integrity tests",
    )
    p.set_defaults(func=cmd_test)

    p = sub.add_parser(
        "status",
        help="List available project reports and artifacts",
    )
    p.set_defaults(func=cmd_status)

    p = sub.add_parser(
        "inject",
        help="Run one selected T6 failure-injection scenario",
    )
    p.add_argument(
        "--scenario",
        choices=list(FAILURE_SCENARIOS),
        default=None,
        help="Failure-injection scenario",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Confirm disruptive F04/F05 scenarios",
    )
    p.set_defaults(func=cmd_inject)

    p = sub.add_parser(
        "report",
        help="Generate T6 failure evidence report",
    )
    p.set_defaults(func=cmd_report)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if hasattr(args, "limit"):
        if args.limit is not None and args.limit <= 0:
            parser.error("--limit must be positive")

    if hasattr(args, "idle_seconds"):
        if args.idle_seconds <= 0:
            parser.error("--idle-seconds must be positive")

    if hasattr(args, "batch_size"):
        if args.batch_size <= 0:
            parser.error("--batch-size must be positive")

    if hasattr(args, "timeout"):
        if args.timeout <= 0:
            parser.error("--timeout must be positive")

    try:
        args.func(args)

    except subprocess.CalledProcessError as error:
        raise SystemExit(
            f"\nPipeline command failed "
            f"(exit code {error.returncode})."
        ) from error

    except (
        FileNotFoundError,
        TimeoutError,
        RuntimeError,
    ) as error:
        raise SystemExit(
            f"\nPipeline failed: {error}"
        ) from error


if __name__ == "__main__":
    main()
