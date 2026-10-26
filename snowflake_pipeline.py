"""Run the Snowflake ingestion pipeline. Authentication stays on your computer."""

import argparse, json, logging
from pathlib import Path
from bird_strikes.snowflake_loader import bootstrap, run_snowflake


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create dedicated warehouse, database and schemas",
    )
    p.add_argument("--data-dir", type=Path, default=Path(__file__).parent / "data")
    p.add_argument(
        "--through",
        choices=["Base", "Day 1", "Day 2", "Day 3", "Final"],
        default="Final",
    )
    p.add_argument("--max-delete-fraction", type=float, default=0.05)
    p.add_argument("--override-reason", default="")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if a.bootstrap:
        bootstrap()
    print(
        json.dumps(
            run_snowflake(
                a.data_dir, a.through, a.max_delete_fraction, a.override_reason
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
