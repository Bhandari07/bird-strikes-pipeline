# Sources

All assessment metrics derive from the five CSV files under data/, verified by data/manifest.json. No external facts were used to invent missing incident records, flight volumes or currency rates.

Implementation references checked for this revision:

- Snowflake Python connector and PUT/COPY: https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-example
- Snowflake transaction and DDL behaviour: https://docs.snowflake.com/en/sql-reference/transactions
- Schema swap syntax, ownership and grants: https://docs.snowflake.com/en/sql-reference/sql/alter-schema
- dbt Snowflake connection profiles: https://docs.getdbt.com/docs/local/connect-data-platform/snowflake-setup
- dbt DuckDB connection profiles: https://docs.getdbt.com/docs/local/connect-data-platform/duckdb-setup

Part 2 reference documentation:

- Openflow: https://docs.snowflake.com/en/user-guide/data-integration/openflow/about
- VARIANT: https://docs.snowflake.com/en/sql-reference/data-types-semistructured
- Horizon: https://docs.snowflake.com/en/user-guide/snowflake-horizon
- UNLOAD: https://docs.snowflake.com/en/user-guide/data-unload-overview
- dbt sources: https://docs.getdbt.com/docs/build/sources
- dbt snapshots: https://docs.getdbt.com/docs/build/snapshots
- dbt keys: https://docs.getdbt.com/blog/managing-surrogate-keys
- dbt commands: https://docs.getdbt.com/reference/commands/build

Proposed augmentation sources (not imported): FAA OPSNET https://www.aspm.faa.gov/opsnet/sys/main.asp and NOAA hourly observations https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database . Confirm coverage, identifiers, usage terms and population alignment before implementation.
