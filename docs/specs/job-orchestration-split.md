---
status: draft
date: 2026-07-07
depends-on-adrs: [0035]
---

# Splitting `job_orchestration.py` — ADR-0035 demolition step 1

## Status

Draft — the executable split plan (Fable planning session, 2026-07-07, 22nd
session). ADR-0035 §5 step 1: split the 8,335-line / 202-def orchestration god
module into bounded modules along the spine's existing seams, **zero behavior
change**, the 454-test suite as the net, the live e2e harness as the final
accept gate. Execution is Opus-shaped once this plan is ratified; each commit
below is independently landable and leaves `main` coherent.

**BDD note.** No BDD scenarios: no user-facing contract, schema, service, or
observable behavior changes. The proof artifacts are (a) the unchanged suite
after every commit, (b) the import-graph checks below, (c) an e2e-harness spot
run vs the 2026-07-07 baseline (`evals/e2e_runs/20260707T171258Z/REPORT.md`).
This mirrors the 19th-session precedent (eval as proof artifact where no
contract surface changes).

## Related docs

- [docs/decisions/0035-saved-rerunnable-analysis-code.md](../decisions/0035-saved-rerunnable-analysis-code.md) — §5 names the seams and the gate
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — the spine the module boundaries must match; component map updated at the closing commit
- [STATUS.md](../../STATUS.md) — strategic through-line entry

## Measured ground truth (2026-07-07, at 0.2.27 / `a03f17f`)

The plan rests on these **measured** facts, not guesses — re-verify cheaply if
executing from a later base:

1. **Production import surface is 8 symbols in 2 modules.** `__init__.py`
   imports `setup_job_orchestration`; `websocket_api.py` imports the five
   `handle_job_orchestration_*_ws_command` handlers + `has_enabled_job_orchestration`
   + `has_job_orchestration_setup`. The other six files that grep for
   "job_orchestration" only carry the `"job_orchestration_called": False`
   marker string or comments. **All 8 symbols stay in `job_orchestration.py`**
   → zero production import changes anywhere in this packet.
2. **Tests + evals + scripts reference ~51 symbols** (from-imports and
   attribute access on the module). Handled by an explicit compat re-export
   block in the facade — tests keep importing from `job_orchestration`
   unchanged, except the one patch-site below.
3. **Six patch sites in tests** (the monkeypatch trap for module splits — a
   patch on `job_orchestration.X` stops reaching callers of `X` the moment
   those callers move to another module). *Corrected during commit 3: the
   original measurement caught only the two attribute-write sites; multi-line
   `patch.object(job_orchestration, "…")` sites escaped the single-line grep —
   found by the suite failing exactly as designed. The full set:*
   - `tests/test_planner_replan_on_validation_failure.py:252` writes
     `job_orchestration._plan_once`. Sole caller `_record_model_provider_plan`
     moves with it in commit 6 → **that commit repoints this test**.
   - `tests/test_dashboard_card_long_running_smoke.py:423` writes
     `job_orchestration_module._artifact_snapshot_lock_for_job`. Its sole
     caller (the snapshot WS handler) stays in the facade, whose bare-name
     call resolves through facade module globals → patch keeps intercepting.
     **No change needed** (verified green at commit 2).
   - `tests/test_first_real_vertical_slice.py:1282` patches
     `append_validated_job_snapshot`; the relevant caller
     (`_append_artifact_complete_snapshot`) moved in commit 3 → **repointed to
     `snapshot_assembly` in commit 3** (caught live by the suite).
   - `tests/test_first_real_vertical_slice.py:1250` patches
     `validate_artifact_metadata_contract`; its callers (artifact-metadata
     recording) stay in the facade until commit 7 → **repoint at commit 7**.
   - `tests/test_first_real_vertical_slice.py:1366` and `:1459` patch
     `render_in_process_chart`; caller `_record_in_process_render` moves at
     commit 7 → **repoint both at commit 7**.
4. **Appenders are driver-only.** All `_append_*` snapshot calls originate in
   the WS-handler/driver region (557–1860, 3113–4016). The worker/codegen
   region (4017–6383) calls zero appenders (only its own
   `_build_worker_progress_snapshot`, which moves with it).
5. **The planning loop's dependencies are exactly**: `plan_chart`
   (model_provider), `_call_planner_with_optional_reasoning`,
   `_apply_catalog_units`, `_resolve_render_envelope`, and five
   `validate_*` gates. No appenders, no store plumbing (the driver stores the
   plan).
6. **Module-level mutable state is confined to** `ARTIFACT_SNAPSHOT_LOCKS_GUARD`
   (a `threading.Lock` guarding per-job lock creation; the per-job locks
   themselves live inside the store dict). It moves with
   `_artifact_snapshot_lock_for_job`. Everything else at module level is
   constants/regexes/schema paths.

## Target shape (7 new modules + the residual orchestrator)

Dependency rule (the cycle-killer, enforced every commit): **seam modules
never import `job_orchestration`; imports flow strictly downward through the
layers.** Anything two seams share moves DOWN into a shared layer in the same
commit that creates the second user.

```
L0  orchestration_contracts.py   ~450 ln  validate_*_contract ×16 + entity/duplicate-source
                                          checks + all *_SCHEMA_PATH constants
L0  orchestration_store.py       ~600 ln  _store_validated_* / _remove_stored_* / _latest_* /
                                          _rollback_artifact_planning_records / per-job record
                                          lookups (_job_for_*, _artifact_for_job, _render_plan_
                                          for_job, …) / _artifact_snapshot_lock_for_job +
                                          LOCKS_GUARD / live-reasoning slot helpers (_live_
                                          reasoning_*) + DATA_LIVE_REASONING / job_orchestration_
                                          side_effects + summarize_job_orchestration_store +
                                          DATA_* keys
L1  snapshot_assembly.py         ~900 ln  the _append_* family (2554–3112) + _append_artifact_
                                          complete_snapshot + failure-message composers +
                                          _safe_* / forbidden-text sanitizers (8036–8156) +
                                          clarification/snapshot small helpers (8157–8335) +
                                          FORBIDDEN_* regexes, ARTIFACT_SOURCE_PROGRESS_STAGES
L1  history_dispatch.py          ~400 ln  _retrieve_history_for_plan + resolve_history_window +
                                          _default_history_time_range/_history_now/_parse_window_
                                          timestamp/_history_window_end_dt + _timestamp_to_epoch_
                                          ms/_history_series_with_epoch_ms/_history_series_for_
                                          render_plan + _hass_time_zone
L1  entity_resolution.py         ~900 ln  select_prompt_entity_ids + D1 scoring (7930–8035) +
                                          D2/composition (_resolve_entity_selection_with_model,
                                          _run_model_entity_selection, _prune_composition_with_
                                          model, _composition_has_shared_token) + alias machinery
                                          (_inject_semantic_aliases, _alias_display_entries,
                                          _maybe_save_semantic_alias) + family/envelope routing
                                          (_resolve_render_family/_resolve_render_envelope,
                                          _resolve_overlay_label, _compose_state_overlays,
                                          _compose_binary_overlays) + _approved_catalog_items +
                                          ENTITY_ID_IN_PROMPT, ENTITY_SELECTION_PENDING_STAGE
L2  planning_pipeline.py         ~700 ln  _record_model_provider_plan + _plan_once + replan loop
                                          + _PLANNER_REPLAN_TEMPERATURE + _call_planner_with_
                                          optional_reasoning + _model_provider_planner_request +
                                          _apply_catalog_units + validate_model_provider_chart_
                                          family + _build_model_provider_plan + model-provider
                                          retry-policy build/record + _configured_max_planner_
                                          replan_attempts + phase labels
L2  render_dispatch.py          ~2100 ln  the codegen loop (_record_codegen_worker_dispatch,
                                          _finish_codegen_success, _codegen_render_failed,
                                          _build_codegen_render_request, _compact_codegen_error_
                                          detail, _configured_render_path/_configured_max_
                                          codegen_repair_attempts) + chart-spec worker dispatch
                                          (_record_worker_dispatch, _build_worker_dispatch,
                                          _build_worker_render_request) + in-process fallback
                                          (_record_in_process_render, _accept_in_process_render_
                                          result, _codegen_fallback_reason) + worker artifact
                                          recording (_record_worker_rendered_artifact, _rollback_
                                          worker_rendered_artifact, _worker_png_bytes_from_render_
                                          result) + worker progress (_record_worker_progress_
                                          events, _normalize_worker_progress_payloads, _build_
                                          worker_progress_snapshot/_event, MAX_WORKER_PROGRESS_
                                          EVENTS) + overlay bands (_compute_overlay_bands,
                                          _overlay_band — ADR-0033) + artifact-metadata builders
                                          (_build_artifact_metadata + in_process/worker variants)
                                          + transport classification & worker retry policy
                                          (6122–6383) + WORKER_RENDERER_NAME
L3  job_orchestration.py        ~2300 ln  THE ORCHESTRATOR (residual): setup/store gates (setup_,
                                          ensure_, has_*) + the five WS handlers + deferral
                                          (_defer_selection/history_to_planning) + _resolve_
                                          pending_entity_selection + the two drivers (_record_
                                          artifact_snapshot_for_source, _record_artifact_and_
                                          render_plan) + _record_run/_record_progress_event/
                                          _record_artifact_metadata + response envelopes
                                          (_accepted*, _orchestration_rejection) + catalog-failure
                                          shapers + chart/artifact snapshot glue + the compat
                                          re-export block
```

Naming notes: `render_dispatch.py` deliberately covers ADR-0035's "codegen
dispatch + repair" **plus** the Pillow fallback and chart-spec worker path —
the seam is "how a validated plan becomes a PNG", and invariant #6 (surfaced
fallback) lives exactly at that boundary; splitting codegen from its fallback
would put one decision on two sides of a module line. Envelope/family routing
lands in `entity_resolution.py`, not planning, because ADR-0022 routes family
from entity KIND *before* planning and ADR-0028 re-routes pruned compositions
— and because planning must import the envelope (downward) while resolution
must not import planning (cycle).

## Commit sequence

Seven bounded commits, dependency-ordered, lowest risk first. **Every commit:**
full suite green (`python3 -m pytest tests/` — 454/4 at base), the moved defs
deleted from the facade and re-imported in the compat block, and the checks in
"Per-commit verification" below. One version bump at the end (packet norm),
`[ADR-0035]` prefix throughout.

1. **`orchestration_contracts.py`** — validators + schema paths. Pure
   functions over `_paths`/json-schema; zero orchestration state. Moves:
   6384–6830 (16 `validate_*_contract` + `_check_chart_spec_no_duplicate_series_sources`
   + `validate_model_provider_chart_spec_entities` + `validate_model_provider_output_entities`)
   + the 13 `*_SCHEMA_PATH` constants. Tests/evals hit SCHEMA_PATHs via facade
   attributes → re-exports cover them.
2. **`orchestration_store.py`** — store plumbing per the table (incl.
   `_artifact_snapshot_lock_for_job` + `ARTIFACT_SNAPSHOT_LOCKS_GUARD`,
   live-reasoning slots, `job_orchestration_side_effects`,
   `summarize_job_orchestration_store`, record lookups, `_store_validated_*`,
   `_remove_stored_*`, `_rollback_artifact_planning_records`, `_latest_*`,
   `_remove_ordered_id`, `_subscription_ids_for_job`). Ground-truth fact #3
   says the long-running-smoke patch keeps working — verify by running that
   test file explicitly in this commit.
3. **`snapshot_assembly.py`** — the appender family + message composers +
   sanitizers + clarification helpers per the table. Driver-only consumers
   (fact #4) → facade re-imports; no seam module needs it yet.
4. **`history_dispatch.py`** — window math + tiered retrieval wrapper +
   epoch-ms transforms (D9 discipline) per the table. Downward deps:
   `history_retrieval` only.
5. **`entity_resolution.py`** — selection machinery + family/envelope routing
   + `_approved_catalog_items` per the table. `_resolve_pending_entity_selection`
   and the deferral helpers **stay in the facade** (they are driver glue that
   calls back into planning continuation). Evals import
   `_resolve_render_family`/`_resolve_render_envelope`/`select_prompt_entity_ids`
   etc. from the facade → re-exports cover.
6. **`planning_pipeline.py`** — the plan/replan loop per the table.
   **Repoint the patch site**: `tests/test_planner_replan_on_validation_failure.py`
   saves/patches/restores `_plan_once` on the *new* module (its caller moves
   there). Also move `_configured_max_planner_replan_attempts` here (its
   sibling codegen readers move in commit 7 — split readers by owner, both
   re-exported).
7. **`render_dispatch.py`** + facade tidy + closeout. The largest move (~2.1K)
   but by now its dependencies (contracts, store, snapshot, history) are all
   below it. Then: organize the residual facade (setup/gates → handlers →
   deferral/pending-selection → drivers → envelopes → compat re-export block
   with a header comment: *"compat re-exports for tests/evals; production
   importers use only the 8 public symbols; trim under ADR-0035 step 2+"*);
   sync `docs/ARCHITECTURE.md` (component map: replace the god-module row with
   the new modules; update the spine diagram annotations); bump version
   (`manifest.json` + `const.py`, 0.2.27 → 0.2.28); promote this spec
   draft→accepted; STATUS/HANDOFF via `/closeout`.

Commits 1–4 are near-mechanical (leaf moves, no test changes). Commit 5–6 are
the ones with judgment calls (envelope placement, patch repoint). Commit 7 is
big but structurally forced by then. If a session ends mid-sequence, any
prefix of the sequence is a valid stopping point — that is the point of the
ordering.

## Per-commit verification

1. Full suite: `python3 -m pytest tests/` → 454 passed / 4 skipped (or +N if
   the base moved; the count must not DROP).
2. No upward imports:
   `grep -rn "job_orchestration" custom_components/isolinear/<new_module>.py`
   → nothing but comments/docstrings, for every seam module.
3. Layer rule: each new module imports only existing non-orchestration modules
   + strictly-lower-layer seam modules (eyeball the import block against the
   L0–L3 table).
4. Facade shrinkage is real:
   `wc -l custom_components/isolinear/job_orchestration.py` strictly decreases;
   the moved def names no longer `^def `-match in the facade (re-exports are
   `from .x import y` lines, not defs).
5. Import sanity: `python3 -c "from custom_components.isolinear import job_orchestration"`
   (catches cycles immediately).
6. Commit 2 extra: `python3 -m pytest tests/test_dashboard_card_long_running_smoke.py -v`.
   Commit 6 extra: `python3 -m pytest tests/test_planner_replan_on_validation_failure.py -v`.
7. Logger caveat: each new module takes `logging.getLogger(__name__)` — log
   records change module attribution. Before commit 1, grep tests for caplog
   assertions pinned to the module name
   (`grep -rn "job_orchestration" tests/ | grep -i "caplog\|record.name"`) and
   note any hits in the commit message (none expected; the 20th session noted
   the re-plan INFO line is deliberately not unit-asserted).

## Final accept gate (after commit 7)

- Evals `codegen_generation_path` + `model_authored_analysis` PASS (as at
  0.2.27 closeout).
- Live e2e harness **spot set** (one per family, ~8 prompts:
  e2e-01, 03, 06, 09, 10, 11, 16, 17) judged against the **2026-07-07 0.2.27
  baseline** (`evals/e2e_runs/20260707T171258Z/REPORT.md` — 11 PASS / 4
  PARTIAL / 3 FAIL). The honest-baseline rule: e2e-12/14/18 already FAIL on
  unsplit 0.2.27 (the cross-sensor-math regression + the (v) wall are
  pre-existing); the split is accepted iff no prompt's verdict *degrades*
  relative to that report — not the 0.2.24 one.

## Non-goals (bounded packet)

- **No behavior change of any kind** — no bug fixes en route (the e2e-12/18
  cross-math regression is a separate packet), no `first_real_vertical_slice`
  retirement (that is ADR-0035 step 2), no ChartSpec slimming (step 3), no
  Pillow-family demolition (step 4), no renames of moved functions, no
  signature changes, no docstring rewrites beyond module headers.
- **No test migration beyond the one forced repoint** (commit 6). The ~51
  compat re-exports stay, explicitly labeled; they shrink opportunistically in
  step-2+ packets that touch those tests anyway.
- **No push** without Colin's go-ahead (commit-only norm).

## Open for Colin

1. Module names (`orchestration_contracts` / `orchestration_store` /
   `snapshot_assembly` / `history_dispatch` / `entity_resolution` /
   `planning_pipeline` / `render_dispatch`) — bikeshed freely; the boundaries
   are the load-bearing part.
2. `render_dispatch.py` lands at ~2.1K lines. Acceptable as one coherent seam,
   or pre-split worker-transport classification (~450 ln) into its own module?
   Plan says: keep one module now, note the sub-split as a follow-up if it
   grows.
3. This spec is deliberately spec-level (no new ADR): ADR-0035 §5.1 already IS
   the decision; this document is its execution contract.
