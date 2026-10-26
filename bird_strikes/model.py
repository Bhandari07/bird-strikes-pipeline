"""SQLite star schema and typed reporting export."""

from .identity import key
from .quality import normalize
from .reporting import write_csv


def build_model(db, state, provenance, out):
    dims = {
        "airport": ["airport", "state"],
        "aircraft": ["aircraft_type", "aircraft_model"],
        "operator": ["operator"],
        "wildlife": ["species", "wildlife_size"],
        "phase": ["phase"],
        "weather": ["sky", "precipitation", "has_rain", "has_fog", "has_snow"],
        "date": ["flight_date", "year", "month", "quarter"],
    }
    numeric = {"year", "month", "quarter", "has_rain", "has_fog", "has_snow"}
    for name, fields in dims.items():
        db.execute(
            f"CREATE TABLE dim_{name} ({name}_key TEXT PRIMARY KEY,"
            + ",".join(
                (f"{f} " + ("INTEGER" if f in numeric else "TEXT") for f in fields)
            )
            + ")"
        )
    measures = [
        "damage",
        "cost",
        "injuries",
        "birds_struck",
        "feet_above_ground",
        "engines",
        "pilot_warned",
        "dq_issue_count",
    ]
    attrs = [
        "altitude_source",
        "altitude_derived",
        "altitude_status",
        "impact",
        "source_file",
    ]
    fact_cols = ["record_id"] + [n + "_key" for n in dims] + measures + attrs
    db.execute(
        "CREATE TABLE fact_strike (record_id TEXT PRIMARY KEY,"
        + ",".join(
            (n + "_key TEXT REFERENCES dim_" + n + "(" + n + "_key)" for n in dims)
        )
        + ","
        + ",".join((x + " INTEGER" for x in measures))
        + ","
        + ",".join((x + " TEXT" for x in attrs))
        + ")"
    )
    normalized = []
    for rid, raw in state.items():
        r, issues = normalize(raw)
        date = r["flight_date"]
        r.update(
            year=int(date[:4]) if date else None,
            month=int(date[5:7]) if date else None,
            quarter=(int(date[5:7]) - 1) // 3 + 1 if date else None,
        )
        for name, fields in dims.items():
            vals = [r[f] for f in fields]
            k = key(*vals)
            r[name + "_key"] = k
            db.execute(
                f"INSERT OR IGNORE INTO dim_{name} VALUES ("
                + ",".join(("?" for _ in range(len(vals) + 1)))
                + ")",
                [k] + vals,
            )
        r["source_file"] = provenance[rid]
        db.execute(
            "INSERT INTO fact_strike VALUES ("
            + ",".join(("?" for _ in fact_cols))
            + ")",
            [r.get(c) for c in fact_cols],
        )
        for rule, field, value, detail in issues:
            db.execute(
                "INSERT INTO dq_current VALUES (?,?,?,?,?,?)",
                (rid, rule, field, value, detail, r["source_file"]),
            )
        normalized.append({k: v for k, v in r.items() if not k.endswith("_key")})
    joins = " ".join((f"JOIN dim_{n} d_{n} ON f.{n}_key=d_{n}.{n}_key" for n in dims))
    select = (
        ["f.record_id"]
        + ["d_" + n + "." + c for n, cols in dims.items() for c in cols]
        + ["f." + c for c in measures + attrs]
    )
    db.execute(
        "CREATE VIEW reporting_strikes AS SELECT "
        + ",".join(select)
        + " FROM fact_strike f "
        + joins
    )
    write_csv(out / "reporting_strikes.csv", normalized)
    return normalized
