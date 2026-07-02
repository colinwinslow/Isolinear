# Codegen generation path: model-generated matplotlib + repair — BDD

## Status

Accepted. Paired with [docs/specs/codegen-generation-path.md](../../docs/specs/codegen-generation-path.md).
ADR-0029 packet 4. Revised 2026-07-02 per ADR-0030: Scenario D (all sandbox
failure classes repairable, including `unsafe_code`); Scenarios C/D2/E/H/I
(codegen primary via `render_path: auto`, Pillow the surfaced fallback,
`render_path: pillow` the explicit trusted option).

## Why this BDD exists

Pins the user-visible behavior of the codegen render path — the PRIMARY path
per ADR-0030: with `render_path: auto` (the default) and a worker configured,
the model generates matplotlib code that the worker renders to a real PNG; on
any sandbox error the integration asks the model to repair the code and
re-renders; and on generation failure / exhausted repair / worker transport
fault the integration falls back to the trusted Pillow renderer with the
fallback **surfaced** on the chart (`render_path` + `render_fallback_reason`),
never silently. `render_path: pillow` explicitly keeps the trusted renderer.

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

### Scenario C — exhausted repair falls back to Pillow, surfaced (ADR-0030)

**Given** `render_path: auto` with `max_codegen_repair_attempts` repairs allowed
**And** every attempt (initial + repairs) fails in the sandbox with a
`runtime_error`
**When** the render job runs
**Then** after the budget is exhausted the job **completes** through the trusted
Pillow renderer, and the served chart carries `render_path: "pillow"` +
`render_fallback_reason` (the final codegen failure context) — the fallback is
surfaced, never silent.

### Scenario D — `unsafe_code` is repairable, bounded (ADR-0030 revision)

**Given** codegen is enabled and the generated code fails static safety in the
sandbox (`error.code == "unsafe_code"`)
**When** the render job runs with repair budget remaining
**Then** `repair_chart_code` is called with the sandbox violation, the repaired
code is re-dispatched (the worker re-runs the full static check + sandbox on the
fresh attempt), and a safe repair completes the job with a served PNG.

### Scenario D2 — `unsafe_code` through exhaustion falls back, surfaced

**Given** `render_path: auto` and the code still fails static safety after
every repair attempt
**When** the repair budget (`max_codegen_repair_attempts`) is exhausted
**Then** the security gate enforced on every attempt (repair only ever got
another try at it, never around it), and the job completes through the Pillow
fallback with `render_fallback_reason: "unsafe_code"` surfaced on the chart.

### Scenario E — `render_path: pillow` explicitly keeps the trusted renderer

**Given** `render_path: "pillow"` is configured (even with a worker configured)
**When** a render job runs
**Then** the trusted in-process Pillow renderer produces the chart, no
`generate_chart_code` / `repair_chart_code` call is made, no worker dispatch
occurs, and the chart carries `render_path: "pillow"` with **no**
`render_fallback_reason` (an explicit choice is not a fallback).

### Scenario H — auto is the default: codegen primary with no toggle

**Given** a fresh options surface (no legacy `codegen_enabled`, nothing set)
**When** a worker + planner are configured and a render job runs
**Then** `render_path` defaults to `"auto"`, the codegen client is installed,
and the job renders through codegen (`render_path: "codegen"` on the chart).

### Scenario I — worker transport fault falls back to Pillow, surfaced

**Given** `render_path: auto` and the worker is unreachable/unhealthy at
dispatch time (a transport-layer fault, not a sandbox result)
**When** the render job runs
**Then** the job completes through the Pillow fallback with
`render_path: "pillow"` + `render_fallback_reason` carrying the transport
failure classification code.

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
