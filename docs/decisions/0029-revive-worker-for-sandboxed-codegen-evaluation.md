---
id: 0029
title: Revive isolated worker to evaluate sandboxed model-generated chart codegen
status: accepted
date: 2026-06-30
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - worker
  - renderer
  - codegen
  - sandbox
  - deployment
  - flexibility
---

# ADR-0029: Revive isolated worker to evaluate sandboxed model-generated chart codegen

## Context

ADR-0017 deferred the worker/add-on split and chose in-process trusted
ChartSpec→Pillow rendering for the first reality proof. That pivot was forced by
a concrete blocker: matplotlib (and its native dependencies) would not install
reliably in the Home Assistant Python environment. The pivot succeeded and the
in-process path ships today, but it renders only a fixed library of trusted
chart families (deterministically routed; the model never writes code). The
original product intent — rendering *model-generated* chart code (the ADR-0004
codegen option) — was never evaluated, because we never got matplotlib running
anywhere the generated code could execute safely.

The integration already carries the worker client (transport, durable token
lifecycle, durable health polling) and a working sandbox proof
(`src/Isolinear/codegen_sandbox_anchor.py`: isolated subprocess, import
allowlist, audit hook denying arbitrary reads, matplotlib PNG output, subprocess
timeout). What is missing is the worker *service* — the long-running process
that answers the ADR-0012 transport contract and runs the sandbox. The
matplotlib blocker dissolves in this model: matplotlib lives in the worker's own
container image, never in HA's Python.

This decision is explicitly an **experiment with a kill condition**. The product
runs against locally-hosted models (the target hardware is a single RTX 3060,
~12 GB VRAM). Whether such models can generate correct, safe matplotlib code at
an acceptable accept/repair rate is unknown and unmeasurable without a running
worker. If the evaluation fails, the worker subsystem is removed and the
architecture refactors back to in-process trusted rendering only.

## Decision

**Revive the isolated worker as a deployment-agnostic HTTP service that runs
sandboxed, model-generated matplotlib codegen, in order to empirically evaluate
codegen quality and sandbox behavior against locally-runnable models. In-process
trusted rendering (ADR-0017) remains the default and is not removed during the
evaluation.**

The worker is a single config-driven HTTP service exposing the ADR-0012 contract
(`POST /v1/render`, `/v1/health`, bearer auth, versioned headers). It is built
and shipped **standalone (Docker) first**; the Home Assistant add-on is a thin
packaging wrapper over the same image, added later, not a fork. The worker knows
nothing about Home Assistant (no HA token, no Supervisor API or token).

Multi-architecture image builds and Supervisor ingress/discovery are explicitly
deferred. The design must not preclude them, but neither is required to learn
whether codegen works.

## Rationale

- The keep/quarantine/remove decision for the worker subsystem cannot be made in
  the abstract. It depends on a fact we have never measured: how good is
  model-generated matplotlib from a 3060-class local model, and how often must
  the sandbox reject or repair it? Building the service buys that data.
- The two hardest pieces already exist (the secure subprocess sandbox and the
  integration-side transport/token/health client). The remaining work is
  connective tissue, not green-field.
- A 12-factor, HA-agnostic service makes "support both standalone and add-on" a
  packaging concern, not an architectural fork. The integration already treats
  the worker as a generic URL+token endpoint (`worker_endpoint_url`).
- Standalone-first forces a clean config/contract boundary and prevents
  accidental coupling to Supervisor conveniences that would break standalone.

## Consequences

**Enables:**
- First real, end-to-end evaluation of model-generated chart code.
- matplotlib rendering without the HA-environment install blocker.
- A path to richer/arbitrary chart shapes beyond the fixed in-process families.

**Constrains:**
- The worker must remain HA-agnostic: config from environment or a mounted file
  only; no Supervisor token or API; listen on a configurable bind address/port;
  stateless beyond a mounted artifact directory.
- Generated code keeps running only under the existing sandbox guarantees —
  import allowlist, no network, no arbitrary filesystem access, audit hook,
  subprocess timeout (ADR-0008).
- Entity selection, allowlist enforcement, and history retrieval remain
  integration-side; only normalized, allowlist-checked render data crosses to
  the worker, which never queries Home Assistant. The integration's data
  boundary (what data goes in) and the worker's sandbox (what code can do) are
  paired defense-in-depth (invariants #1, #4, #5; ADR-0003, ADR-0008).
- In-process trusted rendering stays the default; codegen is the opt-in path
  (invariant #6, ADR-0004).

**Resolved on the build branch:**
- **Repair-loop location: integration-orchestrated** (packet 4). The data
  boundary forces it — the worker never holds a model client, so it cannot call
  the model to repair code. The integration calls `POST /v1/render`
  (`render_mode: "codegen"`) per attempt and, on a *retryable* sandbox failure,
  asks its own model provider to repair the code before re-dispatching, up to a
  capped `max_repair_attempts`. `unsafe_code` is terminal (no repair);
  exhaustion fails closed with a dedicated `codegen_render_failed` card (no
  silent trusted fallback, to keep the packet-5 eval honest). The worker-local
  `invoke_codegen_with_repair` is retained for a future in-worker deployment but
  is not used over HTTP. See
  [docs/specs/codegen-generation-path.md](../specs/codegen-generation-path.md).

**Open:**
- Multi-arch image builds (deferred).
- Supervisor ingress / add-on discovery for zero-config UX (deferred).
- The codegen accept/repair quality bar and the acceptance threshold that
  distinguishes "keep" from "remove."
- The kill path: if the evaluation fails, remove the worker subsystem and
  refactor `job_orchestration.py`, `__init__.py`, and config to in-process only
  (this would be its own superseding ADR).

## Acceptance evidence

**Outcome (2026-07-02): KEEP.** The packet-5 reliability eval
(`evals/codegen_reliability.py`, gallery `evals/prompts/reliability_report.md`,
landed `9320cf0`) ran the 42-prompt benchmark corpus (35 chartable) through
`gemma4:e4b` and `qwen2.5-coder:7b` against the live CT103 worker sandbox:
**both models accepted 33/35 (~94%, 3 recoveries via repair each)** with zero
sandbox false positives — all 4 remaining rejects were legitimate (one
forbidden `locals()`, two genuine numpy type bugs, one output-missing). A real
matplotlib chart was also rendered end-to-end over HTTP on CT103 during
packet 3. The human resolved the kill condition to **keep** on 2026-07-02;
the follow-on render-strategy decisions (codegen primary, pandas, memory cap,
repair policy) are recorded in
[ADR-0030](0030-matplotlib-codegen-primary-render-path.md).
