from pathlib import Path
import sqlite3, json, shutil, sys
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from bird_strikes.publication import current_release

r = current_release(root / "output")
out = root / "results"
out.mkdir(exist_ok=True)
for name in [
    "summary.json",
    "audit.csv",
    "quality.csv",
    "annual.csv",
    "airports.csv",
    "phases.csv",
    "species_cost.csv",
    "quality_issues.csv",
    "weather.csv",
]:
    shutil.copy2(r / name, out / name)
db = sqlite3.connect(r / "bird_strikes.sqlite")
db.row_factory = sqlite3.Row
sql = """select species,count(*) incidents,sum(cost) cost,sum(damage) damaged,sum(cost>0) positive_cost,
round(100.0*sum(damage)/count(*),2) damage_pct,round(1.0*sum(cost)/count(*),2) mean_reported_cost
from reporting_strikes group by species order by cost desc limit 8"""
impact = [dict(x) for x in db.execute(sql)]
total = db.execute(
    "select count(*),sum(cost),sum(cost>0),sum(damage) from reporting_strikes"
).fetchone()
analysis = {
    "species": impact,
    "total_incidents": total[0],
    "total_reported_cost": total[1],
    "positive_cost_incidents": total[2],
    "damaged_incidents": total[3],
    "positive_cost_pct": 100 * total[2] / total[0],
}
(out / "impact_analysis.json").write_text(json.dumps(analysis, indent=2))
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)
s = json.loads((out / "summary.json").read_text())
fig, ax = plt.subplots(figsize=(10, 4.7))
ax.plot(
    [v["year"] for v in s["annual"]],
    [v["incidents"] for v in s["annual"]],
    marker="o",
    color="#176B87",
)
ax.set(
    title="Reported wildlife incidents by year",
    xlabel="Year",
    ylabel="Reported incidents",
)
ax.grid(axis="y", alpha=0.2)
fig.tight_layout()
fig.savefig(out / "annual_incidents.png", dpi=160)
plt.close(fig)
fig, ax = plt.subplots(figsize=(10, 4.7))
top = impact[:5]
ax.barh(
    [x["species"] for x in top][::-1],
    [x["cost"] / 1e6 for x in top][::-1],
    color="#176B87",
)
ax.set(
    title="Species with the highest total reported cost",
    xlabel="Source dollars in millions (USD assumed)",
)
fig.tight_layout()
fig.savefig(out / "species_cost.png", dpi=160)
plt.close(fig)
lines = [
    "# Additional business findings",
    "",
    f"Only {total[2]:,} of {total[0]:,} incidents ({analysis['positive_cost_pct']:.2f}%) have positive recorded cost. A zero can mean no cost or unrecorded cost; it is not evidence of a confirmed zero loss.",
    "",
    "| Species | Incidents | Damage recorded | Damage share | Total reported cost |",
    "|---|---:|---:|---:|---:|",
]
for x in impact[:5]:
    lines.append(
        f"| {x['species']} | {x['incidents']:,} | {x['damaged']:,} | {x['damage_pct']:.2f}% | ${x['cost']:,} |"
    )
lines += [
    "",
    "The damage share is the proportion of reported incidents marked as causing damage. It does not measure strike probability per flight. Combining this share with incident counts and recorded cost gives a more useful prevention shortlist than cost totals alone. Small groups and incomplete costs still limit the comparison.",
    "",
    "Canada goose and white-tailed deer warrant separate operational discussion because they contribute high total recorded cost with different incident counts. Confirm scope before using a wildlife-wide ranking for a birds-only policy.",
    "",
    "An exposure-adjusted airport ranking requires matched airport operations. No denominator has been invented. FAA operations, a verified airport-code crosswalk and reporting coverage should be the first augmentation.",
]
(out / "BUSINESS_FINDINGS.md").write_text("\n".join(lines))
print(json.dumps(analysis, indent=2))
