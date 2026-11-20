"""Read a selected PDF page or image, then align printed percentage labels to years."""
import base64
import csv
import hashlib
import io
import math
import re
import shutil
import subprocess
import threading
from collections import defaultdict
from PIL import Image, ImageOps, UnidentifiedImageError
import pypdfium2 as pdfium

MAX_BYTES = 6*1024*1024
MAX_PIXELS = 18_000_000
PDF_LOCK = threading.Lock()
YEAR_RE = re.compile(r"(?:19|20)\d{2}")
VALUE_RE = re.compile(r"(100(?:\.0+)?|[0-9]{1,2}(?:\.[0-9]{1,4})?)[%％]")


def picture(data, page=1):
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Choose a file no larger than 6 MiB.")
    if not 1 <= page <= 500:
        raise ValueError("Page must be between 1 and 500.")
    if data.startswith(b"%PDF-"):
        with PDF_LOCK:
            try:
                with pdfium.PdfDocument(data) as doc:
                    if page > len(doc):
                        raise ValueError(f"This PDF has {len(doc)} page(s).")
                    p = doc[page-1]
                    try:
                        w, h = p.get_size()
                        if min(w, h) <= 0 or not math.isfinite(w+h):
                            raise ValueError("The PDF page size is invalid.")
                        scale = min(2.7, 1800/max(w, h))
                        bitmap = p.render(scale=scale)
                        try:
                            im = bitmap.to_pil().convert("RGB")
                        finally:
                            bitmap.close()
                    finally:
                        p.close()
                    return im, len(doc)
            except pdfium.PdfiumError as e:
                raise ValueError("The PDF could not be opened. Use an unlocked PDF.") from e
    if page != 1:
        raise ValueError("An image has one page.")
    try:
        with Image.open(io.BytesIO(data)) as original:
            if original.format not in {"PNG", "JPEG", "WEBP"} or original.width*original.height > MAX_PIXELS:
                raise ValueError("Choose a PNG, JPEG or WebP of up to 18 megapixels.")
            trans = ImageOps.exif_transpose(original)
            im = Image.new("RGB", trans.size, "white")
            if "A" in trans.getbands():
                im.paste(trans, mask=trans.getchannel("A"))
            else:
                im.paste(trans.convert("RGB"))
            im.thumbnail((1800, 1800))
            return im, 1
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as e:
        raise ValueError("The image is unreadable or too large.") from e


def png(im):
    f = io.BytesIO()
    im.save(f, format="PNG")
    return f.getvalue()


def preview(im):
    view = im.copy()
    view.thumbnail((850, 680))
    f = io.BytesIO()
    view.save(f, format="JPEG", quality=79)
    return "data:image/jpeg;base64,"+base64.b64encode(f.getvalue()).decode()


def ocr_words(im):
    if not shutil.which("tesseract"):
        raise ValueError(
            "Local OCR requires Tesseract with English data. Use the Docker image or install Tesseract.")
    try:
        proc = subprocess.run(["tesseract", "stdin", "stdout", "-l", "eng", "--psm", "11", "tsv"],
                              input=png(im), capture_output=True, timeout=22, check=True)
    except (subprocess.SubprocessError, OSError) as e:
        raise ValueError("OCR could not finish. Try a clearer crop or a smaller page.") from e
    words = []
    for w in csv.DictReader(io.StringIO(proc.stdout.decode(errors="replace")), delimiter="\t", quoting=csv.QUOTE_NONE):
        if w.get("level") != "5" or not (w.get("text") or "").strip():
            continue
        word = w["text"].strip()
        x, y = int(w["left"]), int(w["top"])
        width, height = int(w["width"]), int(w["height"])
        words.append({"text": word, "x": (x+width/2)/im.width, "y": (y+height/2)/im.height,
                      "box": [round(x/im.width, 4), round(y/im.height, 4), round(width/im.width, 4), round(height/im.height, 4)],
                      "conf": float(w["conf"]), "line": (w["block_num"], w["par_num"], w["line_num"])})
    return words


def extract_local(im, *, retry=True):
    words = ocr_words(im)
    lines = defaultdict(list)
    for w in words:
        lines[w["line"]].append(w)
    title = ""
    for line in sorted(lines.values(), key=lambda group: min(w["y"] for w in group)):
        t = " ".join(w["text"] for w in line).strip()
        if min(w["y"] for w in line) < .36 and re.fullmatch(r"[A-Za-z][A-Za-z &'/+-]{2,74}", t):
            title = t
            break
    years = [w for w in words if YEAR_RE.fullmatch(w["text"])]
    vals = [w for w in words if VALUE_RE.fullmatch(w["text"])]
    # Percentage axes can look like values. Axis ticks form a column or row outside the bar midlines.
    warning = ""
    rows = []
    if years and len({w["text"] for w in years}) == len(years):
        xs = [w["x"] for w in years]
        ys = [w["y"] for w in years]
        axis = "x" if (max(xs)-min(xs)) >= (max(ys)-min(ys)) else "y"
        if len(years) == 1:
            axis = "x"
        coords = sorted(w[axis] for w in years)
        spacing = min((b-a for a, b in zip(coords, coords[1:])), default=.4)
        tolerance = min(.095, spacing*.40)
        for y in years:
            matches = [v for v in vals if abs(v[axis]-y[axis]) <= tolerance]
            if len(matches) != 1:
                warning = "A year has missing or ambiguous percentage labels. Inspect the image and confirm the rows."
                continue
            v = matches[0]
            if min(y["conf"], v["conf"]) < 55:
                warning = "OCR confidence is low on at least one label. Confirm the proposed values."
            rows.append({"year": y["text"], "value": v["text"][:-1], "box": v["box"]})
    else:
        warning = "Year labels are missing or repeated. Check that the selected page contains one chart."
    if len(rows) < len(vals):
        warning = warning or "Some percentage labels could not be linked to a year."
        if retry and max(im.size) > 1100:
            smaller = im.copy()
            smaller.thumbnail((1000, 1000))
            second = extract_local(smaller, retry=False)
            if len(second["rows"]) > len(rows):
                return second
    if not title or not rows:
        warning = warning or "The metric or values need manual transcription."
    return {"metric": title, "rows": sorted(rows, key=lambda r: r["year"]), "warning": warning, "engine": "Local OCR"}


def assemble(data, page, im, pages, reading):
    return {**reading, "page": page, "pages": pages, "sha256": hashlib.sha256(data).hexdigest(),
            "image": preview(im), "unit": "%", "reviewed": False,
            "observed": {"metric": reading["metric"], "rows": [dict(r) for r in reading["rows"]]}}
