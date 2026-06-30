# Codegen sandbox module promotion — BDD

## Status

Draft. Paired with
[docs/specs/codegen-sandbox-module-promotion.md](../../docs/specs/codegen-sandbox-module-promotion.md).

Evidence file:

- `bdd/sandbox-codegen/codegen-sandbox-module-promotion-evidence.md`

## Why this BDD exists

This pins down the *promotion* of the proven codegen sandbox from an anchor into
a self-contained worker module the standalone worker service can import (ADR-0029).
The sandbox's security behavior is already proven by the accepted
[sandbox-codegen BDD](sandbox-codegen-bdd.md); these scenarios prove the
promoted module is real, self-contained, behavior-preserving, and that the
anchor has been retired without losing coverage.

## Scenarios

### Scenario A — happy path: the promoted module renders a PNG through its public API

**Given** the worker package `worker/isolinear_worker/`
**And** a valid render request whose generated Python imports `matplotlib.pyplot`
and defines `render_chart(data, output_path)`
**When** a caller does `from isolinear_worker.codegen_sandbox import
invoke_codegen_sandbox, default_codegen_sandbox_policy` and invokes the sandbox
**Then** a valid PNG (correct signature) is written to the fixed output path
**And** the RenderResult metadata reports the `Agg` backend
**And** no anchor scaffolding (`verify_*_anchor`, hardcoded sample payload) is
involved

### Scenario B — the worker module is self-contained (HA-agnostic)

**Given** the promoted `isolinear_worker.codegen_sandbox` module
**When** it is imported and its import graph is inspected
**Then** it imports nothing from `custom_components.isolinear`
**And** it imports nothing from `src.Isolinear` (the anchor tree)
**And** it validates its policy against a schema bundled inside the worker package

### Scenario C — security denials hold at parity through the public API

**Given** generated Python that (i) imports a forbidden module such as
`requests`, (ii) attempts to read secrets / environment / a local socket, or
(iii) routes an arbitrary file read through an allowlisted rendering library
**When** the promoted `invoke_codegen_sandbox` / `static_safety_check` runs
**Then** each attempt is rejected or denied with the inherited structured code
(`unsafe_code` before execution; fail-closed audit denial at runtime)
**And** no target resource is read and no successful artifact is produced
**And** the outcomes match the accepted sandbox-codegen BDD scenarios D and E

### Scenario D — oversized output and timeout still fail closed

**Given** generated Python that writes output larger than the policy allows
(and, separately, code that exceeds the timeout)
**When** invoked through the promoted module
**Then** the results are `output_too_large` and `timeout` respectively
**And** neither exposes a successful artifact

### Scenario E — capped repair loop is preserved with an injected repair callable

**Given** generated Python that raises a runtime exception
**And** `invoke_codegen_with_repair` configured with `max_attempts = 2` and an
injected (non-model) repair callable
**When** the sandbox runs codegen with repair
**Then** static safety checks re-run for every repaired attempt
**And** it retries no more than 2 times
**And** it returns a structured failure if all attempts fail
*(Wiring a real repair model is out of scope — ADR-0029 packet 4.)*

### Scenario F — the anchor is retired without losing coverage

**Given** the promotion slice has landed
**When** the test suite and eval run
**Then** `src/Isolinear/codegen_sandbox_anchor.py` and
`tests/test_codegen_sandbox_anchor.py` no longer exist
**And** `tests/test_codegen_sandbox.py` covers parity with sandbox-codegen
scenarios A–G
**And** `python3 -m pytest tests/` is green
**And** `evals/codegen_sandbox.py` (repointed to the promoted module) passes

## Evidence

The implementing slice produces an evidence file at
`bdd/sandbox-codegen/codegen-sandbox-module-promotion-evidence.md` containing the
**raw** outputs (not summaries) for each scenario: the pytest run, the
import-graph check, the on-disk PNG verification (e.g. `file`/signature bytes),
and the repointed eval run.
