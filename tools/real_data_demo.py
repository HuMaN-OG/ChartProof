"""Redraw official CBSE Class XII pass-rate statistics for reproducible demos.

One image deliberately contains a wrong number and is marked DEMO ONLY.
It must never be represented as an official CBSE chart or revised statistic.
"""
from argparse import ArgumentParser
import csv
from pathlib import Path
from PIL import ImageDraw
from charts import chart, font

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "cbse_class_xii_pass_rates.csv"


def published_rates(path=DATA):
    with open(path, newline="", encoding="utf-8") as source:
        records = list(csv.DictReader(source))
    years = {r["year"]: float(r["overall_pass_percentage"]) for r in records}
    if set(years) != {"2024", "2025", "2026"} or not all(0 <= v <= 100 for v in years.values()):
        raise ValueError("Expected published pass rates for the three documented years.")
    return years


def generate(output):
    rates = published_rates()
    output.mkdir(parents=True, exist_ok=True)
    cases = {
        "01_official_prior_chart.png": (["2024", "2025"], False, 0),
        "02_official_updated_chart.png": (["2024", "2025", "2026"], False, 0),
        "03_intentional_reporting_error.png": (["2025", "2026"], True, 0),
        "04_official_corrected_chart.png": (["2025", "2026"], False, 0),
        "05_cosmetic_redesign.png": (["2026", "2025", "2024"], False, 1),
    }
    for name, (years, intentional_error, style) in cases.items():
        rows = [(year, 88.90 if intentional_error and year == "2026" else rates[year]) for year in years]
        im = chart("CBSE pass rate", rows, style=style)
        text = ("DEMO ONLY - INTENTIONALLY WRONG VALUE" if intentional_error
                else "CBSE published figures - redrawn for demonstration")
        ImageDraw.Draw(im).text((64, 493), text, font=font(15, intentional_error),
                               fill="#9e2f32" if intentional_error else "#4e6268")
        im.save(output / name, optimize=True)
        print(output / name)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "samples" / "real-data")
    generate(parser.parse_args().out)
