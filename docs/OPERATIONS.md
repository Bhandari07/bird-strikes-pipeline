# Operations and recovery

## Before the first cloud run

Use an isolated assessment database. A setup role needs CREATE DATABASE and CREATE WAREHOUSE at account level, then ownership or the appropriate CREATE privileges within the database. The runtime role needs warehouse USAGE, database/schema USAGE, table DML privileges, stage READ/WRITE and permission to create temporary tables in RAW. dbt needs CREATE TABLE in BUILD and access to RAW; publication needs ownership of BUILD and MART. The simplest assessment setup uses the same authorised role to create and run its own dedicated objects.

For a team deployment, separate setup, loader, transform and read-only roles. Because a schema swap also swaps grants, apply matching BI USAGE/SELECT grants and future grants to both BUILD and MART before enabling BI access. No role grants are automatically widened by this package.

## Failure handling

- Invalid CSV, key, schema, manifest or deletion fraction: stop; retain previous state. Verify source delivery and business scope before retrying.
- PUT/COPY/merge/reconciliation failure: the ingestion transaction rolls back. A retry can leave staged prepared files, but a committed batch cannot be applied twice. Inspect LOAD_AUDIT and the captured exception.
- dbt failure: MART remains the prior publication. Correct the failing model or input, then run the full build/publish command again. Do not bypass a failed test by manually swapping schemas.
- Connection drops around COMMIT: rerun ingestion. LOAD_AUDIT determines whether the batch committed. A timeout message alone does not prove rollback.
- Reporting rollback: if no subsequent build has overwritten BUILD, `ALTER SCHEMA BUILD SWAP WITH MART` restores the preceding publication. Verify contents and grants before performing a rollback. After another build, the old schema contents may have been replaced; use retained inputs and a new isolated replay database.
- Local failure: CURRENT.json still identifies the last complete release. A stale `.writer.lock` contains a PID. Confirm the process is gone before removing that file; never remove an active writer's lock.

## Monitoring and costs

Use LOAD_AUDIT counts, per-batch checksums, query tags and DQ_CURRENT as the operational evidence. The CLI returns a nonzero exit code on failure. A production scheduler should capture this, alert the data owner, retain logs and enforce one deployment at a time. This package does not configure an email service, scheduler, resource monitor or spending limit. Warehouse auto-suspend controls idle compute, not total spend.

## Retention and scale

Update history stores changed fields only; insert/delete events retain the required payload for traceability. Source files remain immutable. No prebuilt SQLite or DuckDB database is included in the submission. Local releases retain earlier complete outputs; prune them deliberately after the retention requirement is agreed.

The Python change planner fetches the current assessment population into memory. This is practical for 25,518 records, but needs redesign for millions of records: construct effective column-preserving payloads in Snowflake staging, calculate differences in SQL, and retain a supplier sequence/version per delivery. The present stage names and manifest describe one fixed assessment week. A continuous service needs dated batch IDs, late-arrival rules, supplier-certified scope/cutoff manifests and secure scheduled key-pair authentication.

## Reproducibility

Direct dependencies are pinned in the requirements files. The exact environment used locally is recorded in evidence/dependency_versions.txt. No credentials, local virtual environments, database files or dbt caches are packaged. Re-run local tests after any modification and execute the live Snowflake acceptance script before claiming a cloud deployment is verified.
