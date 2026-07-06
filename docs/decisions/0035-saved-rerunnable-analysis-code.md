---
id: 0035
title: "v0.3 north star: the product is saved, re-runnable analysis code — plus the demolition plan"
status: accepted
date: 2026-07-06
supersedes: []
superseded-by: null
tags: [direction, saved-viz, refresh, demolition, v0.3]
---

# ADR-0035: v0.3 north star — the product is saved, re-runnable analysis code

## Context

Sixteen sessions of live-fire iteration have moved Isolinear's design center
three times: schema-rendered charts (ADR-0004 era) → codegen-primary rendering
(ADR-0030) → model-authored analysis with grounded answers (ADR-0031) → the
user's request as the codegen contract (ADR-0034). Each pivot left residue the
next one built around: a 8.2K-line orchestration god module, Pillow render
families serving a superseded design center, a completed-milestone flag
(`first_real_vertical_slice`, ADR-0017) still threading the orchestration, and
ChartSpec ceremony that codegen is now explicitly told to ignore.

Meanwhile the question "if we rebuilt from scratch, what would Isolinear BE?"
has a crisp answer (Colin, 17th session): **a small-LLM data analyst whose
product is Python code the user can save and re-run on demand in the worker
sandbox without re-engaging the model.** That is open-queue (l)'s "saved live
visualizations" stub — promoted from a parked feature to the organizing
principle. This ADR makes that promotion explicit and attaches the demolition
plan that a ground-up rebuild would otherwise be needed for. (The rebuild
alternative was considered and rejected the same session: it would forfeit the
437-test regression net woven from live failures, re-type the HA plumbing
unchanged, and freeze the live instance for many sessions — while the parts a
rebuild would keep verbatim, the sandbox and the floor-model discipline, are
already self-contained.)

## Decision

**Isolinear v0.3's durable artifact is saved, re-runnable, model-authored
analysis code.** The existing pipeline (prompt → entity resolution → window →
allowlisted data → codegen → sandbox → grounded chart+answer) becomes the
*authoring* flow; a successful result can be pinned as a saved visualization
that the integration refreshes **with no model call in the refresh loop**. The
codebase consolidates around this spine; machinery serving superseded design
centers is demolished incrementally behind the e2e harness gate.

### 1. The saved-visualization contract

A saved viz is an integration-owned, versioned, schema-validated record
(SemanticAlias-style store envelope — ADR-0009/0010 pattern; this ADR is the
invariant-#8 decision for the new store):

```
{ saved_viz_id, name, user_request, python_code, entity_ids[],
  window: {type: "relative", duration},  render_policy,
  created, code_version, last_good: {rendered_at, artifact_ref} }
```

- `python_code` is the exact sandbox-accepted code from the authoring run;
  `user_request` and `entity_ids` are provenance + validation inputs.
- The window is stored as a **structured relative duration** (derived
  deterministically at save time from the authored absolute window's span) —
  never the prompt phrase, so refresh re-resolution is model-free by
  construction.

### 2. Model-free refresh

On demand (and later on an integration-owned `async_track_time_interval`
schedule), the integration: re-validates every `entity_ids` member against the
current allowlist (use-time invalidation, exactly the ADR-0009 alias rule —
missing/unapproved → the viz is marked invalid, never silently re-pointed);
re-resolves `[now - duration, now]`; re-fetches history through the normal
tiered allowlist path; dispatches the **saved** code to the worker
(`render_mode: codegen`; the worker re-runs the full static safety check on
every dispatch, exactly as it does for fresh code — a saved script earns zero
trust from being saved); re-runs the deterministic answer-grounding check on
the returned claims, so the refreshed answer is re-verified on every refresh
for free. **No model call anywhere in this loop.**

Refresh failures fail soft: keep `last_good` + a stale/error badge on the
card. Bounded model-repair-on-refresh is **off** for slice 1 (a config knob
behind a later decision, lean no — the value of saved code is its
determinism).

### 3. Axes policy (the stub's open question, decided)

Slice 1: the codegen prompt instructs the model to **omit explicit axis
limits** (matplotlib autoscale) — simplest, robust to seasonal drift, no
clipping. The known cost (y-scale jumping between refreshes hurts visual
comparability) is accepted for slice 1; if it proves annoying live, the fix is
a **deterministic refresh-time bounds policy outside the generated code**
(quantized/padded bounds computed by the integration from the fetched data),
not smarter generated code.

### 4. Card surface

`custom:isolinear-card` gains a saved-viz mode pointing at a `saved_viz_id`.
Saving is user-driven from a completed result ("pin this"); the integration
never writes Lovelace config (invariant #2). Conversational refinement (the
repair loop with human feedback instead of sandbox errors — stub (l) part 1)
is explicitly a **follow-on ADR**, not this one; saving one-shot results ships
first.

### 5. The demolition plan (the consolidation half)

Sequenced, each step a bounded packet behind the suite + the live e2e harness
(`evals/e2e_pipeline_harness.py`) as the accept gate — the `f8f7760` purge
playbook, applied to the post-purge residue:

1. **Split `job_orchestration.py`** (8.2K, 44% of the integration) into
   bounded modules along the spine's existing seams: entity resolution /
   planning + envelope / history dispatch / codegen dispatch + repair /
   snapshot assembly. No behavior change; the suite is the net.
2. **Retire the `first_real_vertical_slice` gate** (ADR-0017's milestone
   completed; 22 references) — collapse to the one real path.
3. **Shrink ChartSpec to the planning/intent contract** ADR-0034 already
   declares it to be: title/summary, series identity, window, overlay intent.
   Retire render-side ceremony codegen is told to ignore.
4. **Retire the Pillow histogram + aggregate_bar families and the ADR-0023
   envelope machinery** once the e2e harness shows codegen-authored
   presentation (reachable via `user_request`, ADR-0034) covers those prompts:
   the multi-family planner schema widening, `_render_histogram_png`,
   `_render_aggregate_bar_png`, and the envelope gate collapse to the
   single-family path. **Pillow itself stays** — narrowed to the surfaced
   fallback for numeric lines and the raw-states step track (which is also the
   candidate route for open-queue (r) binary/timeline entities; invariant #6
   and the ADR-0022 kind-routing are untouched).
5. **Archive the ADRs each step obsoletes** (0017, 0023 expected; others as
   they fall) and sync `docs/ARCHITECTURE.md` at each `/closeout`.

Steps 1–2 are safe immediately; 3–4 gate on e2e evidence, not calendar.

## Rationale

- **It answers "what would we build from scratch" without the rebuild.** The
  saved-script identity is what every recent decision was already converging
  on: ADR-0030 made the model author code, ADR-0031 made the code compute
  answers, ADR-0034 made the user's request the codegen contract — the code
  IS the response now. Saving it is the natural completion, and it demands
  nothing new from the hard parts (sandbox, grounding, tiering are reused
  verbatim).
- **The refresh loop is deliberately the most deterministic path in the
  system** — allowlist re-validation, deterministic window math, tiered
  retrieval, static-checked saved code, deterministic grounding re-check.
  Everything the current codebase already does well; the model only ever runs
  at authoring time. This is also the strongest argument against the rebuild:
  the model-free spine a saved-script product needs is the part that already
  exists and is tested.
- **Demolition as sequenced packets beats a rewrite** on this repo's own
  evidence: the 2026-07-02 purge (135 files, ~40K lines) was executed in one
  session under the test suite and made everything after it faster. The
  residue this ADR targets is smaller than that was.

## Consequences

**Enables:** pinned live-refreshing dashboard analyses (charts + re-verified
answers) with zero recurring model/GPU cost per refresh; a codebase whose
module boundaries match the spine in `docs/ARCHITECTURE.md`; a shorter live
ADR list.

**Constrains:** the saved-viz store is a new schema surface (spec + BDD before
implementation, invariant #8 satisfied by this ADR); saved code is immutable
per version (re-authoring = a new save, provenance kept); refresh never
mutates HA (invariant #2) and never bypasses the allowlist (invariant #1);
demolition steps 3–4 must not regress the e2e harness's 18-prompt set.

**Open:**
- Refresh scheduling granularity + card staleness UX (spec-level).
- Whether saved-viz refresh should eventually run `answer_verification`
  caveats differently from authoring (a stale-data caveat class).
- Conversational refinement (follow-on ADR, after saving ships).
- Multi-arch worker / HA add-on packaging remains deferred (ADR-0029).

## References

- Open-queue (l) stub (STATUS.md, 2026-07-02) — the promoted design.
- ADR-0030 (codegen primary), ADR-0031 (model-authored analysis), ADR-0034
  (user_request conduit) — the convergence this completes.
- ADR-0009/0010 (store envelope pattern), ADR-0022 (kind routing, untouched),
  ADR-0023 (envelope — demolition target), ADR-0017 (gate retirement).
- `docs/ARCHITECTURE.md` — the current-state map this ADR reshapes.
