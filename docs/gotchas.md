# Operational gotchas — hard-won knowledge

> **Why this file exists.** These are facts that cost a debugging session to
> learn and are **not recoverable from the code, the ADRs, or the specs**. They
> were rescued from `HANDOFF.md`'s session history during the 2026-07-28
> continuity trim, before that history was dropped to git.
>
> This file is **not** always-loaded — read it when you're debugging in the
> relevant area, or when a symptom below matches. Add to it whenever a session
> burns time on something a future reader couldn't have known.

## Model / prompt behavior

- **The planner samples at temperature 0, so a plain "re-sample" is
  byte-identical** (proven 3/3 live). The 0.2.25 re-plan loop was a live no-op
  *whose unit tests passed*, because stub planners vary where greedy gemma does
  not. Re-plan attempts now pass temperature 0.7. **Lesson: a stub-backed test
  cannot prove a resampling loop works.**

- **Ollama truncates an over-long prompt from the FRONT**, evicting the system
  prompt and rules — so gemma answers with prose analysis, emits no code fence,
  and you get `syntax_error@L1`. Repair never recovers, because the repair
  prompt is bigger still. Ollama caps `prompt_eval_count` at exactly `num_ctx`
  when it truncates, which is why `prompt_eval_count >= num_ctx` is a
  definitive overflow signal.

- **"The repair prompt is bigger still" was literally true, and cost ~7 of 21
  e2e prompts for weeks** (found 2026-08-07, fixed in 0.2.48). Generation fit
  the window at 58–79%; every repair hit `prompt_eval_count == 8192` exactly.
  The failure does not look like truncation — it looks like *model
  incompetence*: attempt 1 produces real code with a real bug, then every
  repair returns textbook boilerplate with fabricated data (`np.random.seed(42)`,
  `pd.date_range(start='2023-01-01')`, `_mock` arrays) and fails the static gate
  as `unsafe_code`. **If you see mock data in generated code, suspect prompt
  budget before suspecting the model.** Fix: `_repair_prompt_rules` prunes the
  rules to the failure class. Prompts that succeed on attempt 1 were never
  affected, which is why the suite looked merely "flaky" rather than broken.

- **Never size a prompt budget with a chars/token estimate.** The usual 4.0
  ch/tok rule of thumb under-counts this repo's dense JSON payloads by ~30%:
  measured ratios are **2.41–3.51 ch/tok**, and the JSON-heavy repair payload
  sits at the low end. That gap is exactly the margin between "85%, tight" and
  "100%, truncated" — an estimate said the repair prompt fit when it did not.
  Use `scripts/measure_codegen_prompt.py` with `LIVE_TOKENS=1`, which asks the
  real tokenizer via a `num_predict=1` call and reads `prompt_eval_count`.

- **The 12-point preview count is experimentally derived — do not shrink it.**
  Summary-only = 1/3 grounded (2/3 empty plots); 6 points = 6/6; 12 points =
  6/6 at ~3.2K tokens; 40 points = 6/6 but ~6.2K tokens. For the floor model,
  removing all concrete data trades an overflow problem for an empty-plot drift
  problem.

- **`chart_spec` is a trap for the codegen model.** Its `unit` is
  planner-hallucinated, and its series are keyed by `series_id` /
  `source.entity_id` with no top-level `entity_id`. The `PlannerResult` schema
  still *requires* a per-series `unit` the planner has no way to know;
  `_apply_catalog_units` overwrites it after validation, but the schema wart
  remains.

- **Prompt-rule discipline (standing agreement with Colin):** contract rules
  stay permanently; failure-driven *style hints* must earn their accept-rate in
  an eval or be retired. This is the statement of record for that principle.

- **Grounding's event-anchor re-detection (ADR-0031 D8a §1a / packet 4d) has
  never been exercised.** The floor model records absolute `{start, end}`
  bounds even with the anchored form documented in the prompt. Open, and
  explicitly not a defect — it needs a harder prompt or a stronger model.

- **A single global `_TOLERANCE = 0.05`** spans correlation, means, and
  hour-counts. Arch review called this accepted tranche-1 coarseness, not a
  violation. Only `state_duration` has a metric-aware relative tolerance
  (added 0.2.45).

- **The GPU has almost no headroom** (measured 2026-07-16 on the RTX 3060
  12 GB, not re-verified since — treat as an order-of-magnitude fact, not a
  spec). gemma4:e4b at `num_ctx=8192` ≈ 10.69 GB (weights ~9.6 GB fixed, KV
  ~1.1 GB scaling with context); Frigate baseline ≈ 1.6 GB → ~11.4 GB resident
  with ~500 MB spare. This is why Ollama pins `OLLAMA_MAX_LOADED_MODELS=1`:
  loading a second model OOMs Frigate. It is also why concurrent e2e prompts
  intermittently fail under load and then pass in isolation — that is GPU
  contention, not a defect.

- **Never rename a model-emitted metric name to force a registry match.** An
  honest-but-unregistered metric landing in the caveat box is *correct*
  behaviour per ADR-0031 D3. Renaming it to hit the registry fabricates a
  `value_mismatch` against a quantity the model never claimed. Raising the
  verified-rate is done by fixing emission or adding a real recompute, never by
  relabelling.

## Data / history

- **Catalog `unit_of_measurement` is snapshotted at catalog-build time.**
  Cloud-integration entities (the ecobees) are `unavailable` right after an HA
  restart, so the catalog caches `null` and you get "Value ()" axes.
  `backfill_catalog_units_from_state` patches from live state in *both*
  `_approved_catalog_items` copies — but **a catalog built during a restart
  window is still the first thing to suspect.**

- **`_read_via_recorder_executor` bounces recorder reads through
  `asyncio.run_coroutine_threadsafe(...).result(timeout=60)`.** This is only
  sound because job orchestration runs synchronously on a general-executor
  worker thread, distinct from both the event loop and the recorder executor.
  **If orchestration ever moves onto the event loop, this deadlocks.** Its
  real-HA leg is `# pragma: no cover`.

## Worker / sandbox / deploy

- **A raise anywhere in the worker's own response-validation path becomes an
  HTTP 500**, which the integration classifies as an unrepairable *transport*
  fault → immediate Pillow fallback with **zero** repair attempts. Anything new
  on that path must degrade inside the 200 flow, never raise.

- **Sandbox tracebacks exist only in `docker logs isolinear-worker`** on the
  worker host. They never reach the HA logs.

- **The compose `tmpfs` for `/var/lib/isolinear-worker/work` mounts
  `root:root` and overrides the Dockerfile's chown** while the container runs
  as uid 10001 → `PermissionError` on `fig.savefig`. It needs
  `uid=10001,gid=10001` in the tmpfs options. Fixed live and in the homelab IaC
  template (homelab `4e80bbc`) — **a fresh deploy anywhere else will hit it
  again.**

- **The worker image has no version identity.** It was long carried as `:dev`
  and never bumped, so HA and the worker image can drift out of lockstep
  invisibly. Corollary that still bites when using a mutable tag: rebuilding
  the same tag requires a manual
  `docker compose up -d --force-recreate isolinear-worker` — compose will not
  re-read an unchanged tag. (Since 2026-07 the service runs the GHCR image with
  a pinned digest via the homelab continuous-deploy path, which is what fixes
  this properly.)

- **The worker orders every request auth → api-version → schema.** An
  authenticated but version-less health call returns 400, not 200.

- **`worker/Dockerfile` does not digest-pin `python:3.12-slim`** — flagged as
  worth doing, never done.

- **Reading the real worker token:** Colin has key-only root SSH to the worker
  host and reads it himself via
  `docker exec isolinear-worker env | grep ISOLINEAR_WORKER_TOKEN`, so it never
  crosses a transcript. That's the route when a repro needs the real token.

## Process

- **The live e2e suite flips ~26% of its prompts run-to-run on UNCHANGED code,
  so a single before/after run proves nothing.** Measured 2026-07-31: two runs,
  same 0.2.47 build, same model, hours apart — 5 of 19 comparable prompts
  changed verdict (e2e-03/09/15/17 passed then failed; e2e-19 the reverse).
  Any A/B (a prompt-rule change, a model swap, a KV-cache quantization) needs
  **≥3 runs per arm**, or it is measuring noise. The reliable technique is to
  decompose instead of averaging: classify each prompt as **always-pass**,
  **always-fail**, or **flipper** across runs, and judge a change only on the
  always-fail set. That is what made the 0.2.48 result legible — the stable-7
  went 0/7 → 6/7 while the headline per-run number (11/21 → 20/21 → 16/21)
  looked like it might be luck. Report **eventual success across passes**, not
  a per-run total.

- **A harness "timeout" is not always slowness — check whether the snapshot
  poll was REJECTED.** On 2026-07-31 e2e-20/21 were logged as 362s timeouts;
  they had actually been refused with
  `code=invalid_integration_model_provider_retry_policy`, so the job was
  unreadable through the card and the harness simply waited it out. The tell is
  in `scripts/ha_logs.py` (a `websocket_api` WARNING naming the rejection code),
  never in the harness output. Same shape as the withheld-vs-no-answer trap:
  distinct causes with identical surface symptoms.

- **The BDD carve-out (applied in ~6 recent packets, written down nowhere
  else).** `CLAUDE.md` states BDD-before-implementation without exception, but
  a **prompt-rule change or a bug fix on an already-accepted contract** ships
  with an eval gate + unit tests *instead of* a BDD, because no user-facing
  contract surface changed. That is the treatment 0.2.40, 0.2.41, 0.2.44,
  0.2.46 and 0.2.47 all received, each recorded as "No BDD (…the gate + unit
  tests are the proof)". Without this written down, the repo reads as violating
  its own contract on its most recent work, and the next session will either
  over-produce BDDs or quietly re-invent the exception. A *new* user-facing
  surface still gets a BDD.

- **The prose → idiom → callable ladder.** Floor models follow idioms, not
  prose. Measured twice: a prose instruction produced the correct alignment
  2/6 times, a literal copyable idiom 9/9, and the no-instruction control 0/6.
  This is the reason ADR-0036 exists — when a prompt rule keeps failing, the
  escalation is to hand the model a copyable idiom, and then to ship that idiom
  as a callable in `isolinear_analysis`.

- **`scripts/ha_logs.py` only reaches WARNING and above**, because HA's
  `system_log` is WARNING+ only. Anything logged at DEBUG or INFO is invisible
  on that path — which is why 0.2.35 had to escalate per-attempt codegen errors
  to WARNING before they could be diagnosed at all. If you're looking for a
  diagnostic and finding nothing, check the level before concluding the code
  path didn't run.

- **The local exec harness cannot reproduce sandbox enforcement.** It matches
  the worker's library versions (use `/home/claude/.workerenv`, pandas 2.x) but
  it does **not** enforce the import allowlist, the audit hook, the write
  restrictions, or the resource limits. A repro that runs clean locally can
  still be rejected by the real sandbox. Only the worker proves sandbox
  behaviour.

- **The `arch-reviewer` subagent does not register in the hosted runtime**
  even though `.claude/agents/arch-reviewer.md` exists and
  `codex/review-architecture.md` names it. In a hosted/web session, run the
  fresh-context architecture review with `subagent_type: general-purpose` and
  point it at the protocol file. It registers normally in a local Claude Code
  session.

## Repo / docs

- **CLAUDE.md's 9 enforced invariants and `docs/ARCHITECTURE.md`'s 12
  "load-bearing decisions" are two separate numbered lists with no
  cross-reference.** Colin's flagged lean: make the 12 an explicit superset
  that cites which rows are the enforced 9. (Tracked in ROADMAP housekeeping.)

- **The word "heatmap" is reserved for the future spatial/floorplan renderer**
  (Colin's "ship simple" ruling). A temporal calendar heatmap, if ever built,
  must become its own named family — never an overload of "heatmap". 0.2.26
  shipped this as a prompt rule only; this is the statement of record.

- **`mixed_chart_composition_unsupported` is dead code.** Since `372a437`
  (2026-06-24) every numeric+state set routes to `time_series_overlay`, so the
  "mixed" family is unreachable through `_resolve_render_family`. Undecided
  whether to delete the defensive gate or keep it documented-unreachable.

- **The definitive planner clarification text is still suppressed on the card**
  — the e2e harness can only capture the streamed reasoning tail. Surfacing it
  is a small unclaimed integration-side follow-up.

- **The re-plan loop has never been observed recovering a real failure live.**
  The e2e-18 duplicate-source tail did not reproduce in 16 production-path
  runs. `evals/planner_replan_live_proof.py` is resumable and will headline a
  live recovery if one ever fires.
