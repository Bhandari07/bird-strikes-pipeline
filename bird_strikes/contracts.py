"""Explicit schemas and input validation for the supplied delivery sequence."""

import csv, hashlib, json
from pathlib import Path

STAGES = ["Base", "Day 1", "Day 2", "Day 3", "Final"]
BASE_COLUMNS = [
    "Record ID",
    "Aircraft: Type",
    "Airport: Name",
    "Altitude bin",
    "Aircraft: Make/Model",
    "Wildlife: Number struck",
    "Wildlife: Number Struck Actual",
    "Effect: Impact to flight",
    "FlightDate",
    "Effect: Indicated Damage",
    "Aircraft: Airline/Operator",
    "Origin State",
    "When: Phase of flight",
    "Conditions: Precipitation",
    "Remains of wildlife collected?",
    "Remains of wildlife sent to Smithsonian",
    "Remarks",
    "Wildlife: Size",
    "Conditions: Sky",
    "Wildlife: Species",
    "Pilot warned of birds or wildlife?",
    "Cost: Total $",
    "Feet above ground",
    "Number of people injured",
    "Is Aircraft Large?",
]
EXTRA = "Aircraft: Number of engines?"


def read_batch(path, stage):
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        text = data.decode("cp1252")
        encoding = "cp1252"
    import io

    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = reader.fieldnames
    expected = set(BASE_COLUMNS)
    if stage == "Day 2":
        expected.remove("Pilot warned of birds or wildlife?")
    if stage == "Final":
        expected.add(EXTRA)
    if headers is None or len(set(headers)) != len(headers) or set(headers) != expected:
        raise ValueError(f"{path.name}: unapproved schema drift: {headers}")
    rows, blanks, ids = ([], 0, set())
    for row_no, row in enumerate(reader, 2):
        if None in row or any((v is None for v in row.values())):
            raise ValueError(f"{path.name} row {row_no}: invalid field count")
        row = {k: v.strip() for k, v in row.items()}
        if not any(row.values()):
            blanks += 1
            continue
        rid = row["Record ID"]
        if not rid.isdigit() or rid in ids:
            raise ValueError(
                f"{path.name} row {row_no}: missing, invalid or duplicate Record ID {rid!r}"
            )
        ids.add(rid)
        rows.append((row_no, row))
    if not rows:
        raise ValueError(f"{path.name}: empty batch refused")
    return (rows, blanks, headers, encoding, hashlib.sha256(data).hexdigest())
