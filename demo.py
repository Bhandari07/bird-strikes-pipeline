#!/usr/bin/env python3
"""Run the pipeline and print the four business answers without extra installs."""
from pathlib import Path
from pipeline import run

root = Path(__file__).resolve().parent
s = run(root / "data", root / "output")
t = s["totals"]
a = s["airports"][0]
p = s["phases"][0]
w = s["species_cost"][0]
print("\nBUSINESS ANSWERS")
print(
    f"1. Highest reported airport: {a['airport']} — {a['incidents']:,} incidents. Departure status unverified."
)
print("2. Annual reported incidents:")
for row in s["annual"]:
    print(f"   {row['year']}: {row['incidents']:,}")
print(
    f"   Excludes {t['missing_dates']} undated records. Counts are not exposure-adjusted risk rates."
)
print(
    f"3. Most frequent phase: {p['phase']} — {p['incidents']:,} incidents ({p['incidents']/t['incidents']:.1%} of all records)."
)
print(
    f"4. Highest total reported cost by species: {w['species']} — ${w['total_reported_cost']:,} across {w['incidents']:,} incidents."
)
print(
    "Scope: all supplied wildlife. Cost currency assumed USD and not inflation-adjusted."
)
print("\nQUALITY:")
for q in s["quality"]:
    print(f"  {q['rule']}: {q['issues']:,}")
