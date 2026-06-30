---
status: draft
date: 2026-06-30
depends-on-adrs: [0029, 0008, 0012, 0001, 0004]
---

# Codegen sandbox: promote the anchor to a self-contained worker module

## Status

Draft. Defines the contract surface for promoting the proven codegen-sandbox
anchor into a real, importable worker module per ADR-0029 (revive the isolated
worker to evaluate sandboxed model-generated chart codegen). The sandbox
*security model and behavior* are already specified in
[worker-sandbox-spec.md](worker-sandbox-spec.md) and proven by the accepted
[sandbox-codegen BDD](../../bdd/sandbox-codegen/sandbox-codegen-bdd.md); this
spec does not change them. It promotes the implementation from an anchor into
production code the worker HTTP service (a later packet) can depend on.

## Related docs

- [bdd/sandbox-codegen/codegen-sandbox-module-promotion-bdd.md](../../bdd/sandbox-codegen/codegen-sandbox-module-promotion-bdd.md) — observable behavior
- [worker-sandbox-spec.md](worker-sandbox-spec.md) — the sandbox security model (inherited, unchanged)
- [STATUS.md](../../STATUS.md) — current phase and active work
- ADR-0029 — revive the worker for codegen evaluation

## Context

The codegen sandbox — the security-sensitive piece that runs model-generated
matplotlib code without letting it touch secrets, the network, or the
filesystem — already exists and is proven, but only as an *anchor*:
`src/Isolinear/codegen_sandbox_anchor.py`. It carries test fixtures, a hardcoded
sample payload, and a `verify_*_anchor` verifier mixed in with the real logic,
and it lives in the `src/Isolinear/` anchor tree.

ADR-0029 revives the worker as a **standalone service** that will import this
sandbox. That service must be deployable in its own container with no access to
the Home Assistant integration. So the sandbox must become a **self-contained
worker module** — importable, parameterized, real-tested, and free of any
dependency on `custom_components/isolinear/`. This packet is the foundation the
HTTP server (next packet) builds on; nothing here is user-visible yet.

## Behavior contract

### Location

A new self-contained worker package: **`worker/isolinear_worker/`**.

- The sandbox lands at `worker/isolinear_worker/codegen_sandbox.py`.
- The package **must not import from `custom_components/isolinear/` or
  `src/Isolinear/`** (invariant: the worker knows nothing about Home Assistant,
  ADR-0012/ADR-0029). It carries its own copy of the policy/contract schema(s)
  and a minimal schema-validation helper.
- Worker runtime dependencies are declared in `worker/requirements.txt`
  (matplotlib, jsonschema). The container image that provides them is a later
  packet (ADR-0029); the repo dev `.venv` already has matplotlib so tests run.
- The HACS-shipped `custom_components/isolinear/` package gains **no new
  dependency** and continues to import nothing from `worker/`. The integration's
  existing `worker_renderer.py` HTTP *client* stays where it is.

### Public API

The module exposes the proven anchor operations, with the anchor/fixture/verifier
scaffolding removed:

```python
SANDBOX_POLICY_VERSION: int

def default_codegen_sandbox_policy() -> dict:
    """The Raspberry-Pi-compatible default policy (isolated subprocess, Agg
    backend, import allowlist, fixed output path, timeout, resource limits where
    available, max output bytes)."""

def static_safety_check(code: str, *, policy: dict) -> dict:
    """AST safety gate run before any execution. Returns
    {"safe": bool, "violations": [...], "code": "unsafe_code" | None}."""

def invoke_codegen_sandbox(render_request: dict, *, policy: dict | None = None,
                           work_root: str | Path | None = None) -> dict:
    """Validate → static-check → execute generated code in an isolated `-I`
    subprocess with a stripped env, audit hook, and bounded timeout. Returns a
    RenderResult dict."""

def invoke_codegen_with_repair(render_request: dict, *, policy: dict | None = None,
                               repair, max_attempts: int = 2,
                               work_root: str | Path | None = None) -> dict:
    """Capped repair loop around invoke_codegen_sandbox. The repair callable is
    injected; wiring it to a real repair *model* is a later packet (ADR-0029
    packet 4). Re-runs static safety checks for every repaired attempt."""
```

### RenderResult and error codes

`invoke_codegen_sandbox` returns a dict carrying at least `accepted: bool`,
`code: str`, and on success an image reference at the fixed output path plus
normalized render `metadata` (plotted series, overlays, title, time range,
warnings — including the `Agg` backend warning) and `resource_status`. The
structured failure codes are inherited verbatim from worker-sandbox-spec.md:
`invalid_request`, `unsupported_chart_spec`, `unsafe_code`, `runtime_error`,
`timeout`, `output_missing`, `output_too_large`, `validation_failed`.

### Inherited, unchanged (do not re-decide here)

The subprocess isolation (`-I` + stripped env + temp cwd + no tokens), the
audit hook that fails closed on socket/subprocess/OS-mutation/out-of-sandbox
filesystem events, the import allowlist, the fixed-output-path-only write rule,
the timeout + `resource` limits, and the `max_output_bytes` cap are all defined
by [worker-sandbox-spec.md](worker-sandbox-spec.md) and proven by the accepted
sandbox-codegen BDD (scenarios A–G). Promotion must preserve them at parity.

## Anchor artifact

A real pytest that does `from isolinear_worker.codegen_sandbox import
invoke_codegen_sandbox, default_codegen_sandbox_policy`, feeds the matplotlib
fixture through the public API, and asserts a real PNG (correct signature) was
written to the fixed output path with `Agg` reported in metadata — importing
**only** the `worker` package (no `custom_components`, no `src` anchor). This is
Scenario C behavior, driven through the promoted module from a real test.

## Implementation order

1. **Create `worker/isolinear_worker/`** package skeleton (`__init__.py`), a
   minimal self-contained schema-validation helper, and a bundled copy of
   `codegen-sandbox-policy.schema.json`. Add `worker/requirements.txt`.
2. **Port the sandbox** `src/Isolinear/codegen_sandbox_anchor.py` →
   `worker/isolinear_worker/codegen_sandbox.py`: keep `default_codegen_sandbox_policy`,
   `static_safety_check`, `invoke_codegen_sandbox`, `invoke_codegen_with_repair`
   and their private helpers; drop the hardcoded sample, the `*_generated_python`
   fixtures, and `verify_codegen_sandbox_anchor`.
3. **Move test fixtures** (the generated-Python samples + `sample_codegen_render_request`)
   into the test tree as fixtures — they are test material, not production code.
4. **Real pytest** `tests/test_codegen_sandbox.py` covering parity with BDD
   scenarios A–G, driven entirely through the public API.
5. **Repoint the eval** `evals/codegen_sandbox.py` to the promoted module.
6. **Retire the anchor**: once parity is green, delete
   `src/Isolinear/codegen_sandbox_anchor.py` and
   `tests/test_codegen_sandbox_anchor.py`.

## Proof requirements

1. `tests/test_codegen_sandbox.py` green, at parity with sandbox-codegen
   scenarios A–G (run through the public API).
2. BDD scenarios in
   [codegen-sandbox-module-promotion-bdd.md](../../bdd/sandbox-codegen/codegen-sandbox-module-promotion-bdd.md)
   pass; an evidence file with **raw** outputs is written.
3. Real-artifact proof: a PNG produced through the promoted public API exists on
   disk and is a valid PNG (eyes-on confirmed).
4. Self-containment proof: importing `isolinear_worker.codegen_sandbox` pulls in
   nothing from `custom_components/isolinear/` or `src/Isolinear/` (import-graph
   check in the test).
5. Full `python3 -m pytest tests/` green after anchor removal; the repointed
   `evals/codegen_sandbox.py` passes.

## Non-goals

- The worker **HTTP server** (`/v1/render`, `/v1/health`) — next packet.
- The **Dockerfile / matplotlib image** and standalone deployment — ADR-0029 packet 3.
- The **model codegen generation path** (the planner emitting matplotlib Python)
  and wiring a real **repair model** — ADR-0029 packet 4.
- Wiring the sandbox into `job_orchestration.py` / the integration.
- Any change to the sandbox **security model** (inherited from worker-sandbox-spec.md).
- Multi-arch images and Supervisor ingress/discovery (deferred by ADR-0029).

## References

- [worker-sandbox-spec.md](worker-sandbox-spec.md) — sandbox security model
- [docs/schemas/codegen-sandbox-policy.schema.json](../schemas/codegen-sandbox-policy.schema.json) — policy contract
- ADR-0029 — revive worker for codegen evaluation; ADR-0008 — sandbox security;
  ADR-0012 — worker transport; ADR-0004 — chart-spec-first with codegen option
- Source being promoted: `src/Isolinear/codegen_sandbox_anchor.py`
