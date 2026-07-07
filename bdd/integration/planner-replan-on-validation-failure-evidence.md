# Planner re-plan on validation failure — Evidence

Paired with [planner-replan-on-validation-failure-bdd.md](planner-replan-on-validation-failure-bdd.md)
and [docs/specs/planner-replan-on-validation-failure.md](../../docs/specs/planner-replan-on-validation-failure.md).

**Runs:** 2026-07-06 (18th session, anchor, opt-in default 0) and 2026-07-07
(20th session, default promotion + fresh-sample fix + live proof). **Status:
COMPLETE** — Scenarios A–E covered by unit tests; spec Proof requirement #4
satisfied by `evals/planner_replan_live_proof.py` (see the live-proof section
for exactly what was and was not observed).

## Command + raw output (20th session)

```
$ python3 -m pytest tests/test_planner_replan_on_validation_failure.py -v
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.4.2, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/claude/repos/isolinear
plugins: anyio-4.14.1
collecting ... collected 7 items

tests/test_planner_replan_on_validation_failure.py::PlannerReplanOnValidationFailureTests::test_clarification_is_never_replanned PASSED [ 14%]
tests/test_planner_replan_on_validation_failure.py::PlannerReplanOnValidationFailureTests::test_default_is_one_replan PASSED [ 28%]
tests/test_planner_replan_on_validation_failure.py::PlannerReplanOnValidationFailureTests::test_exhaustion_returns_last_failure_unchanged PASSED [ 42%]
tests/test_planner_replan_on_validation_failure.py::PlannerReplanOnValidationFailureTests::test_non_trigger_rejection_is_not_replanned PASSED [ 57%]
tests/test_planner_replan_on_validation_failure.py::PlannerReplanOnValidationFailureTests::test_recoverable_rejection_is_recovered_by_one_replan PASSED [ 71%]
tests/test_planner_replan_on_validation_failure.py::PlannerReplanOnValidationFailureTests::test_replan_attempt_samples_at_nonzero_temperature PASSED [ 85%]
tests/test_planner_replan_on_validation_failure.py::PlannerReplanOnValidationFailureTests::test_zero_attempts_reproduces_single_attempt_behavior PASSED [100%]

============================== 7 passed in 0.27s ===============================
```

Full suite: `454 passed, 4 skipped` (default promotion updated one failure-path
call-count assertion in `test_first_real_vertical_slice.py` to the exhaustion
count). Evals `codegen_generation_path` + `model_authored_analysis` PASS.

## Scenario → test mapping and observed result

### Scenario A — a rejected sample is recovered by one re-plan
`test_recoverable_rejection_is_recovered_by_one_replan` — **PASS.**
Given a `FlakyThenValidPlanner(bad_samples=1)` and `max_planner_replan_attempts = 1`,
the first sample yields an incomplete ChartSpec (fails `validate_chart_spec_contract`
→ `invalid_model_provider_chart_spec`) and the second yields a valid one.
Observed: `snapshot["snapshot"]["status"] == "complete"`, the served PNG starts
with the PNG signature, and `len(planner.calls) == 2` (one bad + one recovered).

### Scenario B — exhaustion returns the last failure unchanged
`test_exhaustion_returns_last_failure_unchanged` — **PASS.**
Given an always-invalid `InvalidPlannerResultPlanner` and `max_planner_replan_attempts = 1`.
Observed: `status == "failed"`, `failure.code == "invalid_model_provider_chart_spec"`,
`failure.stage == "model_provider_planning"`, `len(planner.calls) == 2`,
`chart_rendering_called` is False, and no PNG on disk — the failure surface is
identical to a single-attempt run; only the call count differs.

### Scenario C — a legitimate clarification is never re-planned
`test_clarification_is_never_replanned` — **PASS.**
Given a `ClarifyPlanner` returning a schema-valid `status: clarification_needed`
and a generous `max_planner_replan_attempts = 3`.
Observed: `len(planner.calls) == 1` — the model's deliberate clarify is preserved,
never re-sampled.

### Scenario D — zero attempts reproduces the pre-feature behavior
`test_zero_attempts_reproduces_single_attempt_behavior` — **PASS.**
Given `FlakyThenValidPlanner(bad_samples=1)` and `max_planner_replan_attempts = 0`.
Observed: `status == "failed"`, `failure.code == "invalid_model_provider_chart_spec"`,
`len(planner.calls) == 1` — the first bad sample fails terminally (the clean
revert switch).

### Scenario E — a non-trigger deterministic rejection is not re-planned
`test_non_trigger_rejection_is_not_replanned` — **PASS, with a recorded
deviation from the BDD setup.** The BDD stages "resolved routing is `mixed`",
but since commit `372a437` (multi-numeric overlays, 2026-06-24) every
numeric+state entity set routes to `time_series_overlay`, so the `mixed` family
— and with it `mixed_chart_composition_unsupported` — is **unreachable through
`_resolve_render_family`** (the gate in `_plan_once` is now defensive dead
code). The test therefore pins the loop's non-trigger discipline at the
`_plan_once` seam: given `_plan_once` returns the deterministic
`mixed_chart_composition_unsupported` rejection and `max_planner_replan_attempts = 2`,
observed exactly one planning attempt, `planner_replan_attempts == 0`, failure
returned immediately.

### Default-on guard (default promotion)
`test_default_is_one_replan` — **PASS.** With the option absent entirely
(reader default 1), a bad first sample is recovered by one re-plan:
`status == "complete"`, `len(planner.calls) == 2`.

### Fresh-sample guarantee
`test_replan_attempt_samples_at_nonzero_temperature` — **PASS.** A planner
double recording the `temperature` keyword observes `[None, 0.7]` — the first
attempt keeps the reproducible temperature-0 default; the re-plan attempt
carries `_PLANNER_REPLAN_TEMPERATURE`.

## Live proof (spec Proof requirement #4) — `evals/planner_replan_live_proof.py`

Run 2026-07-07 against live gemma4:e4b (10.0.1.39:11434), driving the
PRODUCTION `_record_model_provider_plan` (real re-plan loop, real validation
gates, real constrained-decoding schema) with the exact live e2e-18 prompt and
the exact live-resolved entity set, with the 0.2.24 hardening clause
("NEVER add an extra series for the computed result…") surgically removed
(marker-gated) to restore the 0.2.23 prompt the tail fired under. The
`max_planner_replan_attempts` option was left absent so the runs exercise the
shipped reader default (1). Results JSON:
`evals/prompts/planner_replan_live_proof_results.json`.

### Part 1 — fresh-sample property (the finding that reshaped the packet)

On a FROZEN request (identical bytes every call):

```
[fresh-sample probe] temperature_0_default: 1/3 distinct samples ['76fb896ad9b4', '76fb896ad9b4', '76fb896ad9b4']
[fresh-sample probe] replan_temperature_0.7: 3/3 distinct samples ['86c89020c06f', '21ee75da5a0b', 'b93062bf2153']
```

The planner's structured pass runs at `temperature: 0` — near-greedy — so the
0.2.25 slice-1 loop ("plain re-sample", same request) would have reproduced the
rejected plan byte-for-byte: **a live no-op**. The fix shipped with the default
promotion: re-plan attempts pass `temperature=_PLANNER_REPLAN_TEMPERATURE`
(0.7) so the retry is a genuinely fresh sample; the frozen request then yields
3/3 distinct plans. This is the recovery mechanism's live proof.

### Part 2 — the duplicate-source tail (honest non-reproduction)

16/16 live production-path runs planned valid on the first sample
(`ok-first-try`, ~30–47 s each) — the e2e-18 duplicate-source class did **not**
reproduce even with the 0.2.24 clause removed. It is a rare variance region (it
fired once in the 17th-session harness batch). End-to-end recovery is therefore
proven by the unit-tested loop mechanics plus the live fresh-sample property
above, not by a captured live occurrence; the eval records
`tail-not-reproduced` explicitly and will headline a live recovery if one is
ever observed on a re-run.

```
=== tally === {"runs": 16, "accepted": 16, "tail_fired": 0, "recovered_by_replan": 0}
PASS planner_replan_live_proof — fresh-sample property proven live (temp-0 default: 1/3 distinct; re-plan override: 3/3 distinct).
  tail-not-reproduced: 16/16 first samples validated (the duplicate-source class is a rare variance region; recorded honestly)
```
