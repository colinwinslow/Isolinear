# Planner re-plan on validation failure — Evidence

Paired with [planner-replan-on-validation-failure-bdd.md](planner-replan-on-validation-failure-bdd.md)
and [docs/specs/planner-replan-on-validation-failure.md](../../docs/specs/planner-replan-on-validation-failure.md).

**Run:** 2026-07-06 (18th session). **Slice-1 status:** anchor landed, opt-in
(`max_planner_replan_attempts` reader default 0). Scenarios A–D covered by unit
tests; Scenario E (mixed-routing pre-planner code) and the live e2e-18 recovery
proof (spec Proof requirement #4) are **pending** — see "Not yet covered" below.

## Command + raw output

```
$ python3 -m pytest tests/test_planner_replan_on_validation_failure.py -v
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.4.2, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/claude/repos/isolinear
plugins: anyio-4.14.1
collecting ... collected 5 items

tests/test_planner_replan_on_validation_failure.py::PlannerReplanOnValidationFailureTests::test_clarification_is_never_replanned PASSED [ 20%]
tests/test_planner_replan_on_validation_failure.py::PlannerReplanOnValidationFailureTests::test_default_is_off_single_attempt PASSED [ 40%]
tests/test_planner_replan_on_validation_failure.py::PlannerReplanOnValidationFailureTests::test_exhaustion_returns_last_failure_unchanged PASSED [ 60%]
tests/test_planner_replan_on_validation_failure.py::PlannerReplanOnValidationFailureTests::test_recoverable_rejection_is_recovered_by_one_replan PASSED [ 80%]
tests/test_planner_replan_on_validation_failure.py::PlannerReplanOnValidationFailureTests::test_zero_attempts_reproduces_single_attempt_behavior PASSED [100%]

============================== 5 passed in 0.16s ===============================
```

Full suite unaffected (additive, default-off): `451 passed, 4 skipped in 7.94s`.

## Scenario → test mapping and observed result

### Scenario A — a rejected sample is recovered by one re-plan
`test_recoverable_rejection_is_recovered_by_one_replan` — **PASS.**
Given a `FlakyThenValidPlanner(bad_samples=1)` and `entry.options["max_planner_replan_attempts"] = 1`,
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

### Scenario D — zero attempts reproduces today's behavior
`test_zero_attempts_reproduces_single_attempt_behavior` — **PASS.**
Given `FlakyThenValidPlanner(bad_samples=1)` and `max_planner_replan_attempts = 0`.
Observed: `status == "failed"`, `failure.code == "invalid_model_provider_chart_spec"`,
`len(planner.calls) == 1` — the first bad sample fails terminally, exactly as
before the feature (the clean revert switch).

Additional guard — `test_default_is_off_single_attempt` — **PASS.** With the option
absent entirely (reader default 0), a bad first sample fails with `len(planner.calls) == 1`
— the additive-landing guarantee that no existing behavior changes.

## Not yet covered (honest gaps)

- **Scenario E** (a non-trigger deterministic rejection like
  `mixed_chart_composition_unsupported` is not re-planned, `planner.calls == 0`) —
  needs a mixed-routing catalog fixture; deferred. The exclusion is enforced in
  code (`_PLANNER_REPLAN_TRIGGER_CODES` only contains the two output-quality
  codes) and exercised indirectly by Scenario C.
- **Spec Proof requirement #4** (live gemma e2e-18-class duplicate-source variance
  tail recovers via re-plan) — pending; requires a live run with the option set.
