import base64
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image
from app import app, check_chart, sample
from chartproof.cloud import chartjs, extract_azure, CloudError, baseline
from chartproof.images import picture, extract_local
from chartproof.verify import compare, compile_claim, verify, UNKNOWN, FALSE, SUPPORTED

ROOT = Path(__file__).resolve().parents[1]
TEXT = "The placement rate rose by at least 10 percentage points from 2024 to 2025."


def c(points, metric="Placement rate"):
    return {"metric": metric, "rows": [{"year": y, "value": v} for y, v in points], "unit": "%", "reviewed": True}


A = c([("2024", "60"), ("2025", "72")])
B = c([("2024", "60"), ("2025", "68")])
def check(sentence, chart=A): return verify(compile_claim(sentence), chart)


class ProofTests(unittest.TestCase):
    def test_stale(self): self.assertEqual(compare(TEXT, A, B)["transition"], "Outdated claim")
    def test_cosmetic(self): self.assertEqual(
        compare(TEXT, A, c([("2025", "72"), ("2024", "60")]))["transition"], "Verdict retained")

    def test_missing_evidence(self): self.assertEqual(check(TEXT, c([("2025", "72")]))["status"], UNKNOWN)

    def test_metric_mismatch(self): self.assertEqual(
        check(TEXT, c([("2024", "60"), ("2025", "72")], "Employment rate"))["status"], UNKNOWN)

    def test_headcount(self): self.assertEqual(
        check("More students were placed in 2025.")["status"], UNKNOWN)

    def test_relative(self): self.assertEqual(
        check("Placement rate grew by 20% from 2024 to 2025.")["status"], SUPPORTED)

    def test_points_and_percent(self): self.assertEqual(
        check("Placement rate rose by 20 percentage points from 2024 to 2025.")["status"], FALSE)

    def test_lookup(self): self.assertEqual(
        check("In 2025, the placement rate was at least 72%.")["status"], SUPPORTED)

    def test_zero_denominator(self): self.assertEqual(
        check("Placement rate grew by 20% from 2024 to 2025.", c([("2024", "0"), ("2025", "10")]))["status"], UNKNOWN)

    def test_reversed_interval(self): self.assertEqual(
        check("Placement rate fell by exactly 12 percentage points from 2025 to 2024.")["status"], SUPPORTED)

    def test_wrong_direction_upper_bound(self): self.assertEqual(
        check("Placement rate fell by at most 3 percentage points from 2024 to 2025.")["status"], FALSE)
    def test_unsupported_qualifier(self): self.assertEqual(
        check("Placement rate was 72% in 2025 because fees fell.")["status"], UNKNOWN)

    def test_compound(self): self.assertEqual(check(TEXT+" All graduates got jobs.")["status"], UNKNOWN)

    def test_reviewed_free_wording(self):
        link = {"operation": "points", "metric": "Placement rate", "years": [
            "2024", "2025"], "direction": 1, "compare": ">=", "target": "10"}
        article = compare("The gains cleared our ten-point reporting threshold.", A, B, link)
        self.assertEqual(article["binding_source"], "Reviewer linked")
        self.assertEqual(article["transition"], "Outdated claim")

    def test_bad_binding(self):
        with self.assertRaises(ValueError):
            compare(TEXT, A, B, {"operation": "anything"})

    def test_change_narrative(self): self.assertIn("8 percentage points",
                                                   compare(TEXT, A, B)["after"]["correction"])

    def test_decimals(self): self.assertEqual(check("Placement rate rose by 0.41 percentage points from 2024 to 2025.", c(
        [("2024", "87.98"), ("2025", "88.39")]))["status"], SUPPORTED)


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.client = TestClient(app)
    def test_home(self): self.assertEqual(self.client.get("/").status_code, 200)

    def test_source_download_after_repository_move(self):
        path = "/assets/ChartProof_Source.zip"
        github = "https://github.com/HuMaN-OG/ChartProof/archive/"
        with TemporaryDirectory() as temporary, patch("app.ROOT", Path(temporary)):
            for sha, ref in [("", "refs/heads/main"), ("a" * 40, "a" * 40)]:
                with self.subTest(ref=ref), patch.dict(os.environ, {"VERCEL_GIT_COMMIT_SHA": sha}):
                    response = self.client.get(path, follow_redirects=False)
                    self.assertEqual(response.status_code, 307)
                    self.assertEqual(response.headers["location"], github + ref + ".zip")
            bundled = Path(temporary) / "web" / "ChartProof_Source.zip"
            bundled.parent.mkdir()
            bundled.write_bytes(b"PK\x05\x06" + bytes(18))
            response = self.client.get(path, follow_redirects=False)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, bundled.read_bytes())

    def test_health(self): self.assertTrue(self.client.get("/healthz").json()["local_ocr"])
    def test_sample(self): self.assertTrue(self.client.get("/api/sample/original").json()["reviewed"])
    def test_unknown_sample(self): self.assertEqual(self.client.get("/api/sample/foreign").status_code, 404)

    def test_invalid_files(self):
        for b in [b"not an image", b"%PDF-invalid"]:
            self.assertEqual(self.client.post(
                "/api/extract", json={"file": base64.b64encode(b).decode()}).status_code, 422)

    def test_external_uploads_require_review(self):
        for f in ["corrected.png", "corrected.pdf"]:
            r = self.client.post(
                "/api/extract", json={"file": base64.b64encode((ROOT/"samples"/f).read_bytes()).decode()})
            self.assertEqual(r.status_code, 200)
            self.assertFalse(r.json()["reviewed"])
            self.assertEqual({e["year"]: e["value"] for e in r.json()["rows"]},
                             {"2023": "55", "2024": "60", "2025": "68"})

    def test_refuse_unreviewed(self):
        self.assertEqual(self.client.post(
            "/api/check", json={"before": dict(A, reviewed=False), "after": B, "claims": [TEXT]}).status_code, 422)

    def test_accept_review(self):
        r = self.client.post("/api/check", json={"before": A, "after": B, "claims": [TEXT]})
        self.assertEqual(r.json()["results"][0]["transition"], "Outdated claim")

    def test_validate_evidence(self):
        for rows in [[("2025", "101")], [("2025", "nan")], [("2025", "1"), ("2025", "2")], [("Q1", "50")]]:
            with self.assertRaises(ValueError):
                check_chart(c(rows))

    def test_wrong_page(self):
        with self.assertRaises(ValueError):
            picture((ROOT/"samples/original.pdf").read_bytes(), 2)

    def test_malformed_json(self): self.assertEqual(
        self.client.post("/api/check", content="{").status_code, 422)

    def test_bad_azure_auth(self):
        with patch.dict(os.environ, {"AZURE_OPENAI_ENDPOINT": "https://a.openai.azure.com", "AZURE_OPENAI_API_KEY": "test", "AZURE_VISION_DEPLOYMENT": "test", "CHARTPROOF_CLOUD_TOKEN": "private-test"}):
            self.assertEqual(self.client.post("/api/vision", json={"claim": TEXT}).status_code, 403)


class AzureContractTests(unittest.TestCase):
    nested = {"contents": [{"figures": [{"kind": "chart", "content": {"type": "bar", "data": {"labels": ["2024", "2025"],
                                                                                              "datasets": [{"label": "Placement rate", "data": [60, 72]}]}}}]}]}
    env = {"AZURE_CU_ENDPOINT": "https://example.cognitiveservices.azure.com", "AZURE_CU_KEY": "not-a-live-key",
           "CHARTPROOF_CLOUD_TOKEN": "unit-test", "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
           "AZURE_OPENAI_API_KEY": "not-a-live-key", "AZURE_VISION_DEPLOYMENT": "test-model"}

    def test_normalized_chart(self): self.assertEqual(chartjs(self.nested)["rows"][1]["value"], "72")

    def test_multiple_figures(self):
        with self.assertRaises(CloudError):
            chartjs({"contents": self.nested["contents"]*2})

    def test_binary_and_poll(self):
        poll = "https://example.cognitiveservices.azure.com/contentunderstanding/analyzerResults/123"
        with patch.dict(os.environ, self.env), patch("chartproof.cloud.exchange", side_effect=[({}, {"Operation-Location": poll}), ({"status": "Succeeded", "result": self.nested}, {})]) as exchange:
            res = extract_azure(Image.new("RGB", (32, 32)), "unit-test")
            self.assertIn("prebuilt-documentSearch:analyzeBinary", exchange.call_args_list[0].args[0])
            self.assertTrue(exchange.call_args_list[0].args[2].startswith(b"\x89PNG"))
            self.assertEqual(res["metric"], "Placement rate")

    def test_foreign_poll_address(self):
        with patch.dict(os.environ, self.env), patch("chartproof.cloud.exchange", return_value=({}, {"Operation-Location": "https://other.example/test"})):
            with self.assertRaises(CloudError):
                extract_azure(Image.new("RGB", (20, 20)), "unit-test")

    def test_direct_vision_contract(self):
        data = ({"choices": [{"message": {"content": json.dumps(
            {"status": SUPPORTED, "reason": "Evidence matches."})}}]}, {})
        with patch.dict(os.environ, self.env), patch("chartproof.cloud.exchange", return_value=data) as exchange:
            res = baseline(Image.new("RGB", (20, 20)), TEXT, "unit-test")
            self.assertEqual(res["status"], SUPPORTED)
            sent = json.loads(exchange.call_args.args[2])
            self.assertEqual(sent["model"], "test-model")
            self.assertTrue(sent["messages"][1]["content"][1]["image_url"]
                            ["url"].startswith("data:image/png;base64,"))

    def test_invalid_model_output(self):
        with patch.dict(os.environ, self.env), patch("chartproof.cloud.exchange", return_value=({"choices": [{"message": {"content": "invalid"}}]}, {})):
            with self.assertRaises(CloudError):
                baseline(Image.new("RGB", (20, 20)), TEXT, "unit-test")
