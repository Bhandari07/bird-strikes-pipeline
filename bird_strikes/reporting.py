"""Deterministic analytical exports from the current incident population."""

import csv, json


def write_csv(path, rows, headers=None):
    rows = list(rows)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=headers or (list(rows[0]) if rows else ["no_rows"])
        )
        w.writeheader()
        w.writerows(rows)


def analyze(db, audit, out, through):

    def query(sql):
        return [dict(r) for r in db.execute(sql)]

    summaries = {
        "airports": query(
            "SELECT airport,COUNT(*) incidents FROM reporting_strikes GROUP BY airport ORDER BY incidents DESC,airport"
        ),
        "annual": query(
            "SELECT year,COUNT(*) incidents FROM reporting_strikes WHERE year IS NOT NULL GROUP BY year ORDER BY year"
        ),
        "phases": query(
            "SELECT phase,COUNT(*) incidents, SUM(damage) damaged_incidents FROM reporting_strikes GROUP BY phase ORDER BY incidents DESC,phase"
        ),
        "species_cost": query(
            "SELECT species,COUNT(*) incidents,SUM(cost) total_reported_cost,SUM(damage) damaged_incidents FROM reporting_strikes GROUP BY species ORDER BY total_reported_cost DESC,species"
        ),
        "quality": query(
            "SELECT rule,COUNT(*) issues,COUNT(DISTINCT record_id) affected_records FROM dq_current GROUP BY rule ORDER BY issues DESC,rule"
        ),
        "weather": query(
            "SELECT precipitation,COUNT(*) incidents FROM reporting_strikes GROUP BY precipitation ORDER BY incidents DESC"
        ),
        "audit": audit,
        "totals": query(
            "SELECT COUNT(*) incidents,SUM(damage) damaged_incidents,SUM(cost) total_reported_cost, SUM(flight_date IS NULL) missing_dates,MIN(flight_date) first_date,MAX(flight_date) last_date,SUM(dq_issue_count>0) flagged_incidents FROM reporting_strikes"
        )[0],
        "through": through,
    }
    for n in [
        "airports",
        "annual",
        "phases",
        "species_cost",
        "quality",
        "weather",
        "audit",
    ]:
        write_csv(out / (n + ".csv"), summaries[n])
    write_csv(
        out / "quality_issues.csv",
        query("SELECT * FROM dq_current ORDER BY record_id,rule"),
    )
    (out / "summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    return summaries
