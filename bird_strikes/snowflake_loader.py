"""Snowflake batch loader: immutable files, ordered changes and transactional audit."""

import json, logging, os, re, tempfile, uuid
from collections import Counter
from pathlib import Path
from .changes import apply_batch, validate_policy, ValidationError
from .contracts import STAGES, read_batch
from .identity import canonical, key
from .manifest import validate_manifest
from .quality import normalize

LOG = logging.getLogger(__name__)
VERSION = "2.0.0"


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value):
        raise ValueError(
            "Use simple Snowflake identifiers: letters, numbers and underscore"
        )
    return value.upper()


def settings() -> dict:
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_ROLE"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise ValueError("Set " + ", ".join(missing) + " in your local environment")
    return dict(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        role=identifier(os.environ["SNOWFLAKE_ROLE"]),
        database=identifier(os.getenv("SNOWFLAKE_DATABASE", "BIRD_STRIKES_ASSESSMENT")),
        warehouse=identifier(os.getenv("SNOWFLAKE_WAREHOUSE", "BIRD_STRIKES_WH")),
    )


def connect(bootstrap=False):
    import snowflake.connector

    cfg = settings()
    options = {
        k: v
        for k, v in cfg.items()
        if not bootstrap or k not in ("database", "warehouse")
    }
    if os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH"):
        options["private_key_file"] = os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]
        if os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"):
            options["private_key_file_pwd"] = os.environ[
                "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"
            ]
    else:
        options["authenticator"] = "externalbrowser"
    return snowflake.connector.connect(
        **options,
        session_parameters={
            "QUERY_TAG": "bird_strikes_assessment_v2",
            "LOCK_TIMEOUT": 60,
            "STATEMENT_TIMEOUT_IN_SECONDS": 600,
        },
    )


def bootstrap():
    """Create dedicated assessment objects under the caller's explicitly selected role."""
    cfg = settings()
    with connect(bootstrap=True) as conn, conn.cursor() as cur:
        cur.execute(
            f"CREATE WAREHOUSE IF NOT EXISTS {cfg['warehouse']} WAREHOUSE_SIZE='XSMALL' AUTO_SUSPEND=60 AUTO_RESUME=TRUE INITIALLY_SUSPENDED=TRUE"
        )
        cur.execute(f"USE WAREHOUSE {cfg['warehouse']}")
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {cfg['database']}")
        cur.execute(f"USE DATABASE {cfg['database']}")
        for schema in ("RAW", "BUILD", "MART"):
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cur.execute("USE SCHEMA RAW")
        for sql in (
            (Path(__file__).resolve().parents[1] / "snowflake/setup.sql")
            .read_text()
            .split(";")
        ):
            if sql.strip():
                cur.execute(sql)


def upload(cur, path: Path, prefix: str):
    """Stage a local file; prefix consists only of trusted checksum/UUID tokens."""
    safe_path = path.resolve().as_posix().replace("'", "''")
    cur.execute(
        f"PUT 'file://{safe_path}' @RAW.DELIVERIES/{prefix}/ AUTO_COMPRESS=TRUE OVERWRITE=FALSE"
    )
    results = cur.fetchall()
    if not results or any(
        str(r[6]).upper() not in ("UPLOADED", "SKIPPED") for r in results
    ):
        raise RuntimeError("PUT did not confirm successful upload")


def envelope_rows(state, rows, events):
    """Prepare current payloads and compact patches once for COPY and MERGE."""
    by_id = {e.record_id: e for e in events}
    for line, incoming in rows:
        rid = incoming["Record ID"]
        payload = state[rid]
        normalized, issues = normalize(payload)
        event = by_id.get(rid)
        yield dict(
            record_id=rid,
            line=line,
            incoming=incoming,
            payload=payload,
            normalized=normalized,
            issues=[
                dict(rule=r, field=f, source_value=v, detail=d) for r, f, v, d in issues
            ],
            content_hash=key(payload),
            action=event.action if event else "UNCHANGED",
            changed_fields=event.fields if event else [],
            before=event.before if event else None,
            after=event.after if event else None,
        )
    for event in events:
        if event.action == "DELETE":
            yield dict(
                record_id=event.record_id,
                action="DELETE",
                changed_fields=[],
                before=event.before,
                after=None,
            )


def apply_delivery(
    conn, data_dir: Path, stage: str, max_delete_fraction=0.05, override_reason=""
) -> dict:
    validate_policy(max_delete_fraction, override_reason)
    path = data_dir / f"Bird Strikes - {stage}.csv"
    rows, blanks, headers, encoding, sha = read_batch(path, stage)
    index = STAGES.index(stage)
    with conn.cursor() as cur:
        # DDL stays outside the explicit transaction: Snowflake DDL commits implicitly.
        cur.execute("CREATE OR REPLACE TEMPORARY TABLE RAW.LANDING_BATCH (v VARIANT)")
        cur.execute("BEGIN TRANSACTION")
        try:
            # A permanent singleton row serializes this loader across clients.
            cur.execute(
                "UPDATE RAW.LOADER_MUTEX SET touched_at=CURRENT_TIMESTAMP() WHERE lock_name='bird_strikes'"
            )
            if cur.rowcount != 1:
                raise ValidationError("Expected exactly one loader mutex row")
            cur.execute(
                "SELECT batch_index,batch,file_sha256,pipeline_version FROM RAW.LOAD_AUDIT ORDER BY batch_index"
            )
            done = cur.fetchall()
            if [r[0] for r in done] != list(range(len(done))):
                raise ValidationError("Invalid stored batch sequence")
            for applied_index, batch, checksum, version in done:
                if (
                    checksum
                    != read_batch(data_dir / f"Bird Strikes - {batch}.csv", batch)[4]
                    or version != VERSION
                ):
                    raise ValidationError(
                        "Previously loaded input or pipeline version differs; use a fresh assessment database"
                    )
            if index < len(done):
                cur.execute("ROLLBACK")
                return {"batch": stage, "status": "already_applied"}
            if index != len(done):
                raise ValidationError("Deliveries must be applied in order")
            cur.execute("SELECT record_id,TO_JSON(payload) FROM RAW.STRIKE_CURRENT")
            pairs = cur.fetchall()
            state = {rid: json.loads(payload) for rid, payload in pairs}
            if len(pairs) != len(state):
                raise ValidationError("Duplicate current incident keys")
            previous = len(state)
            events = apply_batch(
                state, rows, stage == "Final", max_delete_fraction, override_reason
            )
            counts = Counter(e.action for e in events)
            upload(cur, path, f"original/{sha}")
            token = uuid.uuid4().hex
            with tempfile.TemporaryDirectory() as folder:
                staged = Path(folder) / "batch.jsonl"
                with staged.open("w", encoding="utf-8") as handle:
                    for envelope in envelope_rows(state, rows, events):
                        handle.write(canonical(envelope) + "\n")
                upload(cur, staged, f"prepared/{token}")
                cur.execute(
                    f"COPY INTO RAW.LANDING_BATCH FROM @RAW.DELIVERIES/prepared/{token}/ FILE_FORMAT=(TYPE=JSON) ON_ERROR='ABORT_STATEMENT'"
                )
                cur.fetchall()
            cur.execute(
                "SELECT COUNT(*),COUNT(DISTINCT v:record_id::VARCHAR) FROM RAW.LANDING_BATCH"
            )
            count, unique = cur.fetchone()
            if count != len(rows) + counts["DELETE"] or count != unique:
                raise ValidationError("Staging count/key mismatch")
            cur.execute(
                """INSERT INTO RAW.CHANGE_LOG
                SELECT %s,v:record_id::VARCHAR,v:action::VARCHAR,v:changed_fields,v:before,v:after,CURRENT_TIMESTAMP()
                FROM RAW.LANDING_BATCH WHERE v:action::VARCHAR <> 'UNCHANGED' """,
                (stage,),
            )
            cur.execute(
                """MERGE INTO RAW.STRIKE_CURRENT t USING
                (SELECT v FROM RAW.LANDING_BATCH WHERE v:action::VARCHAR <> 'DELETE') s
                ON t.record_id=s.v:record_id::VARCHAR
                WHEN MATCHED AND t.content_hash IS DISTINCT FROM s.v:content_hash::VARCHAR THEN
                  UPDATE SET payload=s.v:payload,normalized=s.v:normalized,quality_issues=s.v:issues,
                    content_hash=s.v:content_hash::VARCHAR,source_batch=%s,loaded_at=CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN INSERT(record_id,payload,normalized,quality_issues,content_hash,source_batch,loaded_at)
                  VALUES(s.v:record_id::VARCHAR,s.v:payload,s.v:normalized,s.v:issues,s.v:content_hash::VARCHAR,%s,CURRENT_TIMESTAMP())""",
                (stage, stage),
            )
            if stage == "Final":
                cur.execute(
                    "DELETE FROM RAW.STRIKE_CURRENT WHERE record_id IN (SELECT v:record_id::VARCHAR FROM RAW.LANDING_BATCH WHERE v:action::VARCHAR='DELETE')"
                )
            cur.execute("SELECT record_id,content_hash FROM RAW.STRIKE_CURRENT")
            current = cur.fetchall()
            expected = {rid: key(payload) for rid, payload in state.items()}
            if len(current) != len(expected) or dict(current) != expected:
                raise ValidationError(
                    "Snowflake current payload hashes do not match expected state"
                )
            if len(state) != previous + counts["INSERT"] - counts["DELETE"]:
                raise ValidationError("Count reconciliation failed")
            cur.execute("DELETE FROM RAW.DQ_CURRENT")
            cur.execute(
                """INSERT INTO RAW.DQ_CURRENT SELECT c.record_id,
                q.value:rule::VARCHAR,q.value:field::VARCHAR,q.value:source_value::VARCHAR,
                q.value:detail::VARCHAR,c.source_batch
                FROM RAW.STRIKE_CURRENT c,LATERAL FLATTEN(input=>c.quality_issues) q"""
            )
            cur.execute(
                """INSERT INTO RAW.LOAD_AUDIT VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())""",
                (
                    index,
                    stage,
                    sha,
                    VERSION,
                    len(rows),
                    blanks,
                    counts["INSERT"],
                    counts["UPDATE"],
                    counts["DELETE"],
                    len(state),
                    encoding,
                    max_delete_fraction,
                    override_reason,
                    "supplied_bird_strikes_assessment",
                ),
            )
            cur.execute("COMMIT")
            return dict(
                batch=stage,
                status="committed",
                inserts=counts["INSERT"],
                updates=counts["UPDATE"],
                deletes=counts["DELETE"],
                current=len(state),
            )
        except Exception:
            cur.execute("ROLLBACK")
            raise


def run_snowflake(
    data_dir: Path, through="Final", max_delete_fraction=0.05, override_reason=""
):
    validate_manifest(data_dir, through)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("USE SCHEMA RAW")
        results = []
        for stage in STAGES[: STAGES.index(through) + 1]:
            result = apply_delivery(
                conn, data_dir, stage, max_delete_fraction, override_reason
            )
            LOG.info("%s", json.dumps(result))
            results.append(result)
        return results
