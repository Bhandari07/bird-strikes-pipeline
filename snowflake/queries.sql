-- Run after publishing; select the configured assessment database first.
SELECT airport,COUNT(*) AS incidents FROM MART.REPORTING_STRIKES
GROUP BY airport ORDER BY incidents DESC LIMIT 10;
SELECT * FROM MART.ANNUAL ORDER BY year;
SELECT phase,COUNT(*) AS incidents,SUM(damage) AS damaged_incidents
FROM MART.REPORTING_STRIKES GROUP BY phase ORDER BY incidents DESC;
SELECT * FROM MART.SPECIES_IMPACT ORDER BY total_reported_cost DESC LIMIT 10;
SELECT batch,valid_rows,blank_rows,inserts,updates,deletes,state_rows
FROM RAW.LOAD_AUDIT ORDER BY batch_index;
SELECT rule,COUNT(*) AS issues FROM RAW.DQ_CURRENT GROUP BY rule ORDER BY issues DESC;
SELECT * FROM RAW.CHANGE_LOG WHERE action='DELETE';
