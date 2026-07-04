# BDD Evidence — Answer Grounding Check (ADR-0031 D8a)

Spec: `docs/specs/answer-grounding-check.md`

Last verified: 2026-07-03 (8th session — proof req #4 claim-emission benchmark; full suite 372 passed / 4 skipped)

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
tests/test_answer_grounding.py::TestScenarioD::test_fabricated_anchor_unfound PASSED
tests/test_answer_grounding.py::TestScenarioD::test_anchor_mismatch PASSED
tests/test_answer_grounding.py::TestScenarioD::test_verified_via_anchor PASSED
tests/test_answer_grounding.py::TestScenarioD::test_irreproducible_out_of_kind_entity_is_caveat PASSED
tests/test_answer_grounding.py::TestScenarioD::test_irreproducible_missing_search_is_caveat PASSED
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
tests/test_answer_grounding.py::TestRecipeCompleteness::test_malformed_anchor_shape_is_caveat PASSED
tests/test_answer_grounding.py::TestRecipeCompleteness::test_nonfinite_value_contradicted PASSED
tests/test_answer_grounding.py::TestRecipeCompleteness::test_undelivered_input_is_malformed PASSED
tests/test_answer_grounding.py::TestRecipeCompleteness::test_mixed_delivered_and_undelivered_is_malformed PASSED
tests/test_answer_grounding.py::TestRecipeCompleteness::test_undelivered_input_end_to_end PASSED

44 passed in 0.08s
```

Frontend (Vitest):

```
Test Files  5 passed (5)
     Tests  35 passed (35)
```

Full suite: `371 passed, 4 skipped`.

## Scenario coverage

| Scenario | Description | Test(s) | Status |
|---|---|---|---|
| A | Seeded false-Yes contradicted → repair_contradicted, withheld | `TestScenarioA` (3 tests) | PASS |
| B | Grounded verdict passes end-to-end → verified | `TestScenarioB` (2 tests) | PASS |
| C | Parametric `hours_above` with window + threshold → verified | `TestScenarioC` (2 tests) | PASS |
| D | Event anchors (§1a, tranche 2): fabricated event → `grounding_anchor_unfound` (contradicted, withheld); mismatched `resolved_at` → `grounding_anchor_mismatch`; correctly re-detected anchor → `verified` (value↔data guarantee extended to event-scoped claims); out-of-kind entity / missing search-occurrence → `grounding_anchor_unreproducible` (caveat, irreproducible by construction, never attempted) | `TestScenarioD` (5 tests) | PASS |
| E | Unknown metric → unverified_caveat (never error) | `TestScenarioE` (2 tests) | PASS |
| F | Borderline non-flap — reference straddling band edge → pass | `TestScenarioF` (2 tests) | PASS |
| G | Sentence tripwire: yes/no without verdict claim → repair_soft | `TestScenarioG` (4 tests) | PASS |
| H | No claims, no tripwire → pass, no answer_verification | `TestScenarioH` (3 tests) | PASS |
| J | TWO_TIER_GUARANTEE text verbatim in all diagnostics | `TestScenarioJ` (5 tests) | PASS |
| — | Longest-match negation safety | `TestLongestMatchNegation` (5 tests) | PASS |
| — | `_apply_rule` unit coverage | `TestApplyRule` (3 tests) | PASS |
| — | withheld=True on contradicted, False on soft | `TestWithheldFlag` (2 tests) | PASS |
| — | Recipe completeness: missing param → soft; malformed anchor shape → caveat; non-finite → contradicted; undelivered/unallowlisted input → malformed (invariant #1) | `TestRecipeCompleteness` (6 tests) | PASS |
| card | Verified answer: no caveat | frontend grounding test | PASS |
| card | Unverified answer: caveat + guarantee text | frontend grounding test | PASS |
| card | Withheld answer: withheld message + caveat | frontend grounding test | PASS |
| card | No grounding context: nothing rendered | frontend grounding test | PASS |

## Sub-packet 4d note (event anchors, tranche 2)

Implemented in this session: `_anchor_criteria_ok` (§1a's four reproducibility
criteria — delivered raw-state entity, crisp `to`/`from` string equality,
non-zero `occurrence` + numeric `search` bounds, numeric `resolved_at`),
`_detect_transitions` (scans the full ordered raw-state timeline — `raw_state`
or `attrs[attribute]` — for exact transitions, filtered to those whose own
timestamp falls in `search`), `_select_occurrence` (1-based / negative-from-end
indexing into the finite transition list), and `_resolve_anchor` (combines
them). Wired into `_check_claim` step 4: an anchor failing §1a is
`grounding_anchor_unreproducible` (caveat, by construction — never attempted
further); a criteria-passing anchor with no matching transition is
`grounding_anchor_unfound` (contradicted); a re-detected transition at a
different instant than the claimed `resolved_at` is `grounding_anchor_mismatch`
(contradicted, identity not just existence); a correctly re-detected anchor
resolves absolute `{start, end}` bounds from `direction`/`duration_ms`, which
then flow through the same span-check and registry recompute as an absolute
window — extending the full value↔data guarantee to event-scoped claims. No
schema change (the claim `window` field was already an open object;
`additionalProperties: true`). The pre-existing stub test asserting
`grounding_anchor_deferred` on any `"anchor"`-keyed window is renamed
`test_malformed_anchor_shape_is_caveat` and now asserts
`grounding_anchor_unreproducible` (a bare-string anchor still fails §1a's
"anchor must be a dict" criterion, so the observable outcome — caveat — is
unchanged; only the code name changed to reflect real validation instead of a
blanket defer). Proof requirement #1's fabricated-anchor case (a narrated event
with no matching transition → `anchor_unfound` → withheld) is
`TestScenarioD::test_fabricated_anchor_unfound`. Not in this sub-packet: codegen
prompt guidance for emitting anchor-shaped claims (the floor-model
claim-emission-rate benchmark is a separate open item) — the anchor path is
exercised by the deterministic check and available to any model that emits a
well-formed anchor. *(Update, 8th session: `_CODEGEN_PROMPT_RULES` now documents
the anchored window shape — commit `079431d` — but the floor model still records
absolute bounds; see the next section.)*

## Proof requirement #4 — floor-model claim-emission rate (2026-07-03, 8th session)

The spec's proof requirement #4 — "does the floor model (`gemma4:e4b`) reliably
emit a well-formed claim recipe?" — is answered by extending the answer-family
benchmark (`evals/prompts/benchmark_prompts.json` + `evals/analysis_benchmark/`),
with emitted claims scored by the REAL production checker
(`custom_components.isolinear.answer_grounding`) against fresh real HA history
(gitignored). Full raw numbers, per-run tables, and the three measured causes
live in `evals/analysis_benchmark/FINDINGS.md` ("claim-emission rate,
2026-07-03"). Headline evidence:

- **Emission is reliable**: every claim-expected prompt whose generated code
  executed emitted a `claims` list (run 1: 6/6; run 3: 5/5). Misses are prompts
  whose code never ran, not prompts that skipped the ledger.
- **Well-formedness is high** (6/6 and 4/5 pass the production structure step).
- **Registry-verified: 0 in every run** — three measured causes: (1) a prompt
  wording bug made run 1 stringify all values ('3.0°F'); the raw-JSON-number
  hardening now in `_CODEGEN_PROMPT_RULES` fixed the type on every subsequent
  claim; (2) free metric naming lands honest-but-unregistered metrics in the
  caveat box (correct per D3); (3) the registry's exact-timestamp `pearson_r`
  intersection returns no reference on real irregular data — the spec's
  "prescribe the alignment" open item, confirmed live.
- **No false "verified" was ever produced**, and the check caught a genuine live
  `grounding_verdict_contradicted` (pd-05) — the exact class it exists for.
- **Anchored windows: 0/2 emitted in every run** (event logic appears in code
  but records absolute bounds) — acceptable for tranche 1 (value↔data still
  holds); 4d re-detection will not exercise at the capability floor yet.
