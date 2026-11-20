"""Original, deterministic labelled bar charts used by the demo and benchmark."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROWS = [("2023", 55), ("2024", 60), ("2025", 72)]


@lru_cache
def font(n, bold=False):
    for name in (("DejaVuSans-Bold.ttf", "Arial Bold.ttf") if bold else ("DejaVuSans.ttf", "Arial.ttf")):
        try:
            return ImageFont.truetype(name, n)
        except OSError:
            pass
    return ImageFont.load_default(size=n)


def chart(title, rows, style=0):
    W, H = 920, 520
    im = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(im)
    ink = "#142c33"
    muted = "#4e6268"
    d.text((62, 41), title, font=font(39, True), fill=ink)
    x0, x1, base = 78, 860, 421
    for y in (170, 245, 320, 420):
        d.line((x0, y, x1, y), fill="#dfe8e7", width=2)
    for i, (year, value) in enumerate(rows):
        x = x0+(x1-x0)*(i+.5)/len(rows)
        y = base-2.65*value
        color = ("#217166", "#5b588e", "#34638a")[style % 3]
        d.rounded_rectangle((x-44, y, x+44, base), radius=3, fill=color)
        d.text((x, y-26), f"{value}%", font=font(27, True), anchor="mm", fill=ink)
        d.text((x, 457), str(year), font=font(27), anchor="mm", fill=muted)
    return im


if __name__ == "__main__":
    cases = {"original": DEFAULT_ROWS, "corrected": [("2023", 55), ("2024", 60), ("2025", 68)],
             "restyled": list(reversed(DEFAULT_ROWS)), "missing": [("2023", 55), ("2025", 72)]}
    for name, rows in cases.items():
        im = chart("Placement rate", rows, int(name == "restyled"))
        im.save(ROOT/"samples"/(name+".png"), optimize=True)
        im.save(ROOT/"samples"/(name+".pdf"), format="PDF", resolution=110)
