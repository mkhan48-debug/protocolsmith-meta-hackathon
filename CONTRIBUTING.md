# Contributing to ProtocolSmith

Thank you for helping make ProtocolSmith more rigorous, reproducible, and safe.
The most useful contributions expand evidence or reduce uncertainty without
overstating what the prototype can do.

## Development setup

```bash
git clone https://github.com/mkhan48-debug/protocolsmith-meta-hackathon.git
cd protocolsmith-meta-hackathon
uv sync --locked --all-groups
uv run pytest -q
```

Run the local demonstration with `uv run protocolsmith`. Replaying committed
artifacts uses synthetic services and does not require a Meta API key.

## Before opening a change

- Keep the default workflow local and synthetic.
- Probe only systems you own or have explicit permission to test.
- Do not add credentials, personal data, private endpoints, or production
  responses to fixtures, logs, screenshots, issues, or commits.
- Preserve the separation between model reasoning and deterministic execution.
- Prefer explicit rejection or uncertainty over an unsupported compatibility
  guess.
- Keep public claims scoped to the evidence in
  [`docs/CONTROLLED_BENCHMARK.md`](docs/CONTROLLED_BENCHMARK.md).

For vulnerability reports, follow [SECURITY.md](SECURITY.md) instead of opening
a public issue.

## Tests

Run the same core checks used for release review:

```bash
uv run python -m compileall -q src scripts tests
uv run pytest -q
```

Changes to launcher behavior should include isolated launcher tests. Changes to
adapter behavior should include fail-closed cases as well as successful cases.
Changes to the proof path should preserve a real local HTTP-stack test.

## Evidence and artifact changes

The JSON files in `artifacts/` are experimental evidence, not ordinary sample
configuration. If a change regenerates them:

1. Follow [`docs/REGENERATING_ARTIFACTS.md`](docs/REGENERATING_ARTIFACTS.md).
2. Review every artifact diff.
3. Confirm timestamps, model identifiers, controls, receipt totals, and known
   losses.
4. Explain in the pull request why the new run should replace the previous
   evidence.
5. Never hand-edit a model-assisted artifact to manufacture a passing result.

## Pull requests

A focused pull request should include:

- The problem and intended evidence boundary
- The implementation or documentation change
- Tests or reproduction commands
- Any new uncertainty, risk, or unsupported behavior
- Screenshots only when they contain no secrets or private data

Do not combine unrelated cleanup with a behavioral change. If the public demo
or claim boundary changes, update the README, controlled-benchmark note, and
release material in the same pull request.
