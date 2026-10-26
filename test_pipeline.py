"""Behavior tests for loss prevention, snapshot reconciliation and reruns."""

import csv, json, sqlite3, tempfile, unittest
from pathlib import Path
from pipeline import apply_batch, normalize, run, read_batch, BASE_COLUMNS
from bird_strikes.publication import current_release

ROOT = Path(__file__).resolve().parent


class BehaviorTests(unittest.TestCase):
    def test_daily_update_preserves_absent_column_but_clears_explicit_blank(self):
        state = {"1": {"Record ID": "1", "cost": "100", "warned": "Y"}}
        apply_batch(state, [(2, {"Record ID": "1", "cost": "200"})])
        self.assertEqual(state["1"]["warned"], "Y")
        apply_batch(state, [(2, {"Record ID": "1", "warned": ""})])
        self.assertEqual(state["1"]["warned"], "")

    def test_daily_omission_is_not_deletion_and_snapshot_is(self):
        state = {"1": {"Record ID": "1"}, "2": {"Record ID": "2"}}
        apply_batch(state, [(2, {"Record ID": "1"})])
        self.assertIn("2", state)
        events = apply_batch(
            state,
            [(2, {"Record ID": "1"})],
            snapshot=True,
            max_delete_fraction=1,
            override_reason="test fixture",
        )
        self.assertNotIn("2", state)
        self.assertEqual(events[0].action, "DELETE")

    def test_reapplying_batch_has_no_changes(self):
        state = {}
        rows = [(2, {"Record ID": "1", "cost": "100"})]
        apply_batch(state, rows)
        self.assertEqual(apply_batch(state, rows), [])

    def test_precipitation_and_altitude_boundary(self):
        r = {
            "Record ID": "1",
            "Conditions: Precipitation": "Fog, Rain",
            "Feet above ground": "1,000",
            "Altitude bin": "< 1000 ft",
        }
        out, issues = normalize(r)
        self.assertEqual((out["has_rain"], out["has_fog"], out["has_snow"]), (1, 1, 0))
        self.assertEqual(out["altitude_status"], "boundary")
        r["Conditions: Precipitation"] = ""
        self.assertIsNone(normalize(r)[0]["has_rain"])

    def test_count_range_check(self):
        r = {
            "Record ID": "1",
            "Wildlife: Number struck": "2 to 10",
            "Wildlife: Number Struck Actual": "11",
        }
        self.assertIn("BIRD_COUNT_RANGE_MISMATCH", [i[0] for i in normalize(r)[1]])

    def test_bad_snapshot_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sample.csv"
            headers = BASE_COLUMNS + ["Aircraft: Number of engines?"]
            row = {h: "" for h in headers}
            row["Airport: Name"] = "Airport"
            with p.open("w", newline="") as f:
                w = csv.DictWriter(f, headers)
                w.writeheader()
                w.writerow(row)
            with self.assertRaises(ValueError):
                read_batch(p, "Final")

    def test_end_to_end_and_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)
            first = run(ROOT / "data", target)
            db = sqlite3.connect(current_release(target) / "bird_strikes.sqlite")
            actual = dict(db.execute("SELECT record_id,payload FROM current_source"))
            expected = {
                r["Record ID"]: r
                for _, r in read_batch(
                    ROOT / "data" / "Bird Strikes - Final.csv", "Final"
                )[0]
            }
            self.assertEqual({k: json.loads(v) for k, v in actual.items()}, expected)
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM reporting_strikes").fetchone()[0],
                25518,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(DISTINCT record_id) FROM fact_strike"
                ).fetchone()[0],
                25518,
            )
            self.assertEqual(list(db.execute("PRAGMA foreign_key_check")), [])
            db.close()
            second = run(ROOT / "data", target)
            for k in ["totals", "airports", "annual", "quality"]:
                self.assertEqual(first[k], second[k])
            # Failure in a new input must preserve the published database.
            digest = (current_release(target) / "bird_strikes.sqlite").read_bytes()
            with self.assertRaises(FileNotFoundError):
                run(target / "missing", target)
            self.assertEqual(
                digest, (current_release(target) / "bird_strikes.sqlite").read_bytes()
            )


if __name__ == "__main__":
    unittest.main()
