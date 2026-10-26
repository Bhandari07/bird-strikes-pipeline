import csv, json, sqlite3, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from bird_strikes.changes import apply_batch, ValidationError
from bird_strikes.contracts import BASE_COLUMNS, read_batch
from bird_strikes.engine import run
from bird_strikes.identity import key
from bird_strikes.publication import current_release, writer_lock
from bird_strikes.quality import normalize
from bird_strikes.snowflake_loader import identifier, envelope_rows

ROOT = Path(__file__).resolve().parents[1]


class InputTests(unittest.TestCase):
    def write(self, path, rows, encoding="utf-8", headers=None):
        with path.open("w", newline="", encoding=encoding) as handle:
            w = csv.DictWriter(handle, headers or BASE_COLUMNS)
            w.writeheader()
            w.writerows(rows)

    def test_cp1252_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "input.csv"
            r = {k: "" for k in BASE_COLUMNS}
            r.update({"Record ID": "1", "Airport: Name": "Café"})
            self.write(p, [r], "cp1252")
            rows, _, _, encoding, _ = read_batch(p, "Base")
            self.assertEqual(encoding, "cp1252")
            self.assertEqual(rows[0][1]["Airport: Name"], "Café")

    def test_duplicate_key_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "input.csv"
            r = {k: "" for k in BASE_COLUMNS}
            r["Record ID"] = "1"
            self.write(p, [r, r])
            with self.assertRaises(ValueError):
                read_batch(p, "Base")

    def test_empty_batch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "input.csv"
            self.write(p, [])
            with self.assertRaises(ValueError):
                read_batch(p, "Base")

    def test_unapproved_column_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "input.csv"
            self.write(p, [], headers=BASE_COLUMNS + ["surprise"])
            with self.assertRaises(ValueError):
                read_batch(p, "Base")

    def test_large_integer_is_not_rounded_by_float(self):
        out, _ = normalize({"Record ID": "1", "Cost: Total $": "9007199254740993"})
        self.assertEqual(out["cost"], 9007199254740993)

    def test_nonfinite_number_rejected(self):
        for value in ("NaN", "Infinity", "-1", "1.5"):
            out, issues = normalize({"Record ID": "1", "Cost: Total $": value})
            self.assertIsNone(out["cost"])
            self.assertIn("INVALID_NONNEGATIVE_INTEGER", [i[0] for i in issues])


class ChangeSafetyTests(unittest.TestCase):
    def test_threshold_rejects_before_mutation(self):
        state = {str(i): {"Record ID": str(i), "v": "old"} for i in range(100)}
        before = json.dumps(state, sort_keys=True)
        with self.assertRaises(ValidationError):
            apply_batch(state, [(2, {"Record ID": "0", "v": "new"})], True)
        self.assertEqual(json.dumps(state, sort_keys=True), before)

    def test_exact_threshold_allowed(self):
        state = {str(i): {"Record ID": str(i)} for i in range(100)}
        events = apply_batch(
            state, [(i, {"Record ID": str(i)}) for i in range(95)], True
        )
        self.assertEqual(sum(e.action == "DELETE" for e in events), 5)

    def test_override_requires_reason(self):
        with self.assertRaises(ValidationError):
            apply_batch({"1": {"Record ID": "1"}}, [(2, {"Record ID": "2"})], True, 1)

    def test_update_patch_only_contains_changed_field(self):
        state = {"1": {"Record ID": "1", "cost": "10", "large": "unchanged"}}
        e = apply_batch(state, [(2, {"Record ID": "1", "cost": "20"})])[0]
        self.assertEqual(e.fields, ["cost"])
        self.assertNotIn("large", e.before)
        self.assertEqual(e.before["cost"], {"present": True, "value": "10"})

    def test_real_day2_missing_column(self):
        state = {}
        for stage in ("Base", "Day 1"):
            apply_batch(
                state,
                read_batch(ROOT / "data" / f"Bird Strikes - {stage}.csv", stage)[0],
            )
        previous = {
            k: v.get("Pilot warned of birds or wildlife?") for k, v in state.items()
        }
        rows, _, headers, _, _ = read_batch(
            ROOT / "data" / "Bird Strikes - Day 2.csv", "Day 2"
        )
        self.assertNotIn("Pilot warned of birds or wildlife?", headers)
        apply_batch(state, rows)
        existing = new = 0
        for _, r in rows:
            rid = r["Record ID"]
            if rid in previous:
                existing += 1
                self.assertEqual(
                    state[rid].get("Pilot warned of birds or wildlife?"), previous[rid]
                )
            else:
                new += 1
                self.assertNotIn("Pilot warned of birds or wildlife?", state[rid])
        self.assertEqual((existing, new), (102, 3197))

    def test_dimension_keys_distinguish_null_empty_and_delimiters(self):
        values = [key(None), key(""), key("Unknown"), key("a|b", "c"), key("a", "b|c")]
        self.assertEqual(len(set(values)), len(values))
        self.assertEqual(key("a", "b"), key("a", "b"))

    def test_snowflake_identifier_injection_rejected(self):
        with self.assertRaises(ValueError):
            identifier("RAW; DROP DATABASE X")

    def test_envelope_contains_combined_weather_and_compact_patch(self):
        state = {"1": {"Record ID": "1", "Conditions: Precipitation": "Rain"}}
        rows = [(2, {"Record ID": "1", "Conditions: Precipitation": "Rain, Snow"})]
        events = apply_batch(state, rows)
        record = list(envelope_rows(state, rows, events))[0]
        self.assertEqual(
            (record["normalized"]["has_rain"], record["normalized"]["has_snow"]), (1, 1)
        )
        self.assertEqual(record["changed_fields"], ["Conditions: Precipitation"])


class PublicationTests(unittest.TestCase):
    def test_late_export_failure_preserves_entire_release(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            run(ROOT / "data", out, "Base")
            previous = current_release(out)
            original = {p.name: p.read_bytes() for p in previous.iterdir()}
            with patch(
                "bird_strikes.engine.analyze", side_effect=RuntimeError("late failure")
            ):
                with self.assertRaises(RuntimeError):
                    run(ROOT / "data", out, "Day 1")
            self.assertEqual(previous, current_release(out))
            self.assertEqual(
                original, {p.name: p.read_bytes() for p in previous.iterdir()}
            )

    def test_resume_applies_only_new_batch(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            run(ROOT / "data", out, "Base")
            run(ROOT / "data", out, "Day 1")
            with sqlite3.connect(current_release(out) / "bird_strikes.sqlite") as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM load_audit").fetchone()[0], 2
                )
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM current_source").fetchone()[0],
                    17811,
                )
            previous = current_release(out)
            run(ROOT / "data", out, "Day 1")
            self.assertEqual(previous, current_release(out))

    def test_single_writer_lock(self):
        with tempfile.TemporaryDirectory() as d:
            with writer_lock(Path(d)):
                with self.assertRaises(RuntimeError):
                    with writer_lock(Path(d)):
                        pass

    def test_manifest_change_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "manifest.json").write_text((ROOT / "data/manifest.json").read_text())
            (p / "Bird Strikes - Base.csv").write_text("changed")
            with self.assertRaises(ValidationError):
                run(p, p / "out", "Base")


class SnowflakeTransactionTests(unittest.TestCase):
    class Cursor:
        def __init__(self, fail=False):
            self.calls = []
            self.rowcount = 1
            self.fail = fail

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params=None):
            self.calls.append(sql)
            if self.fail and sql.startswith("MERGE"):
                raise RuntimeError("injected merge failure")
            return self

        def fetchall(self):
            sql = self.calls[-1]
            if sql.startswith("SELECT record_id,content_hash"):
                return [("1", key({"Record ID": "1"}))]
            return []

        def fetchone(self):
            return (1, 1)

    class Connection:
        def __init__(self, cursor):
            self.current = cursor

        def cursor(self):
            return self.current

    def check_delivery(self, fail):
        from bird_strikes.snowflake_loader import apply_delivery

        cur = self.Cursor(fail)
        with patch(
            "bird_strikes.snowflake_loader.read_batch",
            return_value=([(2, {"Record ID": "1"})], 0, [], "utf-8", "abc"),
        ), patch("bird_strikes.snowflake_loader.upload"):
            if fail:
                with self.assertRaises(RuntimeError):
                    apply_delivery(self.Connection(cur), ROOT / "data", "Base")
            else:
                apply_delivery(self.Connection(cur), ROOT / "data", "Base")
        return cur.calls

    def test_cloud_failure_rolls_back(self):
        calls = self.check_delivery(True)
        self.assertEqual(calls[-1], "ROLLBACK")
        self.assertNotIn("COMMIT", calls)

    def test_cloud_ddl_precedes_transaction(self):
        calls = self.check_delivery(False)
        self.assertTrue(calls[0].startswith("CREATE OR REPLACE TEMPORARY"))
        self.assertEqual(calls[1], "BEGIN TRANSACTION")
        self.assertEqual(calls[-1], "COMMIT")
        self.assertFalse(any(s.startswith("CREATE") for s in calls[2:]))


if __name__ == "__main__":
    unittest.main()
