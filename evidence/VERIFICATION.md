# Verification record

Revision 2, prepared 26 October 2026.

| Check | Actual status |
|---|---|
| Python unittest discovery | 27 tests passed |
| Local Final payload reconciliation | 25,518 exact normalized source payloads matched |
| Python late-failure publication test | Old database and all old exports preserved |
| Real Day 2 omission | 102 existing values preserved; 3,197 new values unknown |
| dbt on DuckDB | 13 table models and 40 data tests passed |
| dbt Snowflake target | Parsed successfully without account access |
| Static Snowflake SQL parser | 27 statements parsed; schema swap treated as unsupported generic command |
| Schema swap documentation check | Syntax and ownership/grant behaviour checked against Snowflake docs |
| Mocked Snowflake connector tests | Rollback and DDL-before-BEGIN orchestration passed |
| Live Snowflake execution | NOT RUN: no account connection supplied |

See the text logs beside this file. A successful local run does not establish cloud permissions, connector authentication, staging behaviour, warehouse runtime or server transaction correctness. Run scripts/verify_snowflake.py after the cloud ingestion and publication to generate live evidence with query IDs.

The original dataset's Final stage adds the engines column. Its 22,615 updates include schema enrichment. The final 40 deletes are within the default 5% guard. No business assumption has been described as externally confirmed.
