# Changelog

All notable changes to ProtocolSmith will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-17

### Added

- A controlled laboratory containing intentionally incompatible Orders API v1
  and v2 contracts.
- Differential black-box evidence capture across success, collection-size, and
  missing-customer cases.
- Meta Muse Spark 1.3 structured reasoning for compatibility hypotheses,
  constrained adapter compilation, and active experiment design.
- A six-case causal-control experiment for the `page_size` to `limit` request
  parameter mapping.
- An allowlisted declarative adapter specification and deterministic bridge
  runtime.
- A machine-readable verification receipt containing 15 passing controlled
  contract checks and an explicit information-loss warning.
- An interactive local dashboard and a one-command demo launcher.
- A serverless GitHub Pages showcase that honestly replays the committed
  verification receipt without presenting it as a live backend.
- Reliable launcher handling for existing ProtocolSmith services, occupied
  default ports, headless environments, and browser-open failures.
- Unit, integration, and live HTTP end-to-end tests in GitHub Actions.
- Security guidance, a reviewer demo guide, a controlled-benchmark evidence
  note, and draft v0.1.0 release material.

### Security

- Remote targets are denied unless explicitly enabled.
- Redirects are disabled, HTTP requests have timeouts, and response size is
  bounded.
- Model output is validated as typed data and is never executed as generated
  Python source.

### Known limitations

- The current evaluation covers one synthetic Orders domain and one known
  endpoint family.
- Only the request-parameter rename is tested with the six-case causal-control
  matrix; the other rules are supported by paired observations and
  deterministic replay, not independent causal probes.
- The modern API removes time-of-day information. The bridge reconstructs
  midnight UTC and discloses the loss rather than claiming exact equivalence.
- Non-null pagination tokens, non-USD currencies, additional status values,
  authentication, and arbitrary production API surfaces are outside the
  current benchmark.

[Unreleased]: https://github.com/mkhan48-debug/protocolsmith-meta-hackathon/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mkhan48-debug/protocolsmith-meta-hackathon/releases/tag/v0.1.0
