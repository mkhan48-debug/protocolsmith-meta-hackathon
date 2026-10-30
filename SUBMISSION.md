# ProtocolSmith Submission Copy

## Entry

- **Project:** ProtocolSmith
- **Builder:** Muhammad Rafae Khan
- **Track:** Indie Developer
- **Theme:** Push the Frontier
- **Repository:** https://github.com/mkhan48-debug/protocolsmith-meta-hackathon
- **Demo video:** Add the final shareable video URL before submission

## One-line pitch

ProtocolSmith actively probes legacy and modern APIs, uses Meta Muse Spark to compile the observed differences into an allowlisted compatibility bridge, and deterministically proves that unchanged legacy software works again.

## Short summary

ProtocolSmith is a black-box API migration agent that gathers differential evidence, uses Meta Muse Spark 1.3 to infer compatibility rules and design experiments, compiles an allowlisted adapter specification, executes a deterministic bridge, and produces a verification receipt proving that an unchanged legacy client works against a modern API.

## Project description

API migrations often break existing clients in ways documentation does not capture: request parameters are renamed, fields move into nested objects, values change representation, pagination evolves, and errors acquire different HTTP semantics. ProtocolSmith investigates those behavioral changes through controlled black-box experiments.

The prototype includes intentionally incompatible legacy and modern Orders APIs plus an unchanged legacy client. ProtocolSmith sends paired requests, records raw responses and structural shapes, and preserves those observations as evidence. Meta Muse Spark 1.3 analyzes the evidence through typed structured outputs, identifies supported compatibility changes, and designs a discriminating follow-up experiment. A second constrained Muse step compiles the findings into a declarative adapter specification containing only allowlisted operations.

A deterministic runtime executes that specification as a compatibility bridge. The decisive demonstration shows the unchanged client succeeding against API v1, failing directly against API v2, and succeeding again through ProtocolSmith. Fourteen recorded contract checks verify fields, values, pagination, error semantics, and an explicit warning for lost timestamp information. ProtocolSmith never executes arbitrary model-generated source code and does not silently claim compatibility when the evidence cannot support it.

## Impact

API migrations frequently require engineers to compare documentation, inspect traffic, repair clients, and rediscover undocumented behavior manually. ProtocolSmith demonstrates an evidence-driven alternative: observe both systems, separate supported conclusions from assumptions, compile only constrained transformations, and preserve an auditable chain from experiment to verified bridge. The current project is a controlled technical prototype and does not claim production deployment or customer adoption.

## Creative use of Meta AI

Muse Spark is part of the product's reasoning loop, not a generic chat interface or coding-only assistant. It performs three bounded tasks:

1. Infer compatibility changes from paired behavioral evidence.
2. Compile evidence-backed findings into a typed declarative adapter specification.
3. Design and assess a discriminating active experiment.

Pydantic constrains Muse outputs. ProtocolSmith then validates and executes them deterministically. The live dashboard proof uses previously generated Muse artifacts; the button itself performs deterministic HTTP requests and does not call Muse live.

## Technical execution

- Python 3.12 and FastAPI
- Meta Model API with `muse-spark-1.3`
- Pydantic structured model outputs
- Differential request and response evidence collection
- Recursive response-shape descriptions
- Constrained declarative adapter compiler
- Allowlisted deterministic transformation runtime
- Explicit loss and uncertainty reporting
- Active model-designed experiment with deterministic acceptance
- Machine-readable discovery, probe, adapter, and verification artifacts
- Interactive live-proof dashboard
- One-command local launcher
- Eleven automated tests and GitHub Actions CI

## Demonstration sequence

1. Show the hackathon new-work declaration.
2. Explain the API migration problem and evidence-to-proof architecture.
3. Show Muse's model-designed experiment and generated specification.
4. Run the dashboard's live proof.
5. Show v1 passing, direct v2 failing, and the generated bridge passing.
6. Show the deterministic verification receipt and disclosed timestamp loss.

## Honest limitations

- The prototype uses one controlled synthetic Orders domain and one endpoint family.
- It supports a deliberately small transformation allowlist.
- The active probe causally supports one request-parameter mapping; it does not prove every inferred mapping independently.
- The modern example discards time-of-day information. ProtocolSmith reconstructs midnight UTC and exposes the loss explicitly.
- Remote targets require explicit opt-in, and production deployment would require stronger credential, redaction, isolation, and rate-limit policies.

## New-work declaration

ProtocolSmith's application code, experiment engine, Muse integration, artifacts, bridge runtime, verification system, tests, launcher, dashboard, and documentation were created during the Meta Global AI Developer Hackathon build period. Standard open-source dependencies are identified separately and are not claimed as original work.
