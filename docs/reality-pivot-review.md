# Isolinear — Reality Pivot Review

> **Audience:** the coding agent (GPT‑5.5) that has been building Isolinear.
> **Date:** 2026-06-12 · **Branch reviewed:** `michaelkit` (56 commits ahead of `main`).
> **Purpose:** keep what's good, name the core problem, and pivot from simulated
> scaffolds to a real Home Assistant + Ollama + matplotlib vertical slice.

---

## 1. Verdict in one paragraph

You have built genuinely excellent *engineering process* around a product that
has **never touched reality**. 15 ADRs, paired specs/BDD/evidence/evals/schemas,
fail-closed boundaries, token redaction, config-entry scoping, single-flight
guards, bounded backoff — all real, all green (289 tests pass). But every
"production" module in `custom_components/isolinear/` produces **deterministic
fake data**: no real recorder history, no real entities, no real Ollama call, no
real renderer. The hardest and most uncertain parts of the project are exactly
the parts that have been deferred. It is time to stop adding scaffolds and prove
one real path end-to-end.

## 2. What to keep (this is good work — do not regress it)

- **The security invariants.** Allowlist-only entity exposure, read-only MVP,
  token never reaching the card/model, redaction discipline. These carry over
  unchanged to the real integration. Keep them.
- **Schema-first contracts.** `docs/schemas/*.json` + `src/Isolinear/contracts.py`
  are a real asset. The `ChartSpec`, `PlannerResult`, `HistorySeries`,
  `EntityCatalogItem` schemas are the bridge between fake and real — keep
  validating real data against them.
- **The ADR trail and STATUS/HANDOFF continuity.** Keep recording decisions and
  session state. Do not abandon the workflow; just spend it on real work.
- **Correctness patterns** in `worker_health_polling.py` (generation counters,
  single-flight, deepcopy isolation, fail-closed validation). Reuse the patterns
  when the real worker exists.

## 3. The core problem

**Everything is simulated, and the simulation encodes unvalidated assumptions.**

Evidence:
- Every `homeassistant` import is `try/except`-guarded and falls back to fakes.
- `entity_catalog.py` / `history_retrieval.py` build from "fake Home Assistant
  entity/state metadata" — there is no `recorder` call anywhere in the tree.
- The model-provider modules never call Ollama; the latest packet literally
  "records provider-health availability **without calling the provider**."
- `fake_slice.py` is 3,334 lines including a hand-rolled PNG encoder — throwaway
  once real matplotlib renders.

The risk: when you finally call a real recorder / real Ollama / real matplotlib,
the data shapes, latencies, failure modes, and prompt reliability may **not match
the assumptions baked into the scaffolds and schemas** — and a lot of evidence
sits on top of those guesses.

## 4. Anti-patterns to stop now

1. **Stop building parallel `*_anchor.py` verifiers.** ~20k LOC of verifier
   modules duplicate what pytest already does (e.g. a 150-condition boolean
   `if`-chain in `worker_health_polling_anchor_verifier.py`). From here on,
   **pytest is the single source of behavioral truth.** Evals/evidence become
   thin wrappers, not a second test framework.
2. **Stop micro-packets that store a flag.** A packet should move the real
   product forward, not add ceremony around an in-memory boolean.
3. **Stop building on unvalidated seams.** Do not add the next worker/retry/
   polling scaffold. The scaffolds for those already exist; they are blocked on
   reality, not on more scaffolding.
4. **Do not expand `fake_slice.py`.** Freeze it. It can stay as a reference, but
   new effort goes into the real path.

## 5. The pivot: one real vertical slice

**Goal:** a single real prompt produces a real chart from real Home Assistant
history via a real local model, shown in the existing Lit card — against a real
HA dev instance. Ugly is fine. The point is to make every faked seam real.

Recommended scope (deliberately minimal):

| Seam | Today (fake) | First real slice |
|---|---|---|
| Entities | hardcoded fake catalog | real entity/area/device registry, filtered by the configured allowlist |
| History | `get_fake_normalized_history` | real recorder history for the allowlisted entities |
| Planner | deterministic stub | real Ollama call returning a schema-valid `ChartSpec` |
| Renderer | hand-rolled PNG | real matplotlib (in-process trusted renderer is fine for v1) |
| Transport | scaffold snapshots | existing `isolinear/v1/` websocket commands + Lit card |

**Deliberately defer** (scaffolds already exist; do not touch until the spine
works): sandbox codegen, the separate worker add-on, durable health polling,
retry/backoff policies, worker progress streaming, semantic memory persistence.
For v1, render **in-process** in the integration to remove moving parts — the
sandbox/worker split is a hardening step, not an MVP requirement.

### Real-API notes the slice must confront

- **Recorder is synchronous.** Read history via the recorder helper
  (`homeassistant.components.recorder.history`, e.g. significant-states / state
  changes over a period) and run it through
  `recorder.get_instance(hass).async_add_executor_job(...)` — never block the
  event loop. Normalize the raw states into your existing `HistorySeries` schema
  (you already handle `unknown`/`unavailable` → null + warnings; keep that).
- **Registries.** Use `entity_registry`, `area_registry`, `device_registry`
  helpers (`async_get(hass)`) to build real `EntityCatalogItem`s — device_class,
  unit, area, labels. Intersect with the configured allowlist.
- **Ollama.** Default `http://localhost:11434`. `GET /api/tags` for health (you
  already model this), `POST /api/chat` (or `/api/generate`) for planning. Use
  the `format` parameter with your `ChartSpec` JSON schema to force structured
  output, then **still validate** the result with `contracts.py` and reject any
  entity id not in the allowlist (you already have recursive hidden-entity
  rejection logic — reuse it on real output).
- **matplotlib.** Use the `Agg` backend, render to PNG, enforce a max output
  size. In-process for v1.
- **HTTP.** Use HA's shared aiohttp session (`async_get_clientsession`) for the
  Ollama call.

### Acceptance criteria for the slice

- Installs as a real custom integration in a real HA dev container (config flow
  completes; one config entry; allowlist of ≥1 real entity).
- A real prompt over the websocket command returns a real PNG built from real
  recorder history and a real Ollama-produced `ChartSpec`.
- The `ChartSpec`, `HistorySeries`, and `PlannerResult` all validate against the
  existing schemas — **and you fix the schema if real data doesn't fit** (this
  is the whole point: let reality correct the contracts).
- Allowlist + read-only invariants hold against real data (no non-allowlisted
  entity is ever read or rendered; no HA state is mutated).
- Verified **manually against a running HA instance**, not just by unit tests.

## 6. Housekeeping

- **Reconcile branches.** `main` still has the old seed (`docs/adr/`, small
  `fake_slice.py`); `michaelkit` renamed it to `docs/decisions/` and built
  everything. Pick a canonical branch and either merge or retire `main` so
  `/startup` doesn't read stale state.
- **Dev environment is Windows/PowerShell-centric** with historical hardcoded
  python paths and no committed venv. The production target is Linux/Pi — set up
  a real HA dev container (the official `homeassistant` dev container or a
  `pip install homeassistant` venv) so you can actually run the integration.
- **Collapse the verification layers** as you touch each area: when a real module
  replaces a scaffold, delete its `*_anchor.py` verifier and keep only pytest.

## 7. Suggested next ADR + packet

- **ADR-0016: "First real vertical slice — in-process real renderer, real
  recorder history, real Ollama planner."** Record that the MVP proves the spine
  in-process and defers the worker/sandbox split to a later hardening ADR.
- **Packet:** implement Section 5's slice behind the existing `job/start` →
  `job/snapshot` flow, replacing the fakes in `entity_catalog.py`,
  `history_retrieval.py`, `model_provider.py`, and the render step. Keep it one
  packet even if it's larger than your usual — a real seam end-to-end is worth
  more than five flag-storing scaffolds.

---

**One sentence to carry forward:** the scaffolding proved you *can* build this
cleanly; now make it real and let the real recorder, the real model, and a real
chart tell you which of your assumptions were wrong — early, while it's cheap.
</content>
</invoke>
