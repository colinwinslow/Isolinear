# Isolinear — Engineer Onboarding

> Who this is for: a software engineer joining the project cold. It explains what
> Isolinear is, how a request flows through it, the rules you must not break, how
> the architecture got to where it is, and how to actually work in this repo.
> It is a derived guide — decisions live in `docs/decisions/` (ADRs), the current
> architecture map lives in `docs/ARCHITECTURE.md`, and the live project state
> lives in `STATUS.md`/`HANDOFF.md`. When this file disagrees with any of those,
> those win.

---

## 1. What Isolinear is

Isolinear is a **local-first Home Assistant data-analysis assistant**. A user
types a natural-language question into a dashboard card — *"Compare upstairs and
downstairs temperatures over the last 24 hours and mark when the AC was
running"* — and the system answers with a rendered chart PNG **and a grounded
natural-language answer**, computed from the history of Home Assistant entities
the user has explicitly approved.

Everything runs on the user's LAN. There is no cloud dependency: a small local
model (gemma4:e4b-class on an RTX 3060 — the explicit "capability floor" the
design targets) plans the request and writes Python; an isolated Docker worker
executes that Python in a hardened sandbox; the Home Assistant integration
orchestrates everything and owns every safety boundary.

The product identity has evolved (see §5) and its current north star (ADR-0035)
is: **the product is saved, re-runnable, model-authored analysis code**. The
prompt→chart pipeline is the *authoring* flow; a good result can be pinned as a
versioned saved record that the integration refreshes deterministically — with
no model call anywhere in the refresh loop.

The engineering rule of thumb, from the README:

> The model may infer, propose, and explain. The product constrains, validates,
> logs, and asks for user confirmation when ambiguity matters.

---

## 2. The four moving parts

| Part | What it is | Where it runs |
|---|---|---|
| **HA integration** (`custom_components/isolinear/`) | The orchestrator. Owns entity access, the allowlist, model calls, history retrieval, validation, semantic memory, artifact serving, and all state. | The Home Assistant box (10.0.1.200), installed via HACS |
| **Dashboard card** (`frontend/`) | A TypeScript Lit custom element (`custom:isolinear-card`). A strictly thin client: it talks *only* to versioned integration WebSocket commands (`isolinear/v1/*`). It never holds tokens, never calls the worker or model, never reads history. | The user's browser, bundle served by the integration |
| **Worker** (`worker/`) | A self-contained, HA-agnostic HTTP service that executes model-generated matplotlib code in a hardened sandbox. It never holds an HA token, never queries HA, and has no model client. | Docker on CT106 (10.0.1.46:8080), bearer-token auth |
| **Model provider** | Pluggable: Ollama-native (`/api/chat`) or OpenAI-compatible via a LiteLLM proxy (`/v1/chat/completions` — the current default, ADR-0037). Roles: planner, entity selector, codegen, repair. | Ollama on CT103 (10.0.1.39:11434, GPU tier); LiteLLM proxy on CT106 (:4000) |

The split exists for one reason (ADR-0001): risky generated code runs where HA
tokens, secrets, and internal APIs **do not exist**.

---

## 3. The spine: one request, end to end

This is the flow to hold in your head (the authoritative version, with ADR
citations, is in `docs/ARCHITECTURE.md`):

1. **Card → `isolinear/v1/job/start`** (WebSocket). Returns a `planning`
   snapshot immediately; everything after is observed by snapshot polling. The
   card streams the model's live reasoning trace as wait feedback while it
   polls (ADR-0025/0026).

2. **Entity resolution** (`entity_resolution.py`). Saved semantic aliases are
   injected; a deterministic specificity ranking (D1) tries to resolve the
   prompt; residual ambiguity goes to a model `select_entity` pass (D2) that
   chooses **only among approved, disclosed entities**. Genuine ambiguity
   produces a clarification question in the card — never a silent guess.

3. **Planning** (`planning_pipeline.py` + `model_provider.py`). The model
   produces a ChartSpec — which today is an **intent contract**, not a render
   contract. The render family (line vs timeline) is routed deterministically
   from entity kind *before* planning; the model never picks `chart_type`.
   Units are overwritten from the entity catalog after planning. A bounded
   re-plan loop retries recoverable output-quality failures.

4. **History retrieval** (`history_dispatch.py` → `history_retrieval.py`).
   Tiered by window: raw recorder states (short windows), hourly statistics
   (≤60 days), daily statistics (longer) — never stitched, provenance always
   recorded. The model resolves the time window from language; a deterministic
   clamp gate validates it.

5. **Codegen** (`model_provider.py`). The prompt contains the **user's actual
   request text** (ADR-0034 — load-bearing; without it every analysis prompt
   collapsed to a raw plot), the ChartSpec as intent, a bounded 12-point
   preview of the real data, and precomputed overlay bands. Timestamps cross
   this boundary as **epoch-ms integers only**, never ISO strings.

6. **Sandbox execution** (`worker/`). The worker runs the generated code in a
   `python -I` subprocess behind a static AST safety check (re-run on **every**
   attempt, including repairs), an import allowlist, a runtime audit hook, a
   memory cap, a timeout, and a fixed output path. The repair loop
   (code + stack trace → model → minimal fix) lives integration-side and is
   capped.

7. **Answer grounding** (`answer_grounding.py`). The generated code computes
   *and formats* the answer — every number in `answer_text` comes from an
   f-string over a computed variable, and the code emits a **claims ledger**
   that the integration recomputes deterministically before serving. A broken
   claim goes to repair, then to withhold/caveat. Isolinear never serves a
   wrong number as fact.

8. **Serve** (`artifact_serving.py`). The PNG is written as an
   integration-owned artifact, served at `/api/isolinear/artifacts/<id>.png`;
   the snapshot carries the URL (never base64). The card draws the legend
   itself from a renderer-emitted color manifest (ADR-0027).

**Fallback:** any codegen failure — no worker, unhealthy worker, repair
exhaustion, context overflow — falls back to the trusted in-process Pillow
renderer (`in_process_renderer.py`). The fallback is always **surfaced** in
metadata (`render_path` / `render_fallback_reason`), never silent.

---

## 4. The invariants (do not break these)

`CLAUDE.md` lists nine load-bearing invariants; every diff is checked against
them. Abbreviated (read the full text before your first change):

1. **The entity allowlist is absolute** (ADR-0003/0024). The model only ever
   sees explicitly approved entities; off-allowlist references fail closed
   regardless of model confidence; ambiguity clarifies, never guesses.
2. **No HA mutation** (ADR-0008). The MVP is read-only. The one narrow
   exception: Lovelace resource-metadata writes for card registration
   (ADR-0013).
3. **Sandboxed execution** (ADR-0008). Generated Python never has HA tokens,
   secrets, network, or arbitrary filesystem access.
4. **Schema validation first** (ADR-0005). All major data validates against
   `docs/schemas/` before render or storage.
5. **Deterministic plan validation** (ADR-0006). Invalid or hidden-entity plans
   return a clear failure, never a render attempt.
6. **Codegen-primary, fallback-safe rendering** (ADR-0030). Fallback to Pillow
   is surfaced, never silent; static safety checks run on every attempt.
7. **Semantic memory is deterministic** (ADR-0009). Alias invalidity is
   computed at use time; invalid aliases never silently reuse.
8. **No silent architecture decisions**. New services/databases/frameworks
   require an ADR before implementation.
9. **Deterministic render-family routing** (ADR-0022). Family comes from entity
   kind before planning; the model never chooses `chart_type`.

Two more rules that function like invariants in practice:

- **Grounding is non-negotiable** (ADR-0031): `answer_text` only ever comes
  from executed code. A repair-exhausted analysis prompt degrades to a raw
  chart — it never fabricates an answer.
- **The design seam** repeated across ADR-0023/0024/0027/0028/0031: the
  integration owns the deterministic capability/safety envelope; the model owns
  intent and language judgment *within* it; out-of-envelope model output fails
  closed. When you're unsure who should own a new behavior, this seam is the
  tiebreaker (and the standing steer is to lean on the model within it).

---

## 5. How the architecture got here (the arc)

You will read old ADRs and old code. This narrative keeps you from building on
residue. Most ADRs are accepted-and-immutable history — 0004 is superseded, 0015/0016
are deprecated (all three archived), and the earliest few carry no status
frontmatter at all. `docs/ARCHITECTURE.md` is the current-state map.

**Era 1 — Scaffold-first (ADR-0001…0016, mid-2026-05→06).** The repo was
deliberately seeded with ADRs, specs, BDDs, schemas, and evals *before*
production code. The four-part topology, the allowlist, schemas, validation
layers, semantic memory, the Lit card, and the worker transport were all
designed here. Cautionary tale: ADR-0015/0016 built durable worker
health-polling and token-lifecycle machinery ahead of need — ~3.1K LOC later
deleted wholesale (ADR-0032). Both are archived.

**Era 2 — The reality pivot (ADR-0017…0028, 2026-06).** The first *real*
vertical slice (ADR-0017) deferred the worker and rendered in-process, which
forced matplotlib→Pillow (matplotlib cannot install into HA's Python —
ADR-0019) and exposed a stream of real-data problems that scaffolds never
would: model-resolved time windows (0020), tiered history vs recorder retention
(0021), kind-based family routing (0022), the capability-envelope seam (0023),
model-driven entity selection (0024), live reasoning feedback (0025/0026), the
card-owned legend (0027), composition membership (0028).

**Era 3 — The codegen inversion (ADR-0029…0034, 2026-07).** The worker was
revived as an explicit experiment with a kill condition (0029); the eval showed
~94% accept-with-repair, so the architecture inverted: **sandboxed matplotlib
codegen became the primary render path and Pillow the surfaced fallback**
(0030, superseding 0004). The hand-grown ChartSpec `transform` enum had become
the flexibility ceiling; now renderer capability grows with the model. 0031
expanded the identity from charts to *answers* (model-authored analysis + the
grounding check); 0034 closed the loop by putting the user's request text into
the codegen prompt — before that, the model writing the code never saw the
question, and every analysis prompt collapsed to a raw plot.

**Era 4 — The v0.3 north star (ADR-0035…0037, current).** 0030+0031+0034
converge on "the code IS the product": ADR-0035 defines the saved-viz record
(saved code + entities + relative window) with a **model-free refresh loop**
(re-validate allowlist, re-resolve window, re-fetch, re-run static checks +
sandbox + grounding on every refresh), and attaches a sequenced demolition
plan. Step 1 (splitting the 8.3K-line `job_orchestration.py` god module into
seven seam modules) landed in 0.2.28. 0036 bakes a trusted
`isolinear_analysis.align()` helper into the sandbox because floor models
reliably fumbled the ~900-char alignment idiom. 0037 added the
OpenAI-compatible/LiteLLM provider (now the default transport).

**Things that look current but aren't** (see `docs/ARCHITECTURE.md` "Not
current architecture"): ChartSpec's render-side surface, the Pillow
histogram/aggregate families and the ADR-0023 envelope machinery (demolition
step 4), the `first_real_vertical_slice` flag (step 2), and the
`output_modality` planner signal (parked).

---

## 6. Code map

### `custom_components/isolinear/` — the integration

The ADR-0035 step-1 split imposed a **strict downward-only import layering**
(seam modules never import the facade):

- **L3 facade — `job_orchestration.py`** (~2.7K lines): setup/gates, the five
  WS handlers, pipeline drivers, response envelopes, and a labeled compat
  re-export block (~51 symbols kept so tests/evals can keep importing from it;
  production code uses only ~8).
- **L2 — `render_dispatch.py`** (codegen loop, bounded repair, grounding gate,
  worker dispatch, surfaced Pillow fallback, overlay bands),
  `planning_pipeline.py` (plan gates + bounded re-plan loop).
- **L1 — `snapshot_assembly.py`** (validated snapshot appenders, fail-closed
  failure sanitizers), `history_dispatch.py` (window resolution, tiering,
  epoch-ms boundary), `entity_resolution.py` (allowlist seam: aliases, D1/D2,
  family routing).
- **L0 — `orchestration_contracts.py`** (the 13 JSON-Schema contract
  validators), `orchestration_store.py` (validated record writers, snapshot
  lock, live-reasoning slots).

Around the seams: `model_provider.py` (largest module — both provider clients
and all prompts; the floor-model discipline lives here), `history_retrieval.py`,
`in_process_renderer.py` (Pillow fallback), `answer_grounding.py` (claims
ledger + deterministic checks), `websocket_api.py`, `entity_catalog.py`,
`semantic_memory.py`, `config_flow.py`, `artifact_serving.py`,
`dashboard_resource.py`, plus `schemas/` (the bundled JSON Schemas) and
`frontend/dist/isolinear-card.js` (the shipped card bundle).

### `worker/` — the sandbox service

`isolinear_worker/codegen_sandbox.py` is the sandbox: schema-validate inputs →
static AST check (exactly one `render_chart(data, output_path)`; top level =
imports + defs only) → import allowlist → curated builtins (no
`getattr`/`eval`/`type`) → `python -I` subprocess with stripped env → runtime
audit hook → timeout + resource limits → output-size check.
`isolinear_worker/http_server.py` speaks the ADR-0012 transport
(`POST /v1/render`, `GET /v1/health`, bearer auth, fails closed with no token).
`isolinear_analysis/` is the trusted helper library generated code may import
(ADR-0036) — **additive-only API; breaking a signature requires a new ADR**,
because saved ADR-0035 code will depend on it.

Build: `docker build --platform linux/amd64 -t isolinear-worker:dev worker/`.
Dependencies (matplotlib, **pandas 2.x**, scipy, seaborn) go into *system*
site-packages because `-I` excludes user site. The homelab repo owns the
compose/IaC; worker rebuilds are independent of HACS ships.

### `frontend/` — the card

Lit 3 + TypeScript + Vite; Vitest/happy-dom tests; a browser harness with a
fake `hass` and fixture snapshots so you don't need live HA. After
`npm run build`, the bundle must be copied to
`custom_components/isolinear/frontend/dist/` — the HACS-shipped copy. **This
copy step is the most-forgotten step in the repo.**

### `tests/`, `evals/`, `bdd/`

- `tests/`: ~24 pytest files, ~595 tests, one file per spec/packet.
- `evals/`: ~28 standalone gate scripts proving specific behaviors, plus the
  flagship `e2e_pipeline_harness.py` — drives the **real** pipeline (live HA,
  live worker, live model) via the same WS commands the card uses, over a fixed
  prompt set, capturing PNGs + metadata per run. Deliberately no programmatic
  pass/fail: past regressions "rendered successfully," so the PNGs are visually
  judged and verdicts written to a `REPORT.md`. This harness is the standing
  accept gate for pipeline changes and for ADR-0035 demolition steps.
- `bdd/` + `docs/bdd/`: Gherkin `.feature` files define contracts; per-feature
  folders under `bdd/` hold markdown **evidence files** recording real observed
  proof for human review.

---

## 7. How work happens here

This project is developed **agentically**: the human (Colin) provides direction
and oversight; the agent implements. Review happens by reading commits, ADRs,
specs, and evidence. `CLAUDE.md` is the working contract — read it in full.

The engineering sequence for any slice:

1. **ADR** (if an architecture decision is needed — invariant #8) →
2. **Spec** (`docs/specs/`, contract + observable behavior) →
3. **BDD** (scenarios pinning "done" + evidence scaffold) →
4. **Red-green TDD** (anchor artifact first, supporting code second) →
5. **Eval** (deterministic proof scripts).

Key disciplines:

- **Anchor artifact first**: build the simplest concrete observable version of
  the thing before any plumbing. If you're building infrastructure before
  anything visible exists, stop and reorder.
- **Verify on disk**: a slice isn't done until the real artifact is read back
  and confirmed. "Tests pass" is necessary, not sufficient.
- **Reproduce live before fixing**: the project's recent history is full of
  packets whose premise was overturned by a live repro (see STATUS). Verify
  render/answer bugs against the real pipeline, not synthetic simulations.
- **ADRs are immutable once accepted**: to change a decision, write a new ADR
  with `supersedes:` frontmatter.

Session mechanics: `/startup` (reads `STATUS.md` + `HANDOFF.md`, identifies the
next bounded packet), `/closeout` (updates the rolling log, syncs doc indexes,
runs review passes, commits), `/adr`, `/spec`, `/research` scaffolds. Two
review passes: a fresh-context **architecture review** subagent before
completing non-trivial work, and a **BDD-evidence review** after test runs.

Commit norms: one commit per coherent change, message says *why*; `[ADR-NNNN]`
/ `[spec:<feature>]` prefixes; bump the patch version in both `manifest.json`
and `const.py` for every completed implementation packet; stage specific files
(never `git add -A`); ask before pushing.

## 8. Build, test, deploy

```bash
# Integration (repo root)
python3 -m pytest tests/                 # full unit suite
python3 evals/<gate>.py                  # a single eval gate
python3 scripts/ha_token.py --check      # verify the HA token before any live run
python3 scripts/ha_token.py -- python3 evals/e2e_pipeline_harness.py   # live e2e

# Card (frontend/)
npm test && npm run build
# then copy frontend/dist/isolinear-card.js → custom_components/isolinear/frontend/dist/

# Worker image
docker build --platform linux/amd64 -t isolinear-worker:dev worker/
```

**Where the HA token lives.** Nothing in this repo persists an HA credential — the
harness, the eval gates and `scripts/ha_logs.py` all read `HA_TOKEN` from the
environment at run time. The real value is age-encrypted in the homelab vault at
`~/repos/homelab/secrets/ha-access.enc.yaml`; `scripts/ha_token.py` decrypts it
in-process and injects it into a child command, so the plaintext never reaches a
shell variable or your scrollback. Run `--check` first — it verifies the token
against a bogus-token negative control and prints the expiry (currently
**2027-07-31**). A bare `401` from any live script almost always means a rotated
token, not a broken integration; that mistake cost a mid-run e2e harness on
2026-07-31.

Deploy: the integration ships via HACS (push → **Redownload** in HACS →
restart HA); the Lovelace resource URL is version-stamped so browsers don't
load stale bundles. The worker deploys separately to CT106 via the homelab
repo's compose (GHCR image, digest-pinned continuous deploy). Endpoints + tokens are configured in the integration's options
flow (ADR-0032/0037 posture: secrets are deployment-supplied, write-only
fields, stored in HA Stores, never in config-entry data, never echoed).

---

## 9. Gotchas that have actually bitten

- **The schema-copy trap**: a new field on a contract (e.g. `render_chart`
  metadata) must be added to *every* schema copy **and** the worker's
  normalizer, or it is silently dropped — which also means a worker image
  rebuild.
- **Epoch-ms only at the data boundary**: raw ISO timestamp strings destroyed
  ~19/28 benchmark runs via a pandas `to_datetime` format-inference trap
  (ADR-0031 D9).
- **`history_series` is the sole data authority** for generated code; the
  ChartSpec is intent/metadata only — codegen must never read data, units, or
  the series list from it (ADR-0034).
- **"Custom element doesn't exist: isolinear-card"** is usually a stale browser
  cache, not a deploy failure. Conversely, the HACS update entity can lie about
  what's deployed — verify live code, don't trust the badge.
- **Pandas version drift**: the worker pins pandas 2.x; local exec harnesses
  drifting to pandas 3.x turned real behavior into spurious errors. Use the
  faithful exec env when reproducing sandbox behavior.
- **A claimless answer grounds as `pass`**: if generated code emits no claim,
  nothing is verified and the answer is served uncaveated — emission gaps and
  recompute gaps are different bugs; diagnose which one you have.
- **Withheld ≠ no answer**: a grounding-WITHHELD result looks identical to a
  plot-only response in the card. Check the grounding outcome before assuming
  the model didn't answer.
- **Frontend bundle copy** (again, because it's the one everyone forgets): the
  card the user loads is the copy under `custom_components/`, not
  `frontend/dist/`.

---

## 10. Where the project stands (as of 2026-07-29, v0.2.47)

Version 0.2.47 (the cross-sensor smoothed-average emission fix) is pushed and
live-deployed; the suite is at 591 passing / 4 skipped. The current work theme
is hardening the *answer channel* — a run of packets fixing emission and
grounding for multi-sensor math (delta, pearson, rolling means) — plus
executing the ADR-0035 demolition steps, of which step 1 is done and 2–5
remain. Live gaps are tracked in **`ROADMAP.md`**; the headline ones are the
>2-day overlay tiering wall and the inert context-overflow detector on the
LiteLLM path. Binary/timeline codegen rendering, which was a long-running gap,
is closed and live-confirmed. Check `STATUS.md` for the live picture; this
paragraph ages.

## 11. Suggested first-day reading order

1. This file.
2. `CLAUDE.md` — the working contract and the nine invariants, in full.
3. `docs/ARCHITECTURE.md` — the current-state map with ADR citations.
4. The four pivotal ADRs: **0030** (codegen primary), **0031** (model-authored
   analysis + grounding), **0034** (the request reaches codegen), **0035**
   (the v0.3 north star + demolition plan).
5. `docs/gotchas.md` — the traps that have actually cost sessions. Section 9
   above is a curated subset; that file is the full set.
6. `docs/specs/product-spec.md` and `docs/specs/worker-sandbox-spec.md`.
7. `STATUS.md` top entry + `HANDOFF.md` "Current project phase" + `ROADMAP.md`
   — the live state and what's queued.
8. Skim `evals/e2e_pipeline_harness.py` and one recent `evals/e2e_runs/`
   REPORT to see what "proof" looks like here.
