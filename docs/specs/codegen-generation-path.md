---
status: draft
date: 2026-07-01
depends-on-adrs: [0029, 0004, 0008, 0012, 0022, 0023]
---

# Codegen generation path: model-generated matplotlib + integration-orchestrated repair

## Status

Draft. Defines the contract surface for the **model codegen generation path**
and the **integration-orchestrated repair loop** per ADR-0029 (revive the worker
for codegen evaluation). This is ADR-0029 **packet 4**. Packets 1–3 built the
worker sandbox package, the HTTP server, and the amd64 container image; they
render `render_mode: "codegen"` requests carrying `codegen.python_code` end to
end. Packet 4 is the *integration side*: the model produces the matplotlib code,
the integration dispatches it to the worker over the existing transport, and —
on a retryable sandbox failure — the integration asks the model to repair the
code and re-dispatches, up to a capped number of attempts. Packet 5 is the live
CT103 end-to-end + reliability eval; this packet is proven **locally** only (a
worker booted in-process on an ephemeral port, or the sandbox directly).

## Related docs

- [bdd/codegen-generation-path/codegen-generation-path-bdd.md](../../bdd/codegen-generation-path/codegen-generation-path-bdd.md) — observable behavior
- [worker-http-server.md](worker-http-server.md) — packet 2, the transport this dispatches over
- [codegen-sandbox-module-promotion.md](codegen-sandbox-module-promotion.md) — packet 1, the sandbox public API + `unsafe_code` policy
- ADR-0029 — revive the worker for codegen evaluation
- ADR-0004 — the codegen render option (opt-in, not the default)
- ADR-0008 — read-only MVP + sandbox security (the data boundary)
- [STATUS.md](../../STATUS.md) — current phase and active work

## Context

The trusted in-process ChartSpec→Pillow renderer (ADR-0017) is the default and
renders a fixed library of chart families deterministically. ADR-0004's codegen
option — the model *writes* the matplotlib code — was never evaluated because
matplotlib never ran anywhere safe. Packets 1–3 dissolved that blocker: the
worker container ships matplotlib and runs generated code under the ADR-0008
sandbox. What is still missing is the piece that makes codegen a real product
path: the model that *generates* the code and, when the sandbox rejects a
runtime error, the loop that asks the model to *repair* it.

This packet adds exactly that, gated behind an opt-in toggle, so packet 5 can
measure accept/repair/reject rates against a locally-runnable model.

### Where the repair loop lives (resolving an ADR-0029 "Open" item)

ADR-0029 left open whether repair is driven server-side (inside the worker) or
integration-side. **This spec resolves it: the repair loop is
integration-orchestrated.** The data boundary forces it — ADR-0029 constrains
the worker so it "never queries Home Assistant" and knows nothing about the
model provider (no model endpoint, no model token). The worker therefore cannot
call the model to repair code. The sandbox package *does* ship a worker-local
`invoke_codegen_with_repair(render_request, repair=...)` that takes an injected
`repair` callable, but that callable would have to be a model client — which the
worker is forbidden to hold. So over HTTP the integration drives the loop: it
calls `POST /v1/render` (`render_mode: "codegen"`) once per attempt via the
existing `HttpJsonWorkerRenderClient`, and on a retryable sandbox failure it
asks its *own* model provider to repair the code before re-dispatching.
`invoke_codegen_with_repair` is **not** used over the HTTP path; it stays a
worker-local convenience for a future in-worker deployment and is documented as
such.

## Behavior contract

### Configuration surface

Two config knobs, both cleanly removable (packet 5 may revisit quickly):

| Field | Location | Type | Default | Meaning |
|---|---|---|---|---|
| `codegen_enabled` | options | bool | `false` | Opt-in toggle. When false the trusted render path is untouched (invariant #6: chart-spec-first; codegen is the advanced opt-in). |
| `codegen_model` | config | optional str | `null` | Model id for codegen generation + repair. **When unset it defaults to the planner model** so codegen can point at a code-specialized model without changing the planner. (Field already present in `config_schema.py`.) |
| `max_codegen_repair_attempts` | options | int ≥ 0 | `1` | Repair retries after the initial attempt (already present). At most `1 + max_codegen_repair_attempts` worker renders. |

`codegen_model` defaulting: the codegen client is constructed with
`model = codegen_model or planner_model`. Config-entry data may arrive as a
`mappingproxy` (the recurring repo gotcha); the codegen setup reads it through
the same `Mapping`-tolerant accessor pattern the planner setup uses.

### Model-provider generation contract

Two new methods on the Ollama-compatible client (freeform code, **not**
schema-constrained — Ollama's `format` is for JSON; codegen output is Python):

- `generate_chart_code(request) -> dict` — one `/api/chat` call. System prompt
  instructs the model to emit a single `render_chart(data, output_path)` Python
  function that implements the already-validated ChartSpec using matplotlib, and
  nothing else. Output is markdown-stripped with the existing
  `_strip_markdown_json` helper (models fence code the same way they fence
  JSON). Returns `{"accepted": True, "code": "model_provider_chart_code_received",
  "provider": ..., "python_code": <str>, "provider_response": ...}` or a
  sanitized `_provider_failure(...)`.
- `repair_chart_code(previous_code, sandbox_error, request) -> dict` — one
  `/api/chat` call that feeds the previous code **and** the sandbox error
  (`error.code`, `error.message`, and the traceback from `error.details` when
  present) back to the model and asks for corrected code. Same freeform,
  markdown-stripped, `_provider_failure`-on-error contract, returning
  `"code": "model_provider_chart_code_repaired"` on success.

Both reuse the existing `_read_chat` transport and the `_chat_payload`-style
message shape, and both use the **codegen model** (which may equal the planner
model). No constrained-decoding `format` is set for code output.

The request the integration passes carries only the already-validated ChartSpec
and the normalized, allowlist-checked history/render data — the same data that
already crosses to the worker. No HA token, worker token, model token, or secret
is ever placed in the generation or repair prompt (data boundary; invariants
#1/#3).

### Integration-orchestrated repair loop (the render step)

When `codegen_enabled` is true and a worker client is configured, the render
step is replaced (only the render step — planning, entity selection, allowlist
enforcement, and deterministic render-family routing are upstream and
unchanged). The loop:

1. **Generate.** Call `generate_chart_code(request)`. Generation failure →
   fail-closed `codegen_render_failed` (see below). On success, take
   `python_code`.
2. **Dispatch.** Build a `render_mode: "codegen"` render request with
   `codegen.python_code = <generated code>` and
   `codegen.max_repair_attempts = max_codegen_repair_attempts`, wrap it in the
   ADR-0012 transport envelope, and call the existing
   `HttpJsonWorkerRenderClient.render_chart`. Read `render_result`.
3. **Success** → serve the PNG through the existing worker-rendered-artifact
   path (`_record_worker_rendered_artifact`), exactly like the trusted worker
   path does today.
4. **Retryable sandbox failure** (`render_result.status == "failed"` and
   `error.code != "unsafe_code"`; e.g. `runtime_error`, `timeout`,
   `output_missing`, `output_too_large`) → if repair budget remains, call
   `repair_chart_code(previous_code, render_result.error, request)`, replace the
   code, and go to step 2. Each re-dispatch is a fresh `POST /v1/render`; the
   sandbox re-runs static safety on every attempt (already implemented, packet
   1).
5. **`unsafe_code` is terminal** — do **not** repair it. The sandbox already
   breaks its own loop on `unsafe_code` (packet 1); mirror that here: fail closed
   immediately with `codegen_render_failed` carrying `unsafe_code`. (Static
   safety is a security gate, not a correctness bug; repairing it would just
   burn attempts re-probing the gate.)
6. **Exhausted** — after `max_codegen_repair_attempts` repairs still failing →
   fail closed `codegen_render_failed`.

### Fail-closed policy (no silent fallback)

On generation failure, `unsafe_code`, or exhausted repair, the codegen path
returns a **dedicated card-facing failure** `codegen_render_failed`, carrying the
final sandbox error code (or the model-provider failure code) as context. It
does **not** silently fall back to the trusted in-process renderer. Rationale
(recorded here per the brief): a silent trusted fallback would mask codegen
failures and muddy the packet-5 accept/reject/repair eval — the very data the
ADR-0029 keep/remove decision rests on. The failure is surfaced as a
`codegen_render_failed` failed-snapshot the same way other terminal render
failures already produce card-facing failed snapshots.

### What does NOT change

- The planner still produces the validated ChartSpec; entity selection,
  allowlist enforcement (#1), schema validation (#4), deterministic plan
  validation (#5), and render-family routing (#9) are upstream and untouched.
- When `codegen_enabled` is false, `_record_worker_dispatch` /
  `_record_in_process_render` behave exactly as today (`render_mode: "safe"`,
  trusted renderer). No behavior change on the default path.
- The worker transport, auth, and health contracts (packet 2) are unchanged; the
  only new thing on the wire is `render_mode: "codegen"` + `codegen.python_code`,
  which the worker already accepts.

## Anchor artifact

The simplest concrete observable: with codegen enabled, the model (a fake Ollama
returning a known-good `render_chart` body) generates matplotlib code for a
validated ChartSpec, a **locally-booted worker** (packet-2
`isolinear_worker.http_server` on an ephemeral port, mirroring
`evals/worker_http_server.py`) renders it over HTTP into a real PNG on disk, and
the integration serves that PNG through the existing artifact path. Built before
the repair/rejection paths. (On a dev box the `-I` sandbox cannot import
matplotlib — the documented packet-1 limitation — so the matplotlib variant is
`skipUnless`-gated exactly as packets 1–2 gate it, and a non-matplotlib safe
`render_chart` body carries the real-PNG proof in every environment.)

## Implementation order

Concrete-first:

1. **Anchor:** `generate_chart_code` on the client + the enabled happy-path
   render through a locally-booted worker to an on-disk PNG.
2. **Config:** `codegen_enabled` option (default false) wired through
   `config_schema.py` / `config_flow.py`; `codegen_model` default-to-planner in
   the codegen setup.
3. **`repair_chart_code`** + the integration repair loop in `job_orchestration.py`
   (generate → dispatch → retryable repair → serve / fail-closed).
4. **Fail-closed** `codegen_render_failed` snapshot on exhaustion / `unsafe_code`
   / generation failure.
5. **Tests + eval:** fake Ollama for generation/repair + a locally-booted worker
   (or direct sandbox) for rendering.

## Proof requirements

1. Unit tests in `tests/test_codegen_generation_path.py` green, covering:
   disabled→trusted path unchanged; enabled happy path (generate→render→PNG);
   retryable error→repair→success; repair exhausted→`codegen_render_failed`;
   `unsafe_code`→immediate fail-closed (no repair call); `codegen_model` defaults
   to the planner model; a separate `codegen_model` is honored; data boundary (no
   token/secret crosses into the generation/repair prompt).
2. BDD scenarios in
   [bdd/codegen-generation-path/codegen-generation-path-bdd.md](../../bdd/codegen-generation-path/codegen-generation-path-bdd.md)
   pass; an evidence file with **raw** outputs is written at
   `bdd/codegen-generation-path/codegen-generation-path-evidence.md`.
3. **Local end-to-end proof:** an eval (`evals/codegen_generation_path.py`) boots
   the packet-2 worker in-process on an ephemeral port and drives the real
   generation→dispatch→repair loop against it, producing a real PNG (raw
   request/response captured, authorization redacted). No CT103 / remote host is
   touched.
4. Full `python3 -m pytest tests/` green (the 3 matplotlib-in-`-I` dev-box skips
   stay skipped locally).

## Non-goals

- **Live CT103 end-to-end + the reliability eval** (accept/repair/reject rates
  from a real 3060-class model) — ADR-0029 packet 5.
- **In-worker repair** driven by `invoke_codegen_with_repair` over HTTP — the
  worker is forbidden to hold a model client (data boundary); documented, not
  built.
- **Artifact byte transfer** changes — the codegen path reuses the existing
  worker-rendered-artifact serving unchanged.
- Any change to the **sandbox security model** or the packet-1/2/3 public APIs.
- Frontend / card changes (the `codegen_render_failed` failed snapshot rides the
  existing failed-snapshot surface).

## References

- ADR-0029 — revive worker for codegen evaluation
- ADR-0004 — codegen render option
- ADR-0008 — read-only MVP + sandbox security
- ADR-0012 — worker transport and authentication
- [worker-http-server.md](worker-http-server.md) — packet 2
- [codegen-sandbox-module-promotion.md](codegen-sandbox-module-promotion.md) — packet 1
- `custom_components/isolinear/model_provider.py` — the Ollama client
- `custom_components/isolinear/worker_renderer.py` — the worker transport client
- `custom_components/isolinear/job_orchestration.py` — render dispatch
