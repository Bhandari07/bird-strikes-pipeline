"""Verify live Snowflake results and write evidence from that account."""

import json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bird_strikes.snowflake_loader import connect


def main():
    checks = {
        "current_incidents": ("SELECT COUNT(*) FROM RAW.STRIKE_CURRENT", 25518),
        "reporting_incidents": ("SELECT COUNT(*) FROM MART.FACT_STRIKE", 25518),
        "unique_incidents": (
            "SELECT COUNT(DISTINCT record_id) FROM MART.FACT_STRIKE",
            25518,
        ),
        "batches": ("SELECT COUNT(*) FROM RAW.LOAD_AUDIT", 5),
        "weekly_deletes": (
            "SELECT deletes FROM RAW.LOAD_AUDIT WHERE batch='Final'",
            40,
        ),
        "dfw_incidents": (
            "SELECT COUNT(*) FROM MART.REPORTING_STRIKES WHERE airport='DALLAS/FORT WORTH INTL ARPT'",
            803,
        ),
        "canada_goose_cost": (
            "SELECT SUM(cost) FROM MART.REPORTING_STRIKES WHERE species='Canada goose'",
            20664597,
        ),
        "quality_records": (
            "SELECT COUNT(DISTINCT record_id) FROM RAW.DQ_CURRENT",
            957,
        ),
    }
    evidence = {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "backend": "Snowflake",
        "checks": {},
    }
    with connect() as conn, conn.cursor() as cur:
        for name, (sql, expected) in checks.items():
            cur.execute(sql)
            actual = cur.fetchone()[0]
            evidence["checks"][name] = {
                "expected": expected,
                "actual": int(actual),
                "passed": actual == expected,
                "query_id": cur.sfqid,
            }
    path = ROOT / "evidence" / "snowflake_live_run.json"
    path.write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))
    if not all(c["passed"] for c in evidence["checks"].values()):
        raise SystemExit("Live verification failed")


if __name__ == "__main__":
    main()
