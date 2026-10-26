"""Build the same dbt graph in DuckDB for local verification; no Snowflake claim."""

import json, os, sqlite3, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bird_strikes.engine import run
from bird_strikes.publication import current_release
from bird_strikes.quality import normalize


def main():
    import duckdb

    run(ROOT / "data", ROOT / "output")
    source = sqlite3.connect(current_release(ROOT / "output") / "bird_strikes.sqlite")
    target = ROOT / "dbt" / "bird_strikes.duckdb"
    with duckdb.connect(str(target)) as db:
        db.execute("CREATE SCHEMA IF NOT EXISTS raw")
        db.execute(
            "CREATE OR REPLACE TABLE raw.strike_current(record_id VARCHAR,normalized JSON)"
        )
        rows = [
            (rid, json.dumps(normalize(json.loads(payload))[0]))
            for rid, payload in source.execute(
                "SELECT record_id,payload FROM current_source"
            )
        ]
        db.execute("BEGIN TRANSACTION")
        db.executemany("INSERT INTO raw.strike_current VALUES (?,?)", rows)
        db.execute("COMMIT")
        db.execute(
            "CREATE OR REPLACE TABLE raw.dq_current(record_id VARCHAR,rule VARCHAR,field VARCHAR,source_value VARCHAR,detail VARCHAR,source_batch VARCHAR)"
        )
        db.executemany(
            "INSERT INTO raw.dq_current VALUES (?,?,?,?,?,?)",
            source.execute("SELECT * FROM dq_current").fetchall(),
        )
        db.execute("CHECKPOINT")
    db.close()
    source.close()
    env = {**os.environ, "BIRD_STRIKES_DUCKDB": str(target)}
    subprocess.run(
        [
            str(Path(sys.executable).with_name("dbt")),
            "build",
            "--project-dir",
            str(ROOT / "dbt"),
            "--profiles-dir",
            str(ROOT / "dbt"),
            "--target",
            "local",
        ],
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
