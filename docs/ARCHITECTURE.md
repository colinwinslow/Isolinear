# Isolinear — current architecture (the map)

> **Purpose.** The one-page answer to "where does the architecture stand?" The
> ADR set (`docs/decisions/`) is an append-only *history*; this file is the
> *current state* — the spine, the decisions that are load-bearing today, and
> what's fallback or slated for demolition. Update it at `/closeout` whenever
> an ADR changes the architecture. If this file and an ADR disagree, the newer
> one wins and the older one has a bug — fix it.
>
> Last synced: **2026-07-07** (through ADR-0035 step 1 — the
> job_orchestration split, 0.2.28).

## What Isolinear is

A local-first Home Assistant **data-analysis assistant**: natural-language
prompts become sandboxed, model-authored Python that renders a chart PNG and a
grounded natural-language answer from approved HA entity history (ADR-0031).
Everything runs on the user's LAN: the HA custom integration orchestrates; a
small local Ollama model (gemma4:e4b-class) plans and writes code; an isolated
Docker worker executes that code in a hardened sandbox. Read-only, allowlisted,
fail-closed (ADR-0008).

## The spine (one request, end to end)

```
card (Lit, isolinear-card.ts)
  │  WS: isolinear/v1/job/start → job/snapshot polling          [0002, 0011, 0026]
  ▼
entity resolution — entity_resolution.py (driven by the job_orchestration.py facade)
  │  alias injection → D1 deterministic specificity → D2 model
  │  select_entity → clarification card; composition prune       [0003, 0024, 0028, 0009]
  ▼
planning — model_provider.py (plan_chart, two-pass streaming)
  │  ChartSpec = intent contract (family/envelope pinned by
  │  entity KIND before planning; model never picks chart_type)  [0022, 0023, 0025]
  │  units overwritten from catalog after planning (never model) [0031/15th]
  │  bounded re-plan loop on recoverable output-quality gates
  │  (default ON, fresh-sample temp 0.7 on retries; never
  │  re-plans a clarify)                    [spec:planner-replan/18th–20th]
  ▼
history retrieval — history_retrieval.py
  │  tiered: recorder raw (≤2d) | long-term statistics; unit
  │  backfill from live state                                    [0021, 0020]
  ▼
codegen — model_provider.py (generate_chart_code / repair_chart_code)
  │  prompt = user_request + task + rules + chart_spec(intent) +
  │  history_series PREVIEW (12 real pts, runtime key 'points') +
  │  precomputed overlay bands; epoch-ms only, never raw ISO     [0034, 0031, 0033, 0030]
  ▼
worker sandbox — worker/ (HTTP, CT103), render_mode: codegen
  │  static safety check EVERY attempt → -I subprocess, import
  │  allowlist, audit hook, 1024MB, fixed output path; repair
  │  loop lives integration-side (worker never holds a model)    [0008, 0029, 0030, 0012, 0032]
  ▼
grounding check — answer_grounding.py
  │  claims ledger recomputed deterministically before serve;
  │  broken answers → repair loop → withhold/caveat, never serve
  │  a wrong number                                              [0031 D8a]
  ▼
serve — artifact_serving.py → snapshot → card                    [0018, 0027]
```

**Fallback:** any codegen failure (unhealthy worker, repair exhaustion,
context overflow) falls back to the trusted Pillow renderer
(`in_process_renderer.py`), always **surfaced** via
`render_path`/`render_fallback_reason`, never silent (ADR-0030, invariant #6).

## Load-bearing decisions (what you must not break)

| # | Decision | ADR |
|---|---|---|
| 1 | Entity allowlist is absolute; ambiguity → clarification, never a guess | 0003, 0024 |
| 2 | Read-only MVP; generated code runs only in the sandbox, no HA tokens/secrets/network | 0008 |
| 3 | Schema-first: all major data validates against `docs/schemas/` before render/storage | 0005, 0006 |
| 4 | **Codegen is the primary render path; Pillow is the surfaced fallback** | 0030 |
| 5 | The data boundary: worker never queries HA or holds a model client; only validated, allowlisted, normalized data crosses; repair loop is integration-side | 0029, 0030 |
| 6 | Model-authored analysis: generated code computes AND formats answers (f-string over computed variables); claims ledger recomputed deterministically before serve | 0031 |
| 7 | **The user's request reaches the codegen model** (`user_request` in generation/repair prompts only — not the worker dispatch); plot-raw-series is the default with a compute-the-derived-series exception | 0034 |
| 8 | Render family routes deterministically from entity KIND before planning; binary/categorical → timeline/step, never numeric lines | 0022, 0023 |
| 9 | Floor-model grounding discipline: epoch-ms timestamps only (D9); bounded 12-point preview under the runtime key `points`; `history_series` is the sole data authority; units from catalog + live-state backfill, never model-guessed | 0031 + 14th/15th sessions |
| 10 | State overlays are integration-precomputed bands (`derived_intervals`); the model draws them, never derives them | 0033 |
| 11 | Semantic aliases are deterministic, validated at use-time, never silently reused when invalid | 0009, 0010 |
| 12 | Worker auth is a deployment-configured static bearer token (SOPS → compose → paste into options); no runtime token lifecycle machinery | 0032, 0012 |

## Component map (weight-honest)

| Component | Lines | Role |
|---|---|---|
| `job_orchestration.py` | 2.7K | **The orchestrator (facade)** — setup/gates, the five WS handlers, deferral + pending-selection, the pipeline drivers, response envelopes, and a labeled compat re-export block (tests/evals import moved names here; trim under ADR-0035 step 2+). ADR-0035 step 1 (0.2.28) split the former 8.3K god module into the seven seam modules below; imports flow strictly downward. |
| `render_dispatch.py` | 2.1K | How a validated plan becomes a PNG (invariant #6's seam): codegen loop + bounded repair + grounding gate, chart-spec worker dispatch, surfaced Pillow fallback, worker artifact/progress recording, ADR-0033 overlay bands, artifact-metadata builders, transport classification + retry policy |
| `snapshot_assembly.py` | 1.0K | The validated-snapshot appender family (failure/progress/clarification/complete), failure-message composers, fail-closed failure-code/text sanitizers, artifact presentation glue |
| `entity_resolution.py` | 0.9K | Invariant #1's seam: alias injection, D1 specificity scoring, D2 selector + ADR-0024 expansion + ADR-0028 composition prune, ADR-0022/0023 family/envelope routing + overlay composition |
| `orchestration_store.py` | 0.7K | Validated-record writers/removers/rollback, per-job lookups + snapshot lock, ADR-0025 live-reasoning slots + degrading model-call plumbing, side-effect envelope |
| `planning_pipeline.py` | 0.7K | `_plan_once` (contract/family/allowlist gates + catalog-unit overwrite) + the bounded re-plan loop (fresh-sample temperature) + planner request/record builders |
| `orchestration_contracts.py` | 0.6K | The 16 JSON-Schema contract validators + structural entity-reference checks + schema paths (invariants #4/#5) |
| `history_dispatch.py` | 0.3K | Window resolution, tiered-retrieval wrapper, D9 epoch-ms boundary transforms |
| `model_provider.py` | 1.6K | Ollama client: planner (two-pass streaming) + entity selector + codegen/repair prompts (the floor-model discipline lives here) |
| `history_retrieval.py` | 1.3K | Tiered history (recorder/statistics), unit backfill |
| `in_process_renderer.py` | 1.3K | Pillow fallback renderer (time_series/timeline/histogram/aggregate + overlay regions) |
| `websocket_api.py` | 0.9K | The card's WS command surface |
| `answer_grounding.py` | 0.7K | Claims registry + 6-step deterministic check + event anchors |
| `entity_catalog.py` | 0.7K | Allowlist → catalog snapshot |
| `semantic_memory.py` + storage | 0.6K | Alias store (HA Store envelope) |
| `worker/` | 1.9K | Self-contained HA-agnostic sandbox + HTTP server + Dockerfile |
| `frontend/isolinear-card.ts` | 1.0K | Lit card: streaming reasoning, legend, answer, clarifications |
| Everything else | ~2.5K | config flow/schema, artifact serving, job state, health, resource registration |

## Deployment topology

- **HA box (10.0.1.200):** the integration, via HACS (repo → Redownload → restart; HACS tracks commit SHA). Card bundle ships inside the integration.
- **CT103 (10.0.1.39):** Ollama (`:11434`, gemma4:e4b) + `isolinear-worker:dev` compose service (`:8080`, bearer-token; homelab repo owns the compose/IaC). Worker image rebuilds are independent of HACS ships.
- Endpoints + token configured in the integration's options flow (ADR-0032).

## Not current architecture (don't build on these)

- **ChartSpec as the render contract** — it survives as the *planning/intent*
  contract only; codegen is told it's "intent/metadata only — never read data,
  units, or the series list from it" (ADR-0034). Its render-side surface
  (render_as, envelope widening) is early-era residue.
- **Pillow render families** (histogram/aggregate envelope, ADR-0023) — live
  as fallback + the two-family capability envelope, but the design center has
  moved to codegen-authored presentation; expect demolition under the v0.3
  direction (ADR-0035, forthcoming).
- **`first_real_vertical_slice` gating** (ADR-0017) — a completed milestone
  whose flag still threads the facade + render/history dispatch (~19 refs); demolition target (ADR-0035 step 2).
- **`output_modality` planner signal** (ADR-0031 packet 5) — parked; redundant
  now that codegen reads `user_request` directly (ADR-0034).
- Archived outright: 0004 (trusted-renderer default), 0015/0016 (worker
  durability machinery) — see `docs/decisions/archive/`.

## Known live gaps (open queue, STATUS.md)

Binary/timeline entities render empty through codegen (r); >2-day state
overlays hit the single-source tiering wall (t); histogram axis-unit placement
(s); `max_codegen_repair_attempts` default still 1 (m). The live e2e harness
(`evals/e2e_pipeline_harness.py`, Claude-judged) is the standing accept gate
for pipeline changes.
