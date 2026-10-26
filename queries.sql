-- All counts use one current record per Record ID, including all supplied wildlife.
-- Airport: Name is a reported airport, not a verified departure airport.
SELECT airport, COUNT(*) AS incidents
FROM reporting_strikes GROUP BY airport ORDER BY incidents DESC, airport LIMIT 10;

-- 129 records have no valid flight date and do not contribute to this trend.
SELECT year, COUNT(*) AS incidents
FROM reporting_strikes WHERE year IS NOT NULL GROUP BY year ORDER BY year;

SELECT phase, COUNT(*) AS incidents, SUM(damage) AS damaged_incidents
FROM reporting_strikes GROUP BY phase ORDER BY incidents DESC;

SELECT species, COUNT(*) AS incidents, SUM(cost) AS total_reported_cost
FROM reporting_strikes GROUP BY species ORDER BY total_reported_cost DESC LIMIT 10;

SELECT batch, valid_rows, blank_rows, inserts, updates, deletes, state_rows FROM load_audit;
SELECT rule, COUNT(*) AS issues FROM dq_current GROUP BY rule ORDER BY issues DESC;
SELECT * FROM dq_current WHERE rule IN ('ALTITUDE_MISMATCH','INVALID_NONNEGATIVE_INTEGER');

-- Detail for removed incidents retained in the audit, absent from current reporting.
SELECT record_id, before_payload FROM change_log WHERE action='DELETE';
