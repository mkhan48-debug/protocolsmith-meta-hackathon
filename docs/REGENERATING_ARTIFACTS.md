# Regenerating model-assisted artifacts

The normal demo replays the committed artifacts and requires no Meta API key.
Use this procedure only when intentionally producing a new Muse-assisted run.

Regeneration can change compatibility hypotheses, confidence values, the
compiled adapter, and verification evidence. Review the resulting diff as new
experimental output; do not overwrite committed evidence casually.

## 1. Install and configure

```bash
uv sync --locked --all-groups
cp .env.example .env
```

Set `MODEL_API_KEY` in the local `.env` file. The file is ignored by Git. Then
check access:

```bash
uv run python scripts/check_meta_api.py
```

Never put the real key in a command, screenshot, issue, artifact, or commit.

## 2. Start only the controlled laboratory

In terminal A:

```bash
uv run uvicorn protocolsmith_meta_hackathon.lab_api:app \
  --host 127.0.0.1 \
  --port 8000
```

Confirm `http://127.0.0.1:8000/health` reports
`protocolsmith-lab`.

## 3. Generate discovery, specification, and active evidence

In terminal B, from the repository root:

```bash
uv run python scripts/run_discovery.py
uv run python scripts/compile_adapter.py
uv run python scripts/run_active_probe.py
```

The scripts update, in order:

- `artifacts/discovery_report.json`
- `artifacts/adapter_spec.json`
- `artifacts/active_probe_trace.json`

The first and third scripts make local requests to the controlled laboratory
and model requests to the Meta Model API. The compiler reads the discovery
report and also uses the model. The bridge never executes source code returned
by the model; it loads the constrained JSON specification.

## 4. Restart with the new specification

Stop the laboratory in terminal A with `Control+C`. Also stop any earlier
ProtocolSmith demo that you started. Then launch the complete stack:

```bash
uv run protocolsmith
```

Restarting matters because the bridge loads the adapter artifact when its
process starts. Use the dashboard URL printed by the launcher.

## 5. Generate a fresh deterministic receipt

With the complete stack running on the default ports, use terminal B:

```bash
uv run python scripts/verify_bridge.py
```

If the launcher selected alternate ports, set the verification URLs to the
printed ports. For example, after replacing `8010` and `8011` with the actual
laboratory and dashboard ports:

```bash
PROTOCOLSMITH_LEGACY_BASE_URL=http://127.0.0.1:8010/v1 \
PROTOCOLSMITH_MODERN_BASE_URL=http://127.0.0.1:8010/v2 \
PROTOCOLSMITH_BRIDGE_BASE_URL=http://127.0.0.1:8011 \
uv run python scripts/verify_bridge.py
```

Do not assume that a receipt targeting stale or different processes validates
the new adapter.

## 6. Review before committing

```bash
jq empty artifacts/*.json
jq '.summary, .known_loss' artifacts/verification_receipt.json
jq '.execution.checks, .final_verdict' artifacts/active_probe_trace.json
git diff -- artifacts/
uv run pytest -q
```

Verify at minimum:

- The artifacts contain only synthetic inputs and expected local URLs.
- Generation timestamps and model identifiers are present.
- The active experiment includes all required controls.
- Every adapter operation is implemented and allowlisted.
- The verification receipt was generated against the new adapter.
- Uncertainty, unsupported cases, and information loss remain disclosed.
- No credential, private endpoint, or personal data appears in the diff.

If a regenerated result fails or changes the claim boundary, keep the failure
for investigation rather than editing JSON by hand to make it pass.
