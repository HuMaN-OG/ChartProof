# Real-data demonstration: CBSE Class XII pass rates

This guide demonstrates ChartProof with verifiable published data and a separately labeled controlled transcription-error test. The charts are redrawn from CBSE statistics for OCR, not copied from CBSE reports.

## Verified published values

| Year | Overall pass percentage (full subjects) |
| --- | ---: |
| 2024 | 87.98% |
| 2025 | 88.39% |
| 2026 | 85.20% |

- [Official CBSE 2025 Class XII release](https://www.cbse.gov.in/cbsenew/documents/PressRelease2025_ClassXII.pdf): 2024 and 2025.
- [Official CBSE 2026 Class XII release](https://www.cbse.gov.in/cbsenew/documents/PRESS_RELAESE_CLASS_XII_2026_MAIN_13052026.pdf): 2025 and 2026.

The [machine-readable CSV](../data/cbse_class_xii_pass_rates.csv) records the source URL for each row. The CSV and generator are included in this repository.

## Generate OCR-friendly charts

From the repository root with Python and the project dependencies installed:

```bash
python tools/real_data_demo.py
```

This creates five PNGs under `samples/real-data/`. Two represent successive views of **real data**, one is a cosmetic rearrangement, and one is an **intentionally incorrect report chart** for controlled correction testing. Check the red disclaimer on that image before showing it to anyone.

## Demo A — all values are genuine

1. Open the [live workspace](https://chartproof-mu.vercel.app/) and initialize the two chart panels with **Load example** if needed.
2. **Review / replace** the Original using `01_official_prior_chart.png`: 2024 = 87.98%, 2025 = 88.39%.
3. **Review / replace** the Revised chart using `02_official_updated_chart.png`: 2024 = 87.98%, 2025 = 88.39%, 2026 = 85.20%.
4. Keep **Local OCR**, confirm the exact metric `CBSE pass rate` and all percentages against the source, tick review confirmation, and save each chart.
5. Remove any old sample claims, add the following sentences individually, and choose **Run checks**:

   - `CBSE pass rate rose by at least 0.4 percentage points from 2024 to 2025.` — **Supported** before and after; **Verdict retained**. The recorded 2024-to-2025 change is +0.41 percentage points.
   - `CBSE pass rate fell by at least 3 percentage points from 2025 to 2026.` — **Insufficient evidence** before and **Supported** after; **Verdict changed**. The new evidence shows a −3.19-point change.

**Interpretation:** adding 2026 observations is not a change to the already published values for 2024 and 2025. The tool should retain an older correct claim while making a new comparison answerable.

## Demo B — simulated erroneous report corrected using real data

To demonstrate the **Outdated claim** transition, this **controlled** example intentionally invents a bad transcription in the original report. It is not a real CBSE correction:

1. Set Original to `03_intentional_reporting_error.png`. It intentionally says 2026 = **88.90%** (WRONG; not official), alongside the correct 2025 = 88.39%.
2. Set Revised to `04_official_corrected_chart.png`. It shows **85.20% for 2026**, the real published figure.
3. Add `CBSE pass rate rose by at least 0.5 percentage points from 2025 to 2026.`
4. Run checks. The erroneous chart produces +0.51 percentage points (**Supported**). The real data produce −3.19 percentage points (**Contradicted**). ChartProof should mark the claim **Outdated claim**.
5. Inspect the revision-impact trace and export the JSON audit.

The takeaway is that ChartProof catches prose invalidated by a corrected **report figure**. It does not allege that CBSE published the mistaken figure.

## Demo C — visual changes, unchanged numerical data

Set Original to `02_official_updated_chart.png` and Revised to `05_cosmetic_redesign.png`. The colors/order change but the numerical year/value mappings remain the same. The 2024-to-2025 claim stays **Supported**, with no numerical revision-impact rows. Different image digests do not necessarily mean changed statistics.

## What to say in a project evaluation

- **Problem:** report writers may retain statements after updating charts.
- **Pipeline:** extract OCR values → verify against source → classify the claim → compute the comparison → replay it on both chart versions.
- **Explainability:** formulas, exact year/value changes, source-file digests and evidence provenance accompany the verdict.
- **Responsible behavior:** an absent year produces **Insufficient evidence**; the intentionally erroneous first chart is clearly identified as a simulation.
- **Limitations:** the automatic parser is narrow: English, single-series percentage bar charts, four-digit years and printed values. It is not a general visual question-answering system, and optional Azure models are not required for this local demo.

For the source press-release PDFs themselves, ChartProof is more reliable when you use the generated **single-figure** redraws; the original releases contain multiple tables and prose. Check every OCR row rather than trusting a perfect parse.

