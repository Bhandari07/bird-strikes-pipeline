"""Resumable local ingestion with transactional release publication."""

import json, logging, shutil, sqlite3, uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from .changes import apply_batch, ValidationError, validate_policy
from .contracts import STAGES, read_batch
from .identity import canonical
from .manifest import validate_manifest
from .model import build_model
from .publication import current_release, publish, writer_lock
from .quality import normalize
from .reporting import analyze

LOG = logging.getLogger(__name__)
DDL = """
CREATE TABLE raw_rows(batch TEXT,line INTEGER,record_id TEXT,payload TEXT,PRIMARY KEY(batch,line));
CREATE TABLE change_log(batch TEXT,record_id TEXT,action TEXT,changed_fields TEXT,before_payload TEXT,after_payload TEXT);
CREATE TABLE current_source(record_id TEXT PRIMARY KEY,payload TEXT,source_file TEXT);
CREATE TABLE dq_current(record_id TEXT,rule TEXT,field TEXT,source_value TEXT,detail TEXT,source_file TEXT);
CREATE TABLE load_audit(batch TEXT PRIMARY KEY,file_sha256 TEXT,encoding TEXT,input_rows INTEGER,blank_rows INTEGER,valid_rows INTEGER,inserts INTEGER,updates INTEGER,deletes INTEGER,unchanged INTEGER,state_rows INTEGER,run_at_utc TEXT);
CREATE TABLE dq_batch_summary(batch TEXT,rule TEXT,issues INTEGER);
"""


def clear_reporting(db):
    db.execute("DROP VIEW IF EXISTS reporting_strikes")
    db.execute("DROP TABLE IF EXISTS fact_strike")
    for name in [
        "date",
        "airport",
        "aircraft",
        "operator",
        "wildlife",
        "phase",
        "weather",
    ]:
        db.execute(f"DROP TABLE IF EXISTS dim_{name}")
    db.execute("DELETE FROM dq_current")
    db.execute("DELETE FROM current_source")


def process_batch(db, state, provenance, stage, data_dir, max_delete_fraction, reason):
    path = data_dir / f"Bird Strikes - {stage}.csv"
    rows, blanks, headers, encoding, sha = read_batch(path, stage)
    previous = len(state)
    events = apply_batch(state, rows, stage == "Final", max_delete_fraction, reason)
    db.executemany(
        "INSERT INTO raw_rows VALUES (?,?,?,?)",
        [(stage, line, r["Record ID"], canonical(r)) for line, r in rows],
    )
    db.executemany(
        "INSERT INTO change_log VALUES (?,?,?,?,?,?)",
        [
            (
                stage,
                e.record_id,
                e.action,
                canonical(e.fields),
                canonical(e.before),
                canonical(e.after),
            )
            for e in events
        ],
    )
    for _, row in rows:
        provenance[row["Record ID"]] = path.name
    counts = Counter(e.action for e in events)
    if len(state) != previous + counts["INSERT"] - counts["DELETE"]:
        raise ValidationError("Batch reconciliation failed")
    audit = dict(
        batch=stage,
        file_sha256=sha,
        encoding=encoding,
        input_rows=len(rows) + blanks,
        blank_rows=blanks,
        valid_rows=len(rows),
        inserts=counts["INSERT"],
        updates=counts["UPDATE"],
        deletes=counts["DELETE"],
        unchanged=len(rows) - counts["INSERT"] - counts["UPDATE"],
        state_rows=len(state),
        run_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    db.execute(
        "INSERT INTO load_audit VALUES (" + ",".join("?" for _ in audit) + ")",
        list(audit.values()),
    )
    qc = Counter(i[0] for row in state.values() for i in normalize(row)[1])
    db.executemany(
        "INSERT INTO dq_batch_summary VALUES (?,?,?)",
        [(stage, k, v) for k, v in qc.items()],
    )
    LOG.info(
        "batch=%s inserts=%s updates=%s deletes=%s current=%s",
        stage,
        counts["INSERT"],
        counts["UPDATE"],
        counts["DELETE"],
        len(state),
    )
    return audit


def run(
    data_dir,
    out,
    through="Final",
    rebuild=False,
    max_delete_fraction=0.05,
    override_reason="",
):
    """Resume ordered deliveries; --rebuild replays the frozen input set from Base."""
    data_dir, out = Path(data_dir), Path(out)
    validate_policy(max_delete_fraction, override_reason)
    validate_manifest(data_dir, through)
    out.mkdir(parents=True, exist_ok=True)
    with writer_lock(out):
        previous = (
            None
            if rebuild or not (out / "CURRENT.json").exists()
            else current_release(out)
        )
        release = out / "releases" / uuid.uuid4().hex
        release.mkdir(parents=True)
        db = sqlite3.connect(release / "bird_strikes.sqlite")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if previous:
                with sqlite3.connect(previous / "bird_strikes.sqlite") as source:
                    source.backup(db)
                audit = [
                    dict(r)
                    for r in db.execute("SELECT * FROM load_audit ORDER BY rowid")
                ]
                done = [r["batch"] for r in audit]
                if done != STAGES[: len(done)]:
                    raise ValidationError("Stored batch sequence is invalid")
                for r in audit:
                    if (
                        r["file_sha256"]
                        != read_batch(
                            data_dir / f"Bird Strikes - {r['batch']}.csv", r["batch"]
                        )[4]
                    ):
                        raise ValidationError(
                            "Previously applied input changed; rebuild required"
                        )
                if STAGES.index(through) + 1 < len(done):
                    raise ValidationError("Cannot move backwards without --rebuild")
                if STAGES.index(through) + 1 == len(done):
                    db.close()
                    shutil.rmtree(release)
                    return json.loads((previous / "summary.json").read_text())
                state = {
                    r["record_id"]: json.loads(r["payload"])
                    for r in db.execute("SELECT * FROM current_source")
                }
                provenance = {
                    r["record_id"]: r["source_file"]
                    for r in db.execute("SELECT * FROM current_source")
                }
                clear_reporting(db)
            else:
                db.executescript(DDL)
                state = {}
                provenance = {}
                audit = []
                done = []
            for stage in STAGES[len(done) : STAGES.index(through) + 1]:
                audit.append(
                    process_batch(
                        db,
                        state,
                        provenance,
                        stage,
                        data_dir,
                        max_delete_fraction,
                        override_reason,
                    )
                )
            if through == "Final":
                expected = {
                    r["Record ID"]: r
                    for _, r in read_batch(
                        data_dir / "Bird Strikes - Final.csv", "Final"
                    )[0]
                }
                if state != expected:
                    raise ValidationError("Final payload reconciliation failed")
            db.executemany(
                "INSERT INTO current_source VALUES (?,?,?)",
                [(rid, canonical(r), provenance[rid]) for rid, r in state.items()],
            )
            build_model(db, state, provenance, release)
            if list(db.execute("PRAGMA foreign_key_check")):
                raise ValidationError("Foreign key violation")
            if db.execute("SELECT COUNT(*) FROM reporting_strikes").fetchone()[
                0
            ] != len(state):
                raise ValidationError("Fact join changed incident count")
            result = analyze(db, audit, release, through)
            (release / "release_metadata.json").write_text(
                json.dumps(
                    {
                        "max_delete_fraction": max_delete_fraction,
                        "override_reason": override_reason,
                        "through": through,
                    },
                    indent=2,
                )
            )
            db.commit()
            db.close()
            publish(out, release)
            return result
        except Exception:
            db.close()
            shutil.rmtree(release, ignore_errors=True)
            raise
