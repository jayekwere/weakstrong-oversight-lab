# Reproduction and local operation
Install Python 3.12+ and [uv](https://docs.astral.sh/uv/). Clone the repository and run:

```sh
uv sync --frozen --extra dev
uv run weakstrong-oversight-lab dataset --output runs/dataset.json
uv run weakstrong-oversight-lab run --config configs/demo.json --output runs/experiment.json
uv run python scripts/reproduce.py
uv run weakstrong-oversight-lab serve --port 8080
```

Open [the dashboard](http://127.0.0.1:8080). The wheel includes an actual saved demonstration, so no API key is needed. New dashboard runs are retained in memory (maximum four); export JSON to preserve full traces and provenance, or CSV for scalar observations. The CLI saves JSON atomically. Reproduction compares exact row observations excluding wall-clock latency. OS/Python differences affect timing; timing is not a portable performance benchmark.

`Experiment` validates `seed`, `trials` (1–10), `split`, `context_limit` (8–1024 events), `evidence_mode` and `threshold`. Project-specific controls are documented in methodology; irrelevant controls are hidden in the UI. `dataset` validates every case and emits labels for researcher inspection. Evaluators construct observations without labels. `serve` binds 127.0.0.1 and accepts ports 1024–65535.

## Optional model interfaces
`--provider-config configs/provider.local.json` selects an OpenAI-compatible loopback service. Set the exact installed model identifier and `enabled: true`. Local service installation and model weights are the researcher's responsibility. Cloud adapters support OpenAI-compatible chat completions at the official OpenAI endpoint and Claude-compatible Messages tool output at the official Anthropic endpoint. Set an exact model ID, explicit nonzero spending cap and a conservative upper tariff; export the corresponding API key in your shell. Configurations ship disabled with a zero spending cap. Never put keys in files. No paid API call was used for the published simulation.

The supported response contract is JSON schema output (or forced `decision` tool use for Messages). The adapter constrains request count, token reservation, spending estimate, retries (0–2), a shared timeout (<=30 seconds) and response size (256 KiB). This is protocol support verified with mock HTTP transports; untested provider/model combinations can reject schema features or context sizes. Such failures are recorded as errors rather than a successful evaluation.

## API
`GET /api/health`, `GET /api/scenarios`, `GET /api/runs`, `GET /api/runs/{id}`, `POST /api/runs`, `GET /api/runs/{id}/export?format=json|csv`. See `/openapi.json` for exact schemas. POST only runs deterministic simulations. An optional LAB_API_TOKEN requires `Authorization: Bearer ...` for writes. Do not expose this single-user API directly to a public network.

## Verification
Run the commands in [CONTRIBUTING](../CONTRIBUTING.md). `requirements.lock` contains hashed runtime dependencies; `uv.lock` locks the entire development graph. CI tests Python 3.12 and 3.14, builds a wheel, audits dependencies, scans source/content, reproduces saved observations and builds/runs the non-root container without networking.

```sh
docker build -t weakstrong-oversight-lab:local .
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 64 --memory 512m \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m weakstrong-oversight-lab:local \
  run --output /tmp/experiment.json
```

## Independent supervisor configurations and manual review
Use `run --model-map path/to/map.json` to map any of `lens-1`, `lens-2`, `lens-4`, `reference-8` to full ProviderConfig objects. Unspecified profiles remain clearly named synthetic fixtures. `--provider-config` instead replaces lens-1 only; these options are mutually exclusive. Configuration identifiers are labels, not capability claims. Calibration consumes the same provider request/token/spend budget as evaluation, so allocate it explicitly and inspect errors. No external profile is enabled by shipped configurations.

`GET /api/runs/{id}/reviews` returns the first-trial selective queue and supplied decisions; `POST` with a ManualReview validates membership before saving. Review decisions can be edited and exported, and disappear on server restart or run eviction unless exported. The CLI reads either an exported review object or a list of supplied ManualReview records through `review --decisions`. No labels are included in queue entries. The public dataset and full observation inspector remain visible for research, so this is not a blinded study interface.
