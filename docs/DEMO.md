# Reviewer demo guide

This guide runs the ProtocolSmith controlled proof in a few minutes. The replay
is local, uses synthetic data, and does not require a Meta API key.

## Start the demo

Requirements:

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)

From the repository root:

```bash
uv sync --locked --all-groups
uv run protocolsmith
```

Use the dashboard URL printed in the terminal. The launcher attempts to open it
in the default browser, but the printed URL is authoritative if no browser
window appears.

Press `Control+C` in the launcher terminal to stop services started by that
launcher.

## Suggested two-minute walkthrough

1. **Set the boundary.** Point to the **Controlled benchmark** banner. Explain
   that this is one synthetic Orders API migration, not a universal migration
   claim.
2. **Show the evidence chain.** The dashboard loads three paired black-box
   experiments, the compatibility map, and the committed verification receipt.
3. **Show the active test.** The six-case table contains baselines, correct
   names, and swapped-name negative controls. It specifically supports
   `page_size` ↔ `limit`.
4. **Inspect the executable plan.** Select **Inspect generated
   specification**. The JSON contains data rules—not arbitrary generated
   Python.
5. **Run the proof.** Select **Run live compatibility proof**. Expected visible
   sequence:
   - Legacy API v1: pass
   - Modern API v2 direct: expected incompatibility
   - ProtocolSmith bridge: pass
6. **End on honesty.** Show the 15/15 recorded receipt and the explicit
   `created_at` loss: only the calendar date can be preserved because v2
   discarded the original time.

The live button issues five local requests across those three visible paths. It
uses the previously generated and validated specification and does not call
Muse during the click.

## Command-line proof

Keep the launcher running, then use another terminal.

The unchanged client succeeds against v1:

```bash
uv run python scripts/legacy_client.py \
  --base-url http://127.0.0.1:8000/v1
```

The same client fails its contract when pointed directly at v2:

```bash
uv run python scripts/legacy_client.py \
  --base-url http://127.0.0.1:8000/v2
```

The same client succeeds through the bridge:

```bash
uv run python scripts/legacy_client.py \
  --base-url http://127.0.0.1:8001
```

These fixed URLs apply when the launcher is using its default ports. If the
launcher prints different ports, use the printed service URLs instead.

## Manual start

If you prefer separate terminals, start the laboratory first:

```bash
uv run uvicorn protocolsmith_meta_hackathon.lab_api:app \
  --host 127.0.0.1 \
  --port 8000
```

Then start the dashboard and bridge:

```bash
uv run uvicorn protocolsmith_meta_hackathon.dashboard_api:app \
  --host 127.0.0.1 \
  --port 8001
```

Open `http://127.0.0.1:8001`.

## Troubleshooting

### `uv` is not installed

Install it using the official `uv` installation instructions linked above,
then rerun `uv sync --locked --all-groups`.

### The browser does not open

Copy the dashboard URL printed by the launcher into a browser. Browser
auto-opening is a convenience; it is not a readiness check.

### The page opens but the live proof is unavailable

Confirm both local services are healthy. With the default ports:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8001/health
```

Restart the launcher if either command fails. If you started services
manually, confirm that the laboratory was started before the dashboard.

### Port 8000 or 8001 is already in use

The one-command launcher reports the URL it actually selected. If you are
using the manual commands, inspect listeners before choosing different ports:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:8001 -sTCP:LISTEN
```

Do not terminate an unfamiliar process. Either stop a ProtocolSmith instance
you started previously or use the one-command launcher and follow its printed
URL.

### The recorded receipt and live checks have different totals

This is expected. The saved receipt contains 15 checks across one-order,
two-order, and error scenarios. The dashboard button performs a compact live
replay and evaluates its own checks. See
[CONTROLLED_BENCHMARK.md](CONTROLLED_BENCHMARK.md) for the exact boundary.

### The Meta API key is missing

No key is needed for the launcher, dashboard, bridge, tests, or replay of the
committed artifacts. A key is required only to regenerate Muse-assisted
discovery, compilation, or active-probe artifacts.
