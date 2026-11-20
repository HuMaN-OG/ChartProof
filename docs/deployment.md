# Deploy ChartProof

## Live Vercel deployment

The production service runs the root Dockerfile using Vercel's Container framework preset. Tesseract and the PDF runtime are installed inside the container. A public browser check uploaded the corrected PDF, confirmed the extracted values and returned the calculation 68% − 60% = 8 percentage points. The browser accepts up to 3 MiB so its base64 JSON upload fits the function request limit. [Live workspace](https://chartproof-mu.vercel.app/) · [Vercel Container Runtime](https://vercel.com/docs/functions/runtimes/container)

To deploy this repository to another Vercel project, import `HuMaN-OG/ChartProof`, select `main`, use the repository root and choose the **Container** preset. The application listens on the platform-supplied port. The source download serves a bundled ZIP when available. For Git deployments it links to a GitHub archive for the deployment commit when its SHA is available, or to the current main branch.

## Get the source

```sh
git clone https://github.com/HuMaN-OG/ChartProof.git
cd ChartProof
```

The public project includes its benchmark, CI workflow, deployment files and a [technical report](technical-report.md).

## Render

Use the repository root as the Docker build context. The included Render Blueprint declares one free Docker web service and the health endpoint `/healthz`. In Render, create a Blueprint from the repository and select the branch containing this project. If the service name is in use, choose an available service name. Alternatively, create a Docker web service directly with the same root and health endpoint. The server binds to 0.0.0.0 and uses the host's PORT. A free service may take time to start after inactivity.

The local OCR path uses no Azure resources. The initial sample images are included in the image. A restart clears only the server's sample extraction cache. Client workspaces survive a restart in their own browsers. Export audits before clearing browser data. The app is designed for individual workspaces. Shared organizational accounts and a central audit database are outside this release.

Check the host's `/healthz`, open the homepage, load the corrected sample and upload `samples/corrected.pdf`. Verify the year/value pairs, confirm the source, then export and reopen the audit. A health response alone does not exercise extraction.

## Docker locally or on a container service

```sh
docker build -t chartproof .
docker run --rm -p 8000:8000 chartproof
```

The runtime image includes Tesseract English data, PDFium through the Python wheel, and DejaVu fonts. It runs as a non-root user. The repository's CI workflow tests the Python package, builds the container, starts the packaged service and exercises the sample endpoint.

## Connect Microsoft Foundry

Use an existing Microsoft Foundry resource where Content Understanding is supported. Configure the default completion and embedding deployments required for the prebuilt analyzer in the resource. Confirm that your administrator permits key authentication and your account has access to the resource and its deployments. Separately deploy a vision-capable model that accepts image inputs through the Azure OpenAI v1 chat completions API. Copy its deployment name. The app uses server-side resource keys.

| Environment variable | Value |
| --- | --- |
| AZURE_CU_ENDPOINT | Content Understanding resource root, e.g. https://RESOURCE.cognitiveservices.azure.com |
| AZURE_CU_KEY | Resource API key for Content Understanding |
| AZURE_OPENAI_ENDPOINT | Azure OpenAI / Foundry resource root, e.g. https://RESOURCE.openai.azure.com |
| AZURE_OPENAI_API_KEY | Matching Azure OpenAI resource API key |
| AZURE_VISION_DEPLOYMENT | Exact configured deployment name of a vision-capable model |
| CHARTPROOF_CLOUD_TOKEN | A separate access token chosen for authorized ChartProof reviewers |

Configure the variables in the service environment and redeploy. To use Docker locally, copy `.env.example` to `.env`, set the values there, and start the container with `docker run --rm --env-file .env -p 8000:8000 chartproof`. For a native Python session, export the variables in the shell. The application never loads a .env file automatically. Keep server keys out of browser inputs. Only the separate ChartProof token goes into the web interface.

Azure extraction sends the selected page as PNG bytes. It checks the operation status, reads one Chart.js bar series and asks the reviewer to confirm its scale. The optional direct vision comparison sends the two displayed preview images and the claim. A configured service shows the appropriate control in the UI. Configuration status checks variable presence. A successful live analysis verifies the deployment.

With both connections configured, run the two-call smoke test. It sends a sample image to each service, prints the readings and verdicts, and exits nonzero if either disagrees with the reference.

```sh
python tools/cloud_smoke.py
```

The optional full live benchmark makes 180 vision requests and incurs the resource's usual charges. Run it only when you intend to use that quota. It records revision verdicts alongside the same held-out cases as the local method.

```sh
python tools/benchmark.py --azure --out evaluation/foundry-results.json
```

## Operational checks

- A response of 403 on a cloud operation means the application access token is missing or mismatched.
- A 503 or polling timeout indicates an unconfigured service, missing deployment or permissions, invalid provider response, throttling, or a request that took too long. Verify the live smoke test and Azure resource configuration.
- An empty OCR table is reviewable. Use a clearer crop with printed percentage labels or transcribe the verified rows in the figure review dialog.
- The service accepts up to 6 MiB of file data and up to 18 million pixels per uploaded image. The selected PDF page is rasterized within a fixed pixel bound. A three-job per-process concurrency limit bounds simultaneous extraction/vision tasks.

[Microsoft Content Understanding quickstart](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/quickstart/use-rest-api) · [Content Understanding prebuilt analyzers](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/prebuilt-analyzers) · [Azure OpenAI vision input](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/gpt-with-vision) · [Render Blueprint specification](https://render.com/docs/blueprint-spec)
