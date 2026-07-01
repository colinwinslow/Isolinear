# Codegen generation path: model-generated matplotlib + repair — BDD

## Status

Draft. Paired with [docs/specs/codegen-generation-path.md](../../docs/specs/codegen-generation-path.md).
ADR-0029 packet 4.

## Why this BDD exists

Pins the user-visible behavior of the opt-in codegen render path: when enabled,
the model generates matplotlib code that a locally-booted worker renders to a
real PNG; on a retryable sandbox error the integration asks the model to repair
the code and re-renders; and the path fails closed (never silently falls back to
the trusted renderer) on `unsafe_code` or exhausted repair. When disabled, the
trusted render path is untouched.

## Scenarios

### Scenario A — happy path: enabled codegen generates code, worker renders a PNG

**Given** codegen is enabled (`codegen_enabled: true`) and a worker is
configured (a packet-2 worker booted in-process on an ephemeral port)
**And** the model returns a valid `render_chart(data, output_path)` body for the
validated ChartSpec
**When** a render job runs
**Then** the integration calls `generate_chart_code`, dispatches a
`render_mode: "codegen"` request carrying `codegen.python_code` to the worker,
and the render succeeds with a real PNG served through the existing artifact path
(valid PNG signature on disk).

### Scenario B — retryable failure repairs to success

**Given** codegen is enabled with `max_codegen_repair_attempts >= 1`
**And** the first generated code fails in the sandbox with a retryable
`runtime_error`, and the model's repair returns working code
**When** the render job runs
**Then** the integration calls `repair_chart_code` once (feeding the previous
code + the sandbox error/traceback), re-dispatches a second `render_mode:
"codegen"` request, and the second render succeeds with a real PNG served.

### Scenario C — exhausted repair fails closed

**Given** codegen is enabled with `max_codegen_repair_attempts` repairs allowed
**And** every attempt (initial + repairs) fails in the sandbox with a retryable
`runtime_error`
**When** the render job runs
**Then** after the budget is exhausted the job fails with a card-facing
`codegen_render_failed` result carrying the final sandbox error code — the
trusted renderer is **not** silently used as a fallback.

### Scenario D — `unsafe_code` fails closed immediately, no repair

**Given** codegen is enabled and the generated code fails static safety in the
sandbox (`error.code == "unsafe_code"`)
**When** the render job runs
**Then** the job fails immediately with `codegen_render_failed` carrying
`unsafe_code`, and **no** `repair_chart_code` call is made (repairing a security
gate is terminal, mirroring the sandbox's own break-on-`unsafe_code`).

### Scenario E — disabled leaves the trusted path unchanged

**Given** codegen is disabled (`codegen_enabled: false`)
**When** a render job runs
**Then** the render request uses `render_mode: "safe"` / the trusted renderer,
no `generate_chart_code` or `repair_chart_code` call is made, and behavior is
identical to today's default path.

### Scenario F — codegen model selection

**Given** codegen is enabled
**When** `codegen_model` is unset
**Then** the codegen client uses the planner model for generation and repair;
**and** when `codegen_model` is set to a distinct value, that model is used for
codegen while the planner model is unchanged.

### Scenario G — data boundary: no secret crosses into the codegen prompt

**Given** codegen is enabled
**When** `generate_chart_code` / `repair_chart_code` build their request bodies
**Then** no HA token, worker token, model token, or other secret appears in the
generation or repair prompt — only the validated ChartSpec and the normalized,
allowlist-checked render data (the same data that already crosses to the worker).

## Evidence

The implementing slice produces an evidence file at
`bdd/codegen-generation-path/codegen-generation-path-evidence.md` containing raw
outputs (not summaries) for each scenario: the fake-Ollama request bodies, the
worker render results, the served PNG signature, and the `codegen_render_failed`
failure payloads.
