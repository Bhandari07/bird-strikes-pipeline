"""Explicit optional AUD conversion. Source USD remains an unconfirmed assumption."""

import argparse, csv, json, sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bird_strikes.publication import current_release


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aud-per-usd", required=True, type=Decimal)
    p.add_argument("--rate-date", required=True, type=date.fromisoformat)
    p.add_argument("--rate-source", required=True)
    a = p.parse_args()
    if not a.aud_per_usd.is_finite() or a.aud_per_usd <= 0:
        p.error("Rate must be finite and positive")
    if not a.rate_source.strip():
        p.error("Rate source is required")
    release = current_release(ROOT / "output")
    with (release / "species_cost.csv").open() as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        value = row["total_reported_cost"]
        row["cost_aud"] = (
            str((Decimal(value) * a.aud_per_usd).quantize(Decimal(".01")))
            if value
            else ""
        )
        row.update(
            aud_per_usd=str(a.aud_per_usd),
            rate_date=a.rate_date.isoformat(),
            rate_source=a.rate_source,
            source_currency_status="USD assumed; awaiting confirmation",
        )
    target = ROOT / "output" / "species_cost_aud.csv"
    with target.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(target)


if __name__ == "__main__":
    main()
