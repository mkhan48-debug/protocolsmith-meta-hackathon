# ProtocolSmith v0.1.0 release notes

ProtocolSmith v0.1.0 is a controlled, local-first demonstration of
evidence-driven API compatibility repair. It compares intentionally
incompatible legacy and modern Orders APIs, uses Meta Muse Spark 1.3 to reason
over structured observations and design an experiment, compiles the supported
findings into an allowlisted specification, and deterministically replays the
legacy contract through a bridge.

## Highlights

- Three paired black-box discovery experiments across success, collection, and
  error behavior
- One Muse-designed six-case causal-control experiment for the
  `page_size` ↔ `limit` mapping
- A declarative adapter with a small, reviewable operation allowlist
- A deterministic bridge that never executes model-generated source code
- A recorded 15/15 verification receipt with adapter identity and known-loss
  disclosure
- A live local dashboard showing v1 success, direct v2 incompatibility, and
  restored success through the bridge
- A public, serverless recorded-evidence showcase for inspection without local
  setup, explicitly distinguished from the live FastAPI proof
- A one-command launcher, automated tests, and GitHub Actions CI

## Evidence, not just a demo

The repository commits four machine-readable artifacts:

- `artifacts/discovery_report.json`
- `artifacts/active_probe_trace.json`
- `artifacts/adapter_spec.json`
- `artifacts/verification_receipt.json`

Together they preserve the path from observed behavior to model-assisted
hypothesis, constrained executable plan, and deterministic verification. See
[CONTROLLED_BENCHMARK.md](CONTROLLED_BENCHMARK.md) for the claim boundary and
unresolved risks.

## Run locally

Browse the recorded-evidence showcase at
https://mkhan48-debug.github.io/protocolsmith-meta-hackathon/. It replays the
committed receipt and does not run a hosted backend.

Run the real HTTP proof locally:

```bash
git clone https://github.com/mkhan48-debug/protocolsmith-meta-hackathon.git
cd protocolsmith-meta-hackathon
uv sync --locked --all-groups
uv run protocolsmith
```

Open the dashboard URL printed in the terminal and select **Run live
compatibility proof**. Replaying committed artifacts does not require a Meta
API key.

This release is intended to run from the Git source checkout. Its
current wheel/sdist omits root-level templates and evidence artifacts and is
not a supported standalone PyPI distribution.

## Important limitations

This release evaluates one synthetic Orders domain, one known route,
a bounded parameter vocabulary, and a small operation allowlist. Only the
parameter rename receives the six-case causal probe. Non-null pagination,
non-USD currencies, additional error and status values, real authentication,
production data, hostile upstreams, and scale are outside the current
evaluation.

The modern fixture discards time of day. The bridge reconstructs midnight UTC
and emits an explicit warning; it does not claim exact timestamp equivalence.

## Safety posture

Remote targets are blocked unless explicitly enabled. Requests use timeouts,
redirects are disabled, response size is bounded, required fields are
validated, unsupported currency fails closed, and model output is constrained
to typed data. These controls are prototype safeguards, not a production
security guarantee. See [SECURITY.md](../SECURITY.md).
