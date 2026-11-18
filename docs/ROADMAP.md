# Research and product roadmap

ProtocolSmith v0.1.0 is a controlled proof of architecture. The next goal is
not a larger claim; it is a larger, independently reproducible body of
evidence.

This roadmap describes intended work, not shipped capability or a delivery
promise.

## Immediate: strengthen the benchmark

- Add non-null pagination fixtures and verify token translation across multiple
  pages. This is the clearest next probe identified by the current active
  experiment.
- Add negative cases for unsupported currencies, missing paths, malformed JSON,
  oversized responses, redirects, and unexpected upstream status codes.
- Repeat model-assisted runs across fixed seeds or equivalent controlled
  settings and report variance instead of presenting one run as representative.
- Separate discovery quality from bridge quality with explicit metrics:
  supported-rule precision, unsupported-case rejection, contract pass rate,
  and loss-disclosure rate.
- Version artifact schemas and record hashes so receipts can identify the exact
  evidence and adapter they verify.

## Next: evaluate generalization

- Create a public synthetic suite with multiple domains, endpoint shapes, and
  deliberately ambiguous migrations.
- Include holdout fixtures that are not represented in model prompts or adapter
  examples.
- Measure false compatibility declarations, not only successful repairs.
- Compare active probing against paired-observation-only baselines to quantify
  when an extra experiment changes the decision.
- Add independent reproduction instructions and publish failed runs alongside
  successful ones.

## Then: broaden constrained capability

- Introduce endpoint inventory from explicit OpenAPI input while keeping the
  operator in control of allowed routes.
- Add more typed transformations only with fail-closed validation and dedicated
  fixtures.
- Model authentication as an operator-supplied policy; never infer or expose
  credentials.
- Support multi-endpoint contract suites and dependency ordering between
  requests.
- Generate a human-reviewable change proposal before any bridge is activated.

## Production-readiness research

- Isolate probes and bridge execution at the network and process levels.
- Add secret and PII redaction before model calls and artifact persistence.
- Add per-target authorization, rate limits, request budgets, and audit logs.
- Sign evidence, specifications, and receipts; verify their chain before load.
- Add adversarial tests for prompt injection inside API payloads and misleading
  upstream behavior.
- Define rollback, expiry, and human approval for generated specifications.

## Packaging and developer experience

- Move dashboard templates and default artifacts into package data.
- Test the installed console script from a wheel outside the repository.
- Publish versioned artifact schemas and a migration policy.
- Add a containerized local demo only after the source workflow remains easy to
  inspect.
- Provide a documented plugin boundary for new fixture domains without
  expanding the trusted execution surface.

## Evidence required before stronger claims

ProtocolSmith should not be described as a general-purpose or production-ready
API migration system until it has, at minimum:

1. A multi-domain holdout evaluation with published failures.
2. Repeated-run stability and false-positive measurements.
3. Independent reproduction of the benchmark and receipts.
4. Security controls for credentials, sensitive payloads, isolation, and rate
   limits.
5. Real-world pilots performed with explicit authorization and human review.

Until then, the accurate description remains: a controlled research prototype
for evidence-driven, constrained API compatibility repair.
