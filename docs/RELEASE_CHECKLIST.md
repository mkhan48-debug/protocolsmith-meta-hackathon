# v0.1.0 release checklist

Use this checklist on the exact commit that will be tagged. A checked box should
mean the command or review was completed on that commit—not on an earlier
working tree.

## Scope and claims

- [ ] README describes the project as a controlled prototype, not a universal
      or production-ready migration system.
- [ ] The 15/15 claim is explicitly tied to the committed synthetic benchmark
      receipt.
- [ ] The six-case causal claim is limited to the `page_size` ↔ `limit`
      parameter mapping.
- [ ] Known timestamp loss and unresolved pagination, currency, status, error,
      authentication, and scale gaps are visible.
- [ ] Hackathon declaration, third-party dependencies, and synthetic-data
      provenance remain accurate.

## Reproducibility gates

- [ ] `uv sync --locked --all-groups`
- [ ] `uv run python -m compileall -q src scripts tests`
- [ ] `uv run pytest -q`
- [ ] `uv run python scripts/build_static_showcase.py`
- [ ] Generated `docs/index.html`, evidence, and assets match a clean rebuild.
- [ ] `uv run protocolsmith` starts cleanly from a fresh shell.
- [ ] The printed dashboard URL loads without a Meta API key.
- [ ] The live proof shows v1 pass, expected direct-v2 incompatibility, and
      bridge pass.
- [ ] `curl --fail <lab-url>/health` succeeds.
- [ ] `curl --fail <dashboard-url>/health` succeeds.
- [ ] `curl --fail <dashboard-url>/api/live-proof` returns a passed result.
- [ ] `Control+C` stops only services started by the launcher.

## Artifact review

- [ ] All four JSON artifacts parse successfully with `jq`.
- [ ] Model identifiers and generation timestamps are present.
- [ ] The adapter specification references the reviewed discovery report.
- [ ] The active trace contains exactly six cases and all controlled expected
      counts match.
- [ ] The verification receipt records 15 total, 15 passed, and 0 failed.
- [ ] The receipt discloses midnight-UTC reconstruction for `created_at`.
- [ ] No artifact contains a real credential, private endpoint, personal data,
      or unrelated local path.
- [ ] If artifacts were regenerated, the diff was reviewed as a new
      model-assisted result rather than accepted automatically.

## Repository hygiene

- [ ] `git status --short` is clean.
- [ ] No `.env`, API key, token, editor file, cache, or build output is tracked.
- [ ] CI passes on the release commit.
- [ ] README links and relative documentation links resolve.
- [ ] Version in `pyproject.toml` is `0.1.0`.
- [ ] License and security policy are present.
- [ ] Contribution guidance is present and links to the evidence and security
      boundaries.
- [ ] Roadmap items are clearly labeled as future work rather than shipped
      capability.
- [ ] Draft markers, placeholder URLs, and submission-only instructions have
      been removed from public release copy where appropriate.

## Distribution boundary

The first release is scoped to a GitHub source checkout. `uv build` can produce
a wheel and sdist, but the current archives omit the root-level dashboard
template and committed evidence artifacts required by the demo. Do not upload
those archives to PyPI as a functioning standalone distribution.

- [ ] GitHub release copy directs users to clone or download the repository.
- [ ] No wheel or sdist is attached or uploaded as a supported runtime.
- [ ] If standalone packaging is added later, templates and default artifacts
      are moved into package data and the installed `protocolsmith` console
      script is tested outside the repository.

## GitHub release

- [ ] Commit the release-ready changes.
- [ ] Create an annotated `v0.1.0` tag on the verified commit.
- [ ] Publish a GitHub release using `docs/RELEASE_NOTES_v0.1.0.md`.
- [ ] Replace the changelog's Unreleased entry with a dated `0.1.0` entry and
      update comparison links.
- [ ] Confirm the GitHub-generated source archive installs and runs using the
      documented commands.

## Reviewer assets

- [ ] Record a short uncut demo showing the terminal command, printed URL,
      controlled-scope banner, six-case experiment, live proof, receipt, and
      known loss.
- [ ] Add the final shareable video URL to `SUBMISSION.md`.
- [ ] Capture a screenshot that visibly includes the controlled-benchmark
      label and 15/15 recorded receipt.
- [ ] Keep public descriptions aligned with the evidence boundary in
      `docs/CONTROLLED_BENCHMARK.md`.
