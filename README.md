# Bird strikes assessment

Saroj Bhandari · Revision 2 · 26 October 2026

A Snowflake ingestion pipeline and dbt reporting project for five ordered wildlife-strike deliveries. It preserves daily changes, reconciles the full weekly snapshot and publishes tested reporting tables. The supplied inputs reconcile to 25,518 incidents, including 40 weekly deletions.

**Verification status:** Python tests and the dbt models have been executed locally. The Snowflake target parses, and SQL has undergone static checks. No Snowflake account was available during preparation: cloud authentication, PUT/COPY, transactions and schema publication still require the live run below. `evidence/` distinguishes local results from server execution. This package contains executable Snowflake code, not a claim of a completed cloud deployment.

## Run in Snowflake

Use Python 3.10–3.12. The supplied dependency versions were checked with Python 3.12. Run these commands from this folder on macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-snowflake.txt
```

Set your account identifier, username and an authorised role. Use the account identifier shown by Snowflake, not a full HTTPS URL. Replace the first three example values before running:

```bash
export SNOWFLAKE_ACCOUNT='YOUR_ORG-YOUR_ACCOUNT'
export SNOWFLAKE_USER='YOUR_USER'
export SNOWFLAKE_ROLE='YOUR_AUTHORISED_ROLE'
export SNOWFLAKE_DATABASE='BIRD_STRIKES_ASSESSMENT'
export SNOWFLAKE_WAREHOUSE='BIRD_STRIKES_WH'
python snowflake_pipeline.py --bootstrap
python scripts/build_snowflake.py --publish
python scripts/verify_snowflake.py
```

Browser authentication opens on your computer. Do not put passwords or private keys into this project. For automation, set `SNOWFLAKE_PRIVATE_KEY_PATH` to your local PKCS#8 key; optionally set `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`. The loader and build script then use key-pair authentication.

Bootstrap creates dedicated assessment objects and an X-Small warehouse with 60-second auto-suspend. The role needs permission to create a warehouse and database, or an administrator can provision these first. It needs ownership of both BUILD and MART for schema publication. Run bootstrap once at setup; do not run concurrent bootstraps. Existing assessment tables are retained.

**Run the complete ingestion/build/publish sequence as one serial job.** Do not start competing dbt builds or ingest other data during a reporting build. The ingestion mutex protects loaders; it is not a distributed deployment scheduler. The project is intentionally scoped to this five-file assessment, not an unbounded daily feed.

`python snowflake_pipeline.py` resumes from committed batches; already applied batches with identical checksums are skipped. An input or pipeline version change after loading fails explicitly. Use a fresh dedicated assessment database for an intentional replay of a changed input set. Do not overwrite historical inputs.

Expected results: five committed batches, 25,518 current records, 40 Final deletions, 803 DFW records, Canada goose reported cost 20,664,597. The live verification script writes actual query IDs to `evidence/snowflake_live_run.json` only after connecting to your account.

## Architecture

1. Validate encoding, exact stage schema, unique IDs, source checksums and input counts against `data/manifest.json`.
2. Keep original CSVs in an internal Snowflake stage under their SHA-256 path. Upload prepared JSON with PUT and bulk load it with COPY.
3. Serialize loaders using a transaction-held mutex row. Apply MERGE, authoritative deletes, quality findings and compact change history in the same transaction. Reconcile current payload hashes before COMMIT.
4. Build 13 dbt tables in BUILD, with source, key, relationship, measure and reconciliation tests.
5. On success, swap BUILD with MART. All models are tables, so publication has no view references to the old schema. The prior MART remains in BUILD until the next build.

Snowflake DDL runs outside ingestion transactions. Failed loads roll back current state, change history and the audit entry. Uploaded files can remain on the stage for diagnosis and are not automatically deleted.

## Project structure

- `snowflake_pipeline.py`: cloud ingestion entry point.
- `bird_strikes/`: contracts, identity, normalization, change planning, publication and backend orchestration.
- `snowflake/`: executable setup SQL and business queries.
- `dbt/`: profiles, sources, typed staging, seven dimensions, incident fact and reporting models.
- `scripts/build_snowflake.py`: build/test and optional publication.
- `scripts/verify_snowflake.py`: independent live acceptance checks.
- `pipeline.py`, `demo.py`: standard-library local verification path.
- `tests/`, `test_pipeline.py`: domain, recovery and mocked orchestration tests.
- `docs/`: operating guide, decisions and technical answers.
- `Submission_Report.docx`, `Interview_Presentation.pptx`: assessment explanation and findings.
- `results/`: reproducible summaries and charts; no generated database is shipped.
- `evidence/`: execution results and precise verification boundaries.

## Local verification

The Python pipeline requires no third-party dependencies:

```bash
python3 -m unittest discover -v
python3 demo.py
```

`output/CURRENT.json` identifies a complete immutable release under `output/releases/`. Resolve this pointer once before reading a group of outputs. Every release contains the database and all CSV/JSON exports together. A failed build leaves the old pointer unchanged.

Show persistent daily application with:

```bash
python3 pipeline.py --through Base --rebuild
python3 pipeline.py --through 'Day 1'
python3 pipeline.py --through 'Day 2'
python3 pipeline.py --through 'Day 3'
python3 pipeline.py --through Final
```

For the separate dbt local check, install `requirements-local-dbt.txt` in a virtual environment and run `python scripts/local_dbt.py`. This executes the same model graph on DuckDB. It does not execute Snowflake-specific ingestion SQL or establish cloud connectivity.

## Contract and quality policy

- Record ID is stable. Daily absent rows imply no deletion. Omitted columns preserve values, and explicit blank cells clear values. These semantics await supplier confirmation.
- Final is authoritative for the same scope, as interpreted from the brief. The manifest freezes the supplied files; it is candidate-created, not supplier certification of completeness.
- A snapshot deleting more than 5% of current IDs is rejected before state changes. This conservative candidate policy is configurable; a higher threshold requires `--override-reason`, recorded with the run. Do not relax it to bypass an unexplained loss.
- Exact 1,000-foot values retain a separate boundary category. Invalid numbers become typed nulls with record-level issues. Original values remain in source files and source payloads.
- All supplied wildlife stays in scope. Airport name is a reported-airport proxy, not confirmed departure location. Counts are not exposure-adjusted risk rates.
- Cost is assumed USD. No AUD conversion is fabricated. For an agreed rate, set dbt variables `aud_per_usd`, `fx_rate_date` and `fx_rate_source` in `dbt_project.yml`; reporting then populates `cost_aud` and retains the original `cost`. Without a rate, AUD fields remain null. `scripts/export_aud.py --help` offers the same explicit conversion for local exports.

For optional chart regeneration, install `requirements-analysis.txt` and run `python scripts/build_analysis.py` after the local pipeline. Developer formatting and static SQL tools are in `requirements-dev.txt`.

See `docs/OPERATIONS.md` for recovery, permissions and scaling limits, and `docs/ASSUMPTIONS.md` for outstanding business decisions.
