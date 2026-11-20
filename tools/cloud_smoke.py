"""Make one real Content Understanding call and one real vision-model call."""
from pathlib import Path
import os
import sys
import json
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chartproof.images import picture
from chartproof.cloud import extract_azure, baseline
from chartproof.verify import verify, compile_claim

im, _ = picture((ROOT/"samples/corrected.png").read_bytes())
token = os.environ["CHARTPROOF_CLOUD_TOKEN"]
claim = "Placement rate rose by at least 10 percentage points from 2024 to 2025."
read = extract_azure(im, token)
pred = verify(compile_claim(claim), read)
direct = baseline(im, claim, token)
result = {"extracted_metric": read["metric"], "rows": read["rows"], "pipeline": pred["status"],
          "vision_baseline": direct, "reference": "Contradicted"}
print(json.dumps(result, indent=2))
if pred["status"] != "Contradicted" or direct["status"] != "Contradicted":
    sys.exit(1)
