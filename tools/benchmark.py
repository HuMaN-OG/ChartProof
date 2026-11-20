"""Evaluate uncorrected OCR and claim replay on grouped chart revisions."""
import argparse
import json
import os
from pathlib import Path
import sys
from PIL import ImageFilter
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chartproof.language import classify
from chartproof.images import extract_local
from chartproof.verify import compare, SUPPORTED as S, FALSE as F, UNKNOWN as U
from chartproof.cloud import baseline
from charts import chart


FAMILIES = ["Graduation rate", "Retention rate", "Recycling rate", "Renewal rate", "Delivery rate", "Pass rate",
            "Response rate", "Acceptance rate", "Adoption rate", "Completion rate", "Occupancy rate", "Participation rate"]


def evaluate(live=False):
    m = dict.fromkeys(["families", "images", "ocr_pairs_correct", "ocr_pairs_total", "ocr_extra", "stale_detected", "stale_total",
                       "cosmetic_alerts", "cosmetic_total", "missing_recognized", "missing_total", "verdict_correct", "verdict_total",
                       "persistence_correct", "false_approved", "false_claims", "answered", "answerable", "answerable_answered"], 0)
    m["design"] = ("Twelve constructed chart families, each with an original, corrected, reordered/recoloured and missing-year figure. "
                   "Five frozen claim patterns per family. Evaluation runs OCR on pixels and uses no manual corrections. "
                   "The official CBSE figures and low-resolution challenge are reported separately.")
    detail = []
    mistakes = []
    visual = {}
    for i, metric in enumerate(FAMILIES):
        a, b = str(2000+i), str(2001+i)
        old = 40+2*i
        high = old+14
        low = old+4
        pairs = [(a, old), (b, high)]
        variants = {"base": pairs, "corrected": [(a, old), (b, low)], "redesign": list(
            reversed(pairs)), "missing": [(b, high)]}
        evidence = {}
        images = {}
        for name, values in variants.items():
            img = chart(metric, values, style=(i+int(name == "redesign")) % 3)
            images[name] = img
            c = extract_local(img)
            evidence[name] = c
            truth = {y: str(v) for y, v in values}
            got = {r["year"]: r["value"] for r in c["rows"]}
            m["images"] += 1
            m["ocr_pairs_total"] += len(truth)
            m["ocr_pairs_correct"] += sum(got.get(y) == val for y, val in truth.items())
            m["ocr_extra"] += len(set(got)-set(truth))
        prompts = [
            (f"{metric} rose by at least 10 percentage points from {a} to {b}.", [S, F, S, U]),
            (f"{metric} grew by at least 18% from {a} to {b}.", [S, F, S, U]),
            (f"{metric} was at least {old+9}% in {b}.", [S, F, S, S]),
            (f"{metric} was above 20% in {b}.", [S, S, S, S]),
            ("More people participated in the programme.", [U, U, U, U])]
        for n, (phrase, expected) in enumerate(prompts):
            for ix, name in enumerate(["corrected", "redesign", "missing"], 1):
                res = compare(phrase, evidence["base"], evidence[name])
                pred = res["after"]["status"]
                true = expected[ix]
                m["verdict_total"] += 1
                m["verdict_correct"] += int(pred == true)
                m["persistence_correct"] += int(res["before"]["status"] == true)
                m["answered"] += int(pred != U)
                m["answerable"] += int(true != U)
                m["answerable_answered"] += int(true != U and pred != U)
                if true == F:
                    m["false_claims"] += 1
                    m["false_approved"] += int(pred == S)
                if expected[0] == S and true == F:
                    m["stale_total"] += 1
                    m["stale_detected"] += int(res["transition"] == "Outdated claim")
                if name == "redesign" and expected[0] == S:
                    m["cosmetic_total"] += 1
                    m["cosmetic_alerts"] += int(pred != S)
                if name == "missing" and expected[0] == S and true == U:
                    m["missing_total"] += 1
                    m["missing_recognized"] += int(pred == U)
                row = {"family": i+1, "revision": name, "claim": phrase,
                       "expected": true, "predicted": pred, "transition": res["transition"]}
                if live:
                    k = (i, n, name)
                    visual[k] = baseline(images[name], phrase, os.environ["CHARTPROOF_CLOUD_TOKEN"])
                    row["foundry"] = visual[k]["status"]
                detail.append(row)
                if pred != true:
                    mistakes.append(row)
        m["families"] += 1
    public = chart("CBSE pass rate", [("2023", 87.33), ("2024", 87.98), ("2025", 88.39)])
    read = extract_local(public)
    p = "CBSE pass rate rose by exactly 0.41 percentage points from 2024 to 2025."
    m["public_example"] = {"source": "CBSE Class XII overall pass percentages, official 2024 and 2025 result releases. Chart redrawn for this project.",
                           "rows": read["rows"], "claim": p, "verdict": compare(p, read, read)["after"]["status"]}
    stress = public.resize((172, 98)).filter(ImageFilter.GaussianBlur(.8)).resize((920, 520))
    blur = extract_local(stress)
    m["legibility_challenge"] = {"labels_read": len(blur["rows"]), "metric_read": blur["metric"], "expected": "Insufficient evidence",
                                 "verdict": compare(p, read, blur)["after"]["status"]}
    held = json.loads((ROOT/"evaluation/language_holdout.json").read_text())
    m["language_evaluation"] = [{"expected": label, "phrase": phrase, "predicted": classify(phrase)[0]}
                                for label, phrases in held.items() for phrase in phrases]
    m["language_correct"] = sum(r["expected"] == r["predicted"] for r in m["language_evaluation"])
    m["language_total"] = len(m["language_evaluation"])
    m["failures"] = mistakes
    m["cases"] = detail
    m["foundry"] = {"live": live, "evaluated": len(visual), "correct": sum(
        r.get("foundry") == r["expected"] for r in detail) if live else None}
    return m


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--azure", action="store_true",
                        help="Calls the configured paid vision deployment once per revision claim")
    parser.add_argument("--out", type=Path)
    opts = parser.parse_args()
    m = evaluate(opts.azure)
    dest = opts.out or ROOT/"evaluation"/("foundry-results.json" if opts.azure else "results.json")
    dest.write_text(json.dumps(m, indent=2)+"\n")
    print(json.dumps({k: v for k, v in m.items() if k not in ("cases", "failures")}, indent=2))
