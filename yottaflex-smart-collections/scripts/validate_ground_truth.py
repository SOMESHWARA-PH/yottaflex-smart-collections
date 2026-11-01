import csv
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with (root/"data/ground_truth/ground_truth.csv").open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
assert rows and len({x["anomaly_id"] for x in rows})==len(rows)
assert all(x["issue_type"] and x["ground_truth"] and x["evidence"] for x in rows)
print(f"PASS: {len(rows)} evidence-backed ground-truth rows")
