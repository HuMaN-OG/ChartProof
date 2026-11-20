"""Measure English check coverage on the published, unseen-chart ChartCheck T2 CSV."""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chartproof.verify import compile_claim


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("csv", type=Path)
    p.add_argument("--out", type=Path, required=True)
    o = p.parse_args()
    with o.csv.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    accepted = [i for i, r in enumerate(rows) if not compile_claim(r["claim"]).reason]
    o.out.write_text(json.dumps({"source": "ChartCheck test_two.csv", "csv_sha256": hashlib.sha256(o.csv.read_bytes()).hexdigest(),
                                 "rows": len(rows), "distinct_images": len({r["chart_img"] for r in rows}), "accepted": len(accepted), "row_indices": accepted,
                                 "scope": "Admission by the English operation parser on untouched sentences. This is a coverage measure, not image-level accuracy."}, indent=2)+"\n")
