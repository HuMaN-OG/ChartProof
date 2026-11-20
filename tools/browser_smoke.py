import tempfile
import os
import sys
import time
import subprocess
import urllib.request
import json
import re
from pathlib import Path
from playwright.sync_api import expect, sync_playwright
src = Path(__file__).resolve().parents[1]
art = Path(tempfile.mkdtemp(prefix='chartproof-browser-'))
env = dict(os.environ, PORT="8764", HOST="127.0.0.1", OMP_THREAD_LIMIT="1",
           NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
server = subprocess.Popen([sys.executable, "app.py"], cwd=src, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for i in range(50):
        try:
            op.open('http://127.0.0.1:8764/healthz', timeout=2).read()
            break
        except OSError:
            time.sleep(.2)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.getenv(
            "CHARTPROOF_CHROMIUM"), args=["--no-sandbox", "--no-proxy-server"])
        page = browser.new_page(viewport={"width": 1360, "height": 1050}, accept_downloads=True)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:8764")
        page.get_by_role("button", name="Upload a chart").wait_for()
        page.set_input_files("#quickFile", str(src/"samples/original.png"))
        expect(page.locator("#editor")).to_be_visible()
        expect(page.locator("#values")).to_have_value(re.compile(r"2025, 72"))
        page.check("#confirmed")
        page.click("#apply")
        page.fill("#newClaim", "Placement rate was at least 70% in 2025.")
        page.locator("#claimForm button").click()
        page.get_by_text("Supported", exact=True).wait_for()
        page.click("#openEntry") if page.locator("#openEntry").is_visible() else page.locator(".card").first.get_by_role("button", name="Paste values / CSV").click()
        page.fill("#entryMetric", "Placement rate")
        page.fill("#entryRows", "year,percentage\n2024,60\n2025,66")
        page.check("#entryConfirm")
        page.click("#entryForm button[type=submit]")
        page.get_by_text("Contradicted", exact=True).wait_for()
        page.click("#load")
        page.get_by_text("Outdated claim", exact=True).wait_for()
        page.screenshot(path=str(art/"workspace.png"), full_page=True)
        page.select_option("#scenario", "restyled")
        page.click("#load")
        page.get_by_text("restyled.png · Local OCR", exact=True).wait_for()
        threshold_claim = page.locator(".result").filter(has_text="at least 10 percentage points")
        threshold_claim.get_by_text("Verdict retained", exact=True).wait_for()
        assert "Outdated claim" not in page.locator("#claimList").inner_text()
        page.select_option("#scenario", "missing")
        page.click("#load")
        page.get_by_text("Needs evidence", exact=True).wait_for()
        page.locator(".card").nth(1).get_by_role("button", name="Review / replace").click()
        page.set_input_files("#file", str(src/"samples/corrected.pdf"))
        page.click("#extract")
        expect(page.locator("#values")).to_have_value(re.compile(r"2025, 68"))
        page.check("#confirmed")
        page.click("#apply")
        page.get_by_text("Outdated claim", exact=True).wait_for()
        page.fill("#newClaim", "Placement rate grew by 20% from 2024 to 2025.")
        page.locator("#claimForm button").click()
        expect(page.locator(".result details")).to_have_count(3)
        page.reload()
        page.get_by_text("Placement rate grew by 20% from 2024 to 2025.", exact=True).wait_for()
        expect(page.locator(".result details")).to_have_count(3)
        with page.expect_download() as d:
            page.click("#export")
        export = art/"audit.json"
        d.value.save_as(str(export))
        saved = json.loads(export.read_text())
        assert saved["schema"] == 1 and len(saved["history"]) == 1 and len(saved["results"]) == 3
        page.set_input_files("#restoreFile", str(export))
        page.get_by_text("Outdated claim", exact=True).first.wait_for()
        page.get_by_role("button", name="Benchmark", exact=True).click()
        page.get_by_text("Evaluation conditions", exact=True).wait_for()
        page.get_by_role("button", name="Workspace", exact=True).click()
        page.set_viewport_size({"width": 390, "height": 840})
        for element in page.locator("header, main, .card, .result, .chartMeta, footer").all():
            box = element.bounding_box()
            assert box and box["x"] >= 0 and box["x"] + box["width"] <= 391, box
        page.screenshot(path=str(art/"mobile.png"), full_page=True)
        page.set_viewport_size({"width": 1360, "height": 1050})
        page.fill("#newClaim", "The gains cleared our ten-point reporting threshold.")
        page.locator("#claimForm button").click()
        target = page.locator(".result").filter(has_text="The gains cleared")
        target.get_by_role("button", name="Link a calculation").click()
        page.select_option("#bindOp", "points")
        page.fill("#bindFrom", "2024")
        page.fill("#bindTo", "2025")
        page.fill("#bindTarget", "10")
        page.check("#bindConfirm")
        page.get_by_role("button", name="Save calculation link").click()
        target.locator(".badge").filter(has_text="Outdated claim").wait_for()
        assert not errors, errors
        print("Browser workflows passed: first load, corrected/redesigned/missing charts, PDF upload and confirmation, third claim, reload, export, restore, benchmark, mobile width and zero JavaScript errors.")
        browser.close()
finally:
    server.terminate()
    server.wait(timeout=5)
