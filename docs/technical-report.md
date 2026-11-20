# ChartProof technical report

## Objective and contribution

A corrected chart can invalidate the prose around it. ChartProof binds a sentence to one metric, one or two years, an operation, a direction and a threshold. The original and revised figures use the same binding. Each result includes the values and calculation. The author can inspect the sources, revise a sentence, save the audit and reopen it after the server restarts.

ChartCheck established a benchmark for fact-checking statements about individual real-world charts. ChartProof builds a revision-review workflow and tests whether it reacts differently to corrected values, cosmetic redesign and missing evidence. This is a project contribution. The study does not establish a first-in-literature claim. [Akhtar et al., ACL Findings 2024](https://aclanthology.org/2024.findings-acl.828/)

## Implementation

Tesseract reads the local image or selected PDF page. The local extractor associates printed year and percentage tokens along the category axis, proposes a metric and retains normalized bounding boxes. Azure Content Understanding offers a second extraction path through the prebuilt document-search analyzer. Uploaded figures always receive a human source check. Image previews, the source file digest, page, raw readings, and edited readings are retained in the browser audit.

A multinomial logistic regression using word and bigram TF-IDF features was fitted to 72 authored training sentences, 18 per class. Constrained English parsing checks the units, metric name, direction and threshold before issuing any verdict. Unsupported phrasing can be linked to a calculation by a reviewer. The audit records that provenance. A separate Azure vision-model comparison returns a direct chart verdict.

Decimal arithmetic evaluates printed percentages. Point change is the difference between the later and earlier rates. Relative change divides that difference by the original rate and multiplies by 100. The comparisons require the named years and metric. An original supported claim that becomes contradicted is marked outdated.

## Results

The pixel benchmark uses 12 held-out chart families with four figures each. Each family has five controlled claim patterns and three revisions, giving 180 revision decisions. Evaluation images are generated from known data; evaluation does not depend on production OCR corrections. Language training and the benchmark use separate sentence records.

| Measurement | Observed |
| --- | --- |
| Expected year/value pairs recovered by local OCR | 84/84, with zero extra year keys |
| Outdated claims detected | 36/36 |
| Unnecessary alerts on still-supported claims after cosmetic changes | 0/48 |
| Previously supported claims made unverifiable by removing a year | 24/24 recognized |
| Answerable revision cases receiving a definite verdict | 120/120 |
| All revision verdicts, including correctly unknown cases | 180/180 |
| Baseline that carries the original verdict forward | 120/180 |
| Operation-classifier accuracy on 24 separate authored phrases | 23/24 |
| Untouched external ChartCheck T2 claims accepted by the automatic sentence parser | 1/981 across 151 charts |

Five repeated claim patterns and one renderer limit the controlled benchmark's external validity. The language model misclassified a sentence describing a 1.3-point change as unsupported. An external ChartCheck admission is only a successful syntactic interpretation; it does not establish agreement with the chart. The reviewer-binding route is useful for actual report prose. The 981 external claims were not converted into a fabricated verification accuracy.

Two extra probes used a chart redrawn from CBSE Class XII overall pass percentages. The local engine recovered 87.33%, 87.98% and 88.39% for 2023, 2024 and 2025, respectively, and supported a 0.41-point increase from 2024 to 2025. After reducing the chart to 172 × 98 pixels and blurring it, OCR recovered zero year/value pairs and the verifier returned insufficient evidence. The original CBSE releases present the data in tables. [CBSE 2024 release](https://www.cbse.gov.in/cbsenew/documents/PRESS_NOTE_DECLARATION_CLASS_XII_RESULT_2024_21052024.pdf) · [CBSE 2025 release](https://www.cbse.gov.in/cbsenew/documents/PressRelease2025_ClassXII.pdf)

## Reproducibility

Local unit/API tests exercise OCR on actual PNG and PDF bytes, input limits, claim semantics, saved reviewer bindings, cloud request/response contracts and error handling. An HTML/JavaScript DOM integration check against the running ASGI service exercised sample switching, PDF upload, source confirmation, claim entry, persistence, restore, benchmark display and reviewer bindings. The release workflow also supplies a real Chromium smoke test and container build for a standard CI runner.

The evaluated machine used Python 3.12, scikit-learn 1.8 for fitting, Pillow 13 and PDFium 5.13 via pypdfium2. Run the commands in the README. To repeat the external audit, obtain the authors' unmodified test_two.csv and run:

```sh
python tools/scope_audit.py test_two.csv --out evaluation/external-scope.json
```

[ChartCheck T2 source](https://github.com/mubasharaak/chartfc_dataset_wikicommons/blob/main/data/dataset/test_two.csv) · [Full case outcomes](../evaluation/results.json) · [External audit and CSV digest](../evaluation/external-scope.json)

## Deployment and validation boundary

The local web and CLI ran with real OCR. Vercel built and deployed the container. On the public site, a browser opened the example, checked the missing-year result, uploaded the corrected PDF and confirmed values of 55%, 60% and 68%. Saving the reviewed figure changed the ten-point claim to outdated and showed an eight-point increase. Azure HTTP adapters passed offline contract tests. The recorded evaluation contains zero live Azure requests because no Foundry resource was configured. The two-call smoke script can verify a future connection. The benchmark covers reviewed single-series percentage charts under the stated conditions. [Live workspace](https://chartproof-mu.vercel.app/) · [Deployment guide](deployment.md)
