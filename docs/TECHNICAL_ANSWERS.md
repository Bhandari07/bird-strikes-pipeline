# Technical answers

Snowflake technical answers

What is Snowflake Openflow

Openflow is a data integration service built on Apache NiFi, using connectors and processors to move and process data [1]. For this scenario it could retrieve supplier deliveries and route them to raw storage. Its value increases with multiple sources or complex connectivity. For five scheduled CSV files, staged loading may be simpler. It still needs credentials, network access, monitoring and explicit rules for order, retries and deletes. It does not automatically determine the business meaning of a weekly snapshot.

What is the VARIANT data type

VARIANT stores a value together with its type and supports nested OBJECT and ARRAY content [2]. A raw payload object could preserve changing supplier fields before typed transformations. For example, payload:"Airport: Name"::varchar extracts an airport value. It is useful for schema evolution and auditability. It does not validate business rules: casts, date parsing and null handling remain necessary. Prefer typed reporting columns for BI measures and joins, and distinguish SQL NULL from JSON null.

What is Snowflake Horizon Catalog

Horizon Catalog provides catalog and governance capabilities, including discovery, lineage, metadata and data protection [3]. In this project, it could help analysts find the reporting tables, understand the origin of a cost field and apply access policies. The benefit is governed discovery and traceability. It does not replace transformation tests, ownership or an agreed definition of an incident. Confirm the required feature availability, privileges and coverage in the target account before designing around it.

What is UNLOAD in Snowflake

Unloading exports data from Snowflake to files, normally with COPY INTO <location>, using a table or SELECT query and an internal or external stage [4]. Here it could export reporting data or a supplier quality-feedback file. Output may span several files; choosing a single file trades convenience against parallel output. Stage permissions, format, compression, encryption and handling of exported sensitive data require configuration. GET can download from an internal stage. UNLOAD does not mean deleting the underlying table.

Example usage in the proposed architecture

Openflow or another ingestion service obtains files. Snowflake stores the raw payloads and reconciled current state. dbt extracts typed fields, models the reporting layer and runs tests. Horizon supports catalog and governance. COPY INTO a stage exports an approved result when a downstream consumer needs files. Revision 2 implements Snowflake ingestion and dbt tables. Account execution is pending; the same dbt graph has been tested in DuckDB.



dbt technical answers

What is a dbt source

A source is a YAML declaration of an existing relation, typically loaded by another process, referenced through source() [5]. It provides dependency lineage and a place to declare tests and freshness checks. Here strike_current would be an ingestion-owned source and dbt models would transform it. A source declaration does not load CSV files. Freshness must use ingestion metadata, not the historic FlightDate; configure and invoke freshness checks separately from ordinary model builds.

What is a dbt snapshot and what are its drawbacks

A snapshot records observed row versions using type-2 history, with validity intervals [6]. It could preserve revisions to the reconciled strike table. A timestamp strategy needs a reliable modification timestamp; otherwise use a check strategy on chosen business columns. Drawbacks include storage and compute growth, missed intermediate changes between runs, dependence on stable unique keys and explicit deletion handling. Historical states cannot be rebuilt from only the latest source. Snapshot the reconciled current state, not a daily delta whose missing rows are not deletions.

Why does dbt not support identity columns for surrogate keys

The question needs qualification: databases can generate identity or sequence values, and dbt can use database-specific logic, hooks or custom materializations. The problem is that normal model rebuilding does not naturally preserve stateful identity assignments. Rebuilds or changing row order can change identifiers and break joins. Deterministic hashes of stable business keys are usually easier to reproduce across environments. dbt documentation demonstrates sequence alternatives and their caveats [7]. Normalize inputs, handle nulls explicitly and test uniqueness. The local SQLite path hashes JSON attribute tuples. The dbt path hashes length-prefixed values with explicit null markers. Keys are backend-specific; production should prefer stable reference IDs where available.

What is the difference between dbt run and dbt build

dbt run executes selected models. dbt build also orchestrates selected tests, seeds and snapshots in dependency order [8]. A blocking upstream test failure can skip dependent resources; warning severity changes that behavior. For this project, run supports model iteration and build is the better production gate for tested reporting outputs. Build does not ingest supplier files or automatically replace a separate source-freshness job. Exact additional resource support is version-dependent, so pin the project and adapter versions.



References: https://docs.snowflake.com/ and https://docs.getdbt.com/. See docs/SOURCES.md for specific documentation links.
