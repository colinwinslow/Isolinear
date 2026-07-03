# BDD Evidence — Answer Grounding Check (ADR-0031 D8a)

Spec: `docs/specs/answer-grounding-check.md`

## Test run evidence

```
platform linux -- Python 3.12.3, pytest-8.4.2
rootdir: /home/claude/repos/isolinear

tests/test_answer_grounding.py::TestScenarioA::test_repair_contradicted PASSED
tests/test_answer_grounding.py::TestScenarioA::test_synthetic_error_is_feedable PASSED
tests/test_answer_grounding.py::TestScenarioA::test_guarantee_in_diagnostics PASSED
tests/test_answer_grounding.py::TestScenarioB::test_verified PASSED
tests/test_answer_grounding.py::TestScenarioB::test_claim_result_verified PASSED
tests/test_answer_grounding.py::TestScenarioC::test_verified PASSED
tests/test_answer_grounding.py::TestScenarioC::test_reference_matches PASSED
tests/test_answer_grounding.py::TestScenarioE::test_unverified_caveat PASSED
tests/test_answer_grounding.py::TestScenarioE::test_not_contradicted PASSED
tests/test_answer_grounding.py::TestScenarioF::test_borderline_pass_not_contradicted PASSED
tests/test_answer_grounding.py::TestScenarioF::test_borderline_outcome_is_verified PASSED
tests/test_answer_grounding.py::TestScenarioG::test_tripwire_fires PASSED
tests/test_answer_grounding.py::TestScenarioG::test_tripwire_no_claim PASSED
tests/test_answer_grounding.py::TestScenarioG::test_tripwire_case_insensitive PASSED
tests/test_answer_grounding.py::TestScenarioG::test_no_tripwire_when_verdict_claim_exists PASSED
tests/test_answer_grounding.py::TestScenarioH::test_pass_no_verification PASSED
tests/test_answer_grounding.py::TestScenarioH::test_pass_no_answer_text PASSED
tests/test_answer_grounding.py::TestScenarioH::test_pass_empty_claims PASSED
tests/test_answer_grounding.py::TestScenarioJ::test_guarantee_in_pass PASSED
tests/test_answer_grounding.py::TestScenarioJ::test_guarantee_in_tripwire PASSED
tests/test_answer_grounding.py::TestScenarioJ::test_guarantee_in_contradicted PASSED
tests/test_answer_grounding.py::TestScenarioJ::test_guarantee_in_verified PASSED
tests/test_answer_grounding.py::TestScenarioJ::test_guarantee_in_unverified_caveat PASSED
tests/test_answer_grounding.py::TestLongestMatchNegation::test_not_correlated_beats_correlated PASSED
tests/test_answer_grounding.py::TestLongestMatchNegation::test_longer_label_wins PASSED
tests/test_answer_grounding.py::TestLongestMatchNegation::test_no_match_returns_none PASSED
tests/test_answer_grounding.py::TestLongestMatchNegation::test_word_boundary_respected PASSED
tests/test_answer_grounding.py::TestLongestMatchNegation::test_case_insensitive PASSED
tests/test_answer_grounding.py::TestApplyRule::test_descending_bands PASSED
tests/test_answer_grounding.py::TestApplyRule::test_abs_basis PASSED
tests/test_answer_grounding.py::TestApplyRule::test_empty_bands PASSED
tests/test_answer_grounding.py::TestWithheldFlag::test_contradicted_withheld_true PASSED
tests/test_answer_grounding.py::TestWithheldFlag::test_repair_soft_withheld_false PASSED
tests/test_answer_grounding.py::TestRecipeCompleteness::test_missing_required_param_is_soft PASSED
tests/test_answer_grounding.py::TestRecipeCompleteness::test_anchored_window_is_caveat PASSED
tests/test_answer_grounding.py::TestRecipeCompleteness::test_nonfinite_value_contradicted PASSED
tests/test_answer_grounding.py::TestRecipeCompleteness::test_undelivered_input_is_malformed PASSED
tests/test_answer_grounding.py::TestRecipeCompleteness::test_mixed_delivered_and_undelivered_is_malformed PASSED
tests/test_answer_grounding.py::TestRecipeCompleteness::test_undelivered_input_end_to_end PASSED

39 passed in 0.07s
```

Frontend (Vitest):

```
Test Files  5 passed (5)
     Tests  35 passed (35)
```

Full suite: `366 passed, 4 skipped`.

## Scenario coverage

| Scenario | Description | Test(s) | Status |
|---|---|---|---|
| A | Seeded false-Yes contradicted → repair_contradicted, withheld | `TestScenarioA` (3 tests) | PASS |
| B | Grounded verdict passes end-to-end → verified | `TestScenarioB` (2 tests) | PASS |
| C | Parametric `hours_above` with window + threshold → verified | `TestScenarioC` (2 tests) | PASS |
| E | Unknown metric → unverified_caveat (never error) | `TestScenarioE` (2 tests) | PASS |
| F | Borderline non-flap — reference straddling band edge → pass | `TestScenarioF` (2 tests) | PASS |
| G | Sentence tripwire: yes/no without verdict claim → repair_soft | `TestScenarioG` (4 tests) | PASS |
| H | No claims, no tripwire → pass, no answer_verification | `TestScenarioH` (3 tests) | PASS |
| J | TWO_TIER_GUARANTEE text verbatim in all diagnostics | `TestScenarioJ` (5 tests) | PASS |
| — | Longest-match negation safety | `TestLongestMatchNegation` (5 tests) | PASS |
| — | `_apply_rule` unit coverage | `TestApplyRule` (3 tests) | PASS |
| — | withheld=True on contradicted, False on soft | `TestWithheldFlag` (2 tests) | PASS |
| — | Recipe completeness: missing param → soft; anchor → caveat; non-finite → contradicted; undelivered/unallowlisted input → malformed (invariant #1) | `TestRecipeCompleteness` (6 tests) | PASS |
| card | Verified answer: no caveat | frontend grounding test | PASS |
| card | Unverified answer: caveat + guarantee text | frontend grounding test | PASS |
| card | Withheld answer: withheld message + caveat | frontend grounding test | PASS |
| card | No grounding context: nothing rendered | frontend grounding test | PASS |
