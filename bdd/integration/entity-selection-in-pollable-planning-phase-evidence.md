# Entity selection in the pollable planning phase — Evidence

Raw evidence for
[entity-selection-in-pollable-planning-phase-bdd.md](entity-selection-in-pollable-planning-phase-bdd.md)
(ADR-0026). Status: implemented and live-confirmed at `0.1.43` (commit `7466ee5`).

## Unit / integration proof (pytest)

`tests/test_entity_selection_pollable_phase.py` — 7 tests, all passing:

```
tests/test_entity_selection_pollable_phase.py::JobStartDefersSelectionTests::test_clarification_is_a_first_poll_outcome PASSED
tests/test_entity_selection_pollable_phase.py::JobStartDefersSelectionTests::test_deferred_success_renders_on_first_poll PASSED
tests/test_entity_selection_pollable_phase.py::JobStartDefersSelectionTests::test_job_start_returns_planning_without_model_call PASSED
tests/test_entity_selection_pollable_phase.py::SelectionIdempotencyTests::test_clarification_poll_is_stable_and_calls_model_once PASSED
tests/test_entity_selection_pollable_phase.py::SelectionIdempotencyTests::test_repeated_polls_do_not_recall_the_model PASSED
tests/test_entity_selection_pollable_phase.py::SynchronousRejectionTests::test_empty_catalog_fails_synchronously_on_start PASSED
tests/test_entity_selection_pollable_phase.py::RetryDefersSelectionTests::test_retry_returns_planning_and_resolves_on_poll PASSED
```

Full suite: `3 failed, 519 passed, 14 subtests passed` — the 3 failures are the
documented pre-existing codegen-sandbox matplotlib-subprocess flakes
(`tests/test_codegen_sandbox_anchor.py`), unrelated to this change.

Affected evals re-run green: `home_assistant_job_orchestration_scaffold`,
`home_assistant_job_orchestration_clarification_continuation_scaffold`,
`home_assistant_job_orchestration_model_provider_planning_scaffold`,
`home_assistant_approved_entity_catalog_scaffold`,
`semantic_memory_store_envelope` (`semantic_alias_save_and_reuse`),
`semantic_alias_invalidation`.

## Live proof (HA 2026.6.4, integration 0.1.43, Ollama `gemma4:e4b` @ 10.0.1.39)

Driven via the registered WebSocket API against the live instance at
`10.0.1.200:8123` after HACS install + restart.

### Scenario A — job/start returns planning fast, zero model call

Before ADR-0026 the same call blocked **15.2s** and returned a terminal state.
After:

```
[job/start] 0.01s  status=planning  stage=job_orchestration_entity_selection_pending
```

### Scenario C — selection reasoning streams on the poll ("Selecting entities…")

Prompt: `show kitchen temperature last hour`, snapshot polled at the card's 1s
cadence. The `progress.reasoning` tail grows live during the selection phase
(ADR-0025 D7 — previously trapped in the blocking job/start):

```
[job/start]  0.01s  status=planning  stage=job_orchestration_entity_selection_pending
[ 0.3s] SELECTING phase: msg='Selecting entities…' reasoning[0]
[ 1.0s] SELECTING phase: msg='Selecting entities…' reasoning[24]
[ 1.3s] SELECTING phase: msg='Selecting entities…' reasoning[90]
[ 2.0s] SELECTING phase: msg='Selecting entities…' reasoning[260]
[ 3.0s] SELECTING phase: msg='Selecting entities…' reasoning[497]
[ 5.0s] SELECTING phase: msg='Selecting entities…' reasoning[939]
[ 7.5s] SELECTING phase: msg='Selecting entities…' reasoning[1443]
 ... (planning phase follows) ...
[53.1s] >>> complete entities=['sensor.kitchen_ecobee_temperature'] img=/api/isolinear/artifacts/01KVC56...
phases seen: ['job_orchestration_entity_selection_pending', 'Selecting entities…',
              'Planning chart…', 'job_orchestration_artifact_storage_ready']
```

Continuous reasoning from submit → selection → planning → rendered chart, with a
real served PNG artifact. The full phase sequence
`entity_selection_pending → Selecting entities… → Planning chart… → artifact_storage_ready`
is observed.

### Multi-entity prompt — reasoning streams across both phases

Prompt: `show me the maren's room and family room temperatures since noon today`,
polled at 1s:

```
[job/start] 0.01s status=planning stage=job_orchestration_entity_selection_pending
[ 1.0s] planning  msg='Selecting entities…'  r_len=0
[ 2.0s] planning  REASONING msg='Selecting entities…'  r_len=190
[ 4.0s] planning  REASONING msg='Selecting entities…'  r_len=635
[ 6.0s] planning  REASONING msg='Selecting entities…'  r_len=1112
[16.0s] planning  REASONING (planning phase)  r_len=1143
[20.1s] planning  REASONING (planning phase)  r_len=614
[25.1s] planning  REASONING (planning phase)  r_len=1341
 ... completes with a two-series temperature chart
 (sensor.maren_ecobee_sensor_temperature + sensor.family_room_sensor_temperature)
```

Served card bundle verified to contain the reasoning-render
(`planning-reasoning`), concurrent poll (`scheduleSnapshotPoll`), and
`progress?.reasoning` access; served MD5 == committed repo bundle MD5.

## Per-scenario coverage map

Each BDD scenario → the proving test / live trace above.

- **A — job/start returns planning, never calls the model:**
  `test_job_start_returns_planning_without_model_call` (asserts status `planning`,
  stage `entity_selection_pending`, `planner.select_calls == 0`); live: `[job/start] 0.01s status=planning`.
- **B — entity-selection clarification becomes a first-poll outcome:**
  `test_clarification_is_a_first_poll_outcome` (start → `planning`; first
  `_snapshot_job` poll → `clarification_needed` with both thermostat options;
  `select_calls == 1`, `plan_calls == 0`).
- **C — D2 expansion resolves on poll with visible reasoning:** live trace above
  (`Selecting entities…` reasoning 0→1443 chars, then completes). NOTE: live D2
  was exercised on the single/temperature path; the dedicated AC-overlay prompt
  hits open-queue item (j) at *planning*, after selection — selection + streaming
  themselves work.
- **D — single-flight, model called exactly once:**
  `test_repeated_polls_do_not_recall_the_model` (5 polls after complete →
  `select_calls == 1`, `plan_calls == 1`) and
  `test_clarification_poll_is_stable_and_calls_model_once`.
- **E — pre-model structural rejection stays synchronous:**
  `test_empty_catalog_fails_synchronously_on_start` (emptied catalog → `job/start`
  returns `failed`/`no_approved_entities_available`, `select_calls == 0`, stage ≠ pending).
- **F — retry continuation moves identically:**
  `test_retry_returns_planning_and_resolves_on_poll` (seeded retryable failure →
  `job/retry` returns `planning`, `select_calls == 0`; first poll → `complete`,
  `select_calls == 1`).
- **G — non-reasoning model still resolves (graceful degradation):** covered by
  the unchanged ADR-0025 D6 fallback (`on_reasoning` guard in `model_provider.py`);
  the D2 fake planners in the suite emit no thinking and still resolve to
  complete/clarification. No dedicated new test (inherited behavior).
- **H — invariants preserved:** `select_calls`/entity assertions confirm only
  allowlisted entities resolve (#1); all returned snapshots pass
  `validate_job_snapshot_contract` via `append_validated_job_snapshot` (#4);
  orchestration evals (`...scaffold`, `...clarification_continuation_scaffold`)
  PASS. D1-before-D2 ordering unchanged (relocation only).

## Notes / deviations

- Deferral is gated on `first_real_vertical_slice_enabled` — the legacy scaffold
  path keeps synchronous selection (smaller blast radius; the scaffold path has
  no model latency). Recorded as a deviation from the spec's unconditional
  framing.
- Cosmetic: during the planning phase the live snapshot's `progress.message`
  reads the static deferral message ("Approved entities are staged for model
  planning.") rather than "Planning chart…" on some polls; reasoning still
  streams. Tracked as a follow-up polish item, not blocking.
- Separately observed (NOT this packet): a multi-concept overlay prompt
  ("temperature and when the AC was running") fails at
  `model_provider_planner_not_chart_spec_ready` — a `gemma4:e4b` planning-quality
  issue; entity selection + reasoning streaming worked correctly. Logged to the
  open queue.
```
