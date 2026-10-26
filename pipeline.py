"""Local CLI. The primary cloud entry point is snowflake_pipeline.py."""

import argparse, logging
from pathlib import Path
from bird_strikes.engine import run
from bird_strikes.publication import current_release
from bird_strikes.changes import apply_batch
from bird_strikes.quality import normalize
from bird_strikes.contracts import BASE_COLUMNS, read_batch


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data")
    parser.add_argument("--output", type=Path, default=root / "output")
    parser.add_argument(
        "--through",
        choices=["Base", "Day 1", "Day 2", "Day 3", "Final"],
        default="Final",
    )
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--max-delete-fraction", type=float, default=0.05)
    parser.add_argument("--override-reason", default="")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(
        args.data_dir,
        args.output,
        args.through,
        args.rebuild,
        args.max_delete_fraction,
        args.override_reason,
    )
    print("Published release:", current_release(args.output))


if __name__ == "__main__":
    main()
