# Security policy

ProtocolSmith is an experimental, local-first hackathon prototype. It is not a
production security boundary, a general-purpose proxy, or authorization to
probe third-party systems.

## Supported versions

There is not yet a tagged stable release. Security fixes are applied to the
latest revision on `main`. Older commits and locally modified copies are not
supported.

## Reporting a vulnerability

Please report potential vulnerabilities privately through the repository's
**Security** tab using GitHub private vulnerability reporting, if it is
available. If private reporting is unavailable, contact the maintainer through
the GitHub profile linked from the repository. Do not place credentials,
private API responses, exploit details, or personal data in a public issue.

Include, when possible:

- The affected commit and component
- The conditions required to reproduce the issue
- A minimal proof of concept using synthetic data
- The potential impact
- Any suggested mitigation

There is currently no guaranteed response-time or disclosure-time service
level. Please allow the maintainer time to confirm the report and coordinate a
fix before publishing details.

Ordinary bugs that do not expose sensitive information can be filed as public
GitHub issues.

## Safe operation

- Use the bundled synthetic laboratory for demonstrations and development.
- Probe only systems you own or have explicit permission to test.
- Leave remote probing disabled unless a trusted target is deliberately in
  scope. Setting `PROTOCOLSMITH_ALLOW_REMOTE=1` removes a local-target guard; it
  does not add authentication, authorization, or safety policy.
- Keep `MODEL_API_KEY` in the ignored local `.env` file. Never paste a real key
  into issues, logs, screenshots, artifacts, or commits.
- Inspect generated artifacts before use. Model output is untrusted input even
  though ProtocolSmith validates it against typed schemas and an operation
  allowlist.
- Do not send secrets, personal data, or regulated production traffic through
  this prototype.

## Current security boundaries

The bridge currently provides several defensive controls: local targets by
default, scheme validation, disabled redirects, request timeouts, a maximum
response size, required-path validation, supported-currency validation, and an
allowlisted transformation runtime. It does not yet provide production-grade
credential isolation, tenant separation, PII redaction, rate-limit policy,
network sandboxing, audit-log integrity, artifact signing, or adversarial-model
output hardening.

See [docs/CONTROLLED_BENCHMARK.md](docs/CONTROLLED_BENCHMARK.md) for the exact
evaluation boundary.
