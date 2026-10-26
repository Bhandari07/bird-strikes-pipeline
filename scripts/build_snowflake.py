"""Build and test isolated reporting tables, then atomically publish the schema."""

import argparse, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bird_strikes.snowflake_loader import connect, settings


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--publish", action="store_true", help="Swap verified BUILD and MART schemas"
    )
    a = p.parse_args()
    target = (
        "snowflake_keypair" if os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH") else "snowflake"
    )
    # The deployment orchestrator must serialize this entire build + publish job.
    # The loader mutex serializes ingestion only; do not ingest during this build.
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT batch,file_sha256 FROM RAW.LOAD_AUDIT ORDER BY batch_index")
        before = cur.fetchall()
        if len(before) != 5 or before[-1][0] != "Final":
            raise RuntimeError("Complete Final ingestion before building reporting")
    subprocess.run(
        [
            str(Path(sys.executable).with_name("dbt")),
            "build",
            "--project-dir",
            str(ROOT / "dbt"),
            "--profiles-dir",
            str(ROOT / "dbt"),
            "--target",
            target,
        ],
        check=True,
    )
    results = json.loads((ROOT / "dbt" / "target" / "run_results.json").read_text())
    if not results["results"] or any(
        r["status"] not in ("success", "pass") for r in results["results"]
    ):
        raise RuntimeError("Publication requires every dbt resource to pass")
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT batch,file_sha256 FROM RAW.LOAD_AUDIT ORDER BY batch_index")
        if cur.fetchall() != before:
            raise RuntimeError("Source batch changed while dbt built; run again")
        if a.publish:
            cur.execute("ALTER SCHEMA BUILD SWAP WITH MART")
            print(
                "Published verified tables in MART; previous publication is retained in BUILD."
            )
        else:
            print(
                "Verified BUILD schema. Re-run with --publish to build, test and publish."
            )


if __name__ == "__main__":
    main()
