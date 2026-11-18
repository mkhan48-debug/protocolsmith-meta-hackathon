# Controlled benchmark and evidence boundary

ProtocolSmith's public evidence demonstrates one bounded claim:

> For the bundled synthetic Orders API migration, the committed declarative
> specification restores the tested legacy contract when requests are routed
> to the bundled modern API through the ProtocolSmith bridge.

It does **not** establish that ProtocolSmith can autonomously migrate an
arbitrary production API. This document separates what the repository records,
what can be reproduced locally, and what remains untested.

## Evaluation fixture

The fixture is intentionally small and inspectable:

- One known route family: `GET /customers/{customer_id}/orders`
- One existing synthetic customer: `customer-123`
- Two synthetic orders
- One missing-customer error case
- No authentication or external service dependency in the replay
- Legacy and modern APIs served by the same local laboratory process

The fixture includes request renaming, response restructuring, field renaming,
money representation, date truncation, pagination shape, and error-semantics
changes. It is a controlled demonstration surface, not a representative sample
of all REST APIs.

## Evidence chain

| Stage | Committed evidence | Recorded result | Boundary |
| --- | --- | --- | --- |
| Observe | `artifacts/discovery_report.json` | 3 paired experiments and 10 reported compatibility changes | Paired observations use known inputs and routes. |
| Discriminate | `artifacts/active_probe_trace.json` | 6/6 controlled cases matched expectations | Causally tests only `page_size` ↔ `limit`. |
| Compile | `artifacts/adapter_spec.json` | 1 query rule, 1 root-field rule, 4 item-field rules, 1 pagination mapping, and 1 error rule | Operations are limited to the implemented allowlist. |
| Verify | `artifacts/verification_receipt.json` | 15/15 recorded contract checks passed | Result applies to the synthetic fixture and committed artifact versions. |

The JSON files are committed for inspection and replay. They are not
cryptographically signed, independently reproduced, or evidence of production
traffic.

## Active experiment

Muse proposed that legacy `page_size=N` maps to modern `limit=N`.
ProtocolSmith executed three cases against each API:

| API | Baseline | Other version's name | Proposed name |
| --- | ---: | ---: | ---: |
| Legacy v1 | 2 items | `limit=1` → 2 items | `page_size=1` → 1 item |
| Modern v2 | 2 items | `page_size=1` → 2 items | `limit=1` → 1 item |

All six requests returned HTTP 200 and the six controlled counts matched. This
supports a version-specific parameter rename for the tested value `N=1`. It
does not, by itself, prove behavior for every integer, endpoint, or API.

## What the 15-check receipt verifies

The saved verification receipt checks:

1. The legacy API succeeds.
2. The modern API is directly incompatible with the unchanged legacy
   contract.
3. The bridge restores the legacy success status.
4. The response identifies the generated adapter.
5. The root customer identifier is preserved.
6. A one-order collection size is preserved.
7. The order identifier is preserved.
8. The integer-cent value is preserved.
9. The status value is preserved.
10. The `created_at` calendar date is preserved.
11. Translating a page size of two preserves two results.
12. The observed pagination value is preserved.
13. The missing-customer HTTP status is restored.
14. The missing-customer error body is restored exactly.
15. The lossy date reconstruction is disclosed.

The dashboard's live button performs a smaller five-request replay and reports
its own live checks. The displayed 15/15 figure comes from the committed,
machine-readable verification receipt; these are related but distinct pieces
of evidence.

## Known loss and unresolved risks

- **Time of day:** v2 retains only `YYYY-MM-DD`. The bridge reconstructs
  `T00:00:00Z`, preserves the calendar date, and emits a warning. It cannot
  recover the original time.
- **Pagination:** only `null` continuation values were observed. Non-null token
  format and multi-page traversal remain unverified.
- **Currency:** the fixture covers USD only. Other currencies fail closed.
- **Statuses:** only `paid` and `shipped` were observed.
- **Errors:** only `unknown_customer` ↔ `CUSTOMER_NOT_FOUND` was evaluated.
- **Discovery surface:** the route is known, and candidate parameter names are
  bounded rather than discovered across an arbitrary API.
- **Operations:** the transformation vocabulary is deliberately small.
- **Security and scale:** production credentials, sensitive data, concurrency,
  rate limits, hostile upstreams, and multi-tenant isolation were not tested.
- **Model generalization:** the saved result demonstrates one Muse-assisted
  run. It is not a statistical evaluation across models, prompts, domains, or
  repeated trials.

## Reproduce the local proof

The replay uses committed artifacts and synthetic local services; it does not
require a Meta API key:

```bash
uv sync --locked --all-groups
uv run protocolsmith
```

Open the dashboard URL printed in the terminal and select **Run live
compatibility proof**. For the command-line sequence and troubleshooting, see
[DEMO.md](DEMO.md).

To inspect the receipt without running a service:

```bash
jq '.summary, .known_loss, .checks' artifacts/verification_receipt.json
```

Regenerating the discovery, adapter, or active-probe artifacts is a different
operation. It requires a valid Meta Model API key and should be treated as a
new model-assisted run, not as replay of the committed result.

## Interpreting the result

The most defensible conclusion is that ProtocolSmith demonstrates an auditable
architecture for evidence capture, constrained model reasoning, deterministic
execution, and explicit uncertainty reporting on a controlled migration. The
next milestone is broader, independently repeated evaluation—not a claim that
the current prototype is production-ready.
