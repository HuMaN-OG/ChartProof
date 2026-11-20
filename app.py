"""ASGI entry point. Run python app.py or uvicorn app:app."""
import asyncio
import base64
import binascii
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from chartproof import cloud
from chartproof.images import picture, extract_local, assemble, MAX_BYTES
from chartproof.verify import compare
from decimal import Decimal, InvalidOperation

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="ChartProof", docs_url=None, redoc_url=None, openapi_url=None)
slots = asyncio.Semaphore(3)
SCENARIOS = {"original", "corrected", "restyled", "missing"}
MAX_BODY = 9*1024*1024


@app.middleware("http")
async def response_headers(request, call_next):
    r = await call_next(request)
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["Referrer-Policy"] = "no-referrer"
    r.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
    if request.url.path.startswith("/api/"):
        r.headers["Cache-Control"] = "no-store"
    return r


@app.exception_handler(ValueError)
async def invalid(request, e): return JSONResponse({"detail": str(e)}, status_code=422)
@app.exception_handler(cloud.CloudError)
async def cloud_failure(request, e): return JSONResponse({"detail": str(e)}, status_code=503)
@app.exception_handler(PermissionError)
async def denied(request, e): return JSONResponse({"detail": str(e)}, status_code=403)


async def body(req):
    chunks = bytearray()
    async for chunk in req.stream():
        chunks.extend(chunk)
        if len(chunks) > MAX_BODY:
            raise HTTPException(413, "The upload exceeds the request limit.")
    try:
        parsed = json.loads(chunks)
    except (ValueError, UnicodeError):
        raise ValueError("The request must contain JSON.") from None
    if not isinstance(parsed, dict):
        raise ValueError("Send a JSON object.")
    return parsed


def filedata(obj):
    try:
        string = obj.get("file", "")
        if not isinstance(string, str) or len(string) > MAX_BYTES*4//3+4:
            raise ValueError
        return base64.b64decode(string, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Choose a file up to 6 MiB.") from None


def check_chart(chart):
    if not isinstance(chart, dict) or chart.get("reviewed") is not True:
        raise ValueError("Confirm both chart readings before checking claims.")
    metric = chart.get("metric")
    rows = chart.get("rows")
    if not isinstance(metric, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9 &'/-]{0,79}", metric.strip()):
        raise ValueError("Enter a short English metric name.")
    if chart.get("unit") != "%" or not isinstance(rows, list) or not 1 <= len(rows) <= 80:
        raise ValueError("Provide 1–80 year/percentage rows.")
    seen = set()
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get("year"), str) or not re.fullmatch(r"(?:19|20)\d{2}", r["year"]) or r["year"] in seen:
            raise ValueError("Each row needs a unique four-digit year.")
        val = str(r.get("value", ""))
        if not re.fullmatch(r"\d{1,3}(?:\.\d{1,4})?", val) or Decimal(val) > 100:
            raise ValueError("Percentage values must be between 0 and 100, with up to four decimal places.")
        seen.add(r["year"])
    return chart


def checked_claim(s):
    if not isinstance(s, str) or not 1 <= len(s.strip()) <= 360:
        raise ValueError("Use a claim between 1 and 360 characters.")
    return s.strip()


@lru_cache(maxsize=4)
def sample(name):
    data = (ROOT/"samples"/(name+".png")).read_bytes()
    im, n = picture(data)
    c = assemble(data, 1, im, n, extract_local(im))
    # Built-in samples have reviewed ground truth. Never apply this bypass to user uploads.
    expected = json.loads((ROOT/"samples/ground_truth.json").read_text())[name]
    c["reviewed"] = (c["metric"] == expected["metric"] and
                     {r["year"]: r["value"] for r in c["rows"]} == expected["values"])
    if not c["reviewed"]:
        c["warning"] = "The installed OCR differs from the bundled reference. Review the extraction."
    c["filename"] = name+".png"
    return c


@app.get("/healthz")
def health():
    import shutil
    return {"status": "ok", "local_ocr": bool(shutil.which("tesseract")),
            "azure_extraction_configured": cloud.enabled(cloud.CU_NAMES),
            "azure_vision_configured": cloud.enabled(cloud.VISION_NAMES)}


@app.get("/api/sample/{name}")
async def get_sample(name: str):
    if name not in SCENARIOS:
        raise HTTPException(404, "Unknown sample.")
    async with slots:
        return await run_in_threadpool(sample, name)


@app.get("/api/evaluation")
def metrics(): return FileResponse(ROOT/"evaluation/results.json", media_type="application/json")


@app.post("/api/extract")
async def extract(req: Request):
    obj = await body(req)

    def perform():
        engine = obj.get("engine", "local")
        if engine not in ("local", "azure"):
            raise ValueError("Unknown extraction engine.")
        data = filedata(obj)
        page = obj.get("page", 1)
        if type(page) is not int:
            raise ValueError("Page must be a whole number.")
        im, n = picture(data, page)
        read = extract_local(im) if engine == "local" else cloud.extract_azure(
            im, req.headers.get("x-chartproof-token", ""))
        return assemble(data, page, im, n, read)
    async with slots:
        return await run_in_threadpool(perform)


@app.post("/api/check")
async def check(req: Request):
    obj = await body(req)
    a, b = check_chart(obj.get("before")), check_chart(obj.get("after"))
    claims = obj.get("claims")
    if not isinstance(claims, list) or not 1 <= len(claims) <= 20:
        raise ValueError("Provide 1–20 claim sentences.")
    links = obj.get("links", {})
    if not isinstance(links, dict) or len(links) > 20:
        raise ValueError("Invalid calculation links.")
    checked = [checked_claim(s) for s in claims]
    return {"results": [compare(s, a, b, links.get(s)) for s in checked]}


@app.post("/api/vision")
async def vision(req: Request):
    obj = await body(req)

    def run():
        token = req.headers.get("x-chartproof-token", "")
        cloud.authorize(cloud.VISION_NAMES, token)
        im, _ = picture(filedata(obj))
        return cloud.baseline(im, checked_claim(obj.get("claim")), token)
    async with slots:
        return await run_in_threadpool(run)


@app.get("/")
def home(): return FileResponse(ROOT/"web/index.html")


@app.get("/assets/ChartProof_Source.zip")
def source_archive():
    bundled = ROOT / "web" / "ChartProof_Source.zip"
    if bundled.is_file():
        return FileResponse(bundled, media_type="application/zip", filename=bundled.name)
    revision = os.getenv("VERCEL_GIT_COMMIT_SHA", "")
    ref = revision if re.fullmatch(r"[0-9a-fA-F]{40}", revision) else "refs/heads/main"
    return RedirectResponse(f"https://github.com/HuMaN-OG/ChartProof/archive/{ref}.zip")


app.mount("/assets", StaticFiles(directory=ROOT/"web"), name="assets")
app.mount("/samples", StaticFiles(directory=ROOT/"samples"), name="samples")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
