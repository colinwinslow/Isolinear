# Semantic Alias Live Wiring — BDD Evidence

**Run timestamp:** 2026-06-23 (closeout; Tranche 1 anchor landed in 0.1.40)

**BDD file:** `bdd/semantic-memory/semantic-alias-live-wiring-bdd.md`

---

## Unit tests — `custom_components/isolinear/semantic_memory.py` + orchestration injection

```
python3 -m pytest tests/test_semantic_alias_live_wiring.py -v
```

```
collected 33 items

StorageHelperTests::test_async_load_ignores_wrong_version_envelope PASSED
StorageHelperTests::test_async_load_restores_persisted_stores PASSED
StorageHelperTests::test_in_memory_backend_when_no_ha_store PASSED
StorageHelperTests::test_seed_and_read_back_is_entry_scoped PASSED
StoreContractTests::test_duplicate_alias_ids_fail_closed PASSED
StoreContractTests::test_missing_required_field_fails_closed PASSED
StoreContractTests::test_unsupported_version_fails_closed PASSED
StoreContractTests::test_valid_store_accepted PASSED
ValiditySplitTests::test_disabled_alias_skipped_not_invalid PASSED
ValiditySplitTests::test_hidden_entity_is_not_allowlisted PASSED
ValiditySplitTests::test_malformed_store_returns_store_error PASSED
ValiditySplitTests::test_missing_entity_is_unavailable PASSED
ValiditySplitTests::test_valid_alias_returned PASSED
MatcherTests::test_match_aliases_filters_to_matching PASSED
MatcherTests::test_no_token_overlap_does_not_match PASSED
MatcherTests::test_sub_threshold_overlap_does_not_match PASSED
MatcherTests::test_trivial_words_only_do_not_match PASSED
MatcherTests::test_two_character_token_matches_without_length_floor PASSED
MatcherTests::test_two_token_name_full_overlap_matches PASSED
EntityIdExtractionTests::test_aggregate_returns_all_entities PASSED
EntityIdExtractionTests::test_entity_meaning_single_entity PASSED
EntityIdExtractionTests::test_state_interval_single_entity PASSED
ResolveInjectionTests::test_aggregate_alias_injects_all_present_entities PASSED
ResolveInjectionTests::test_disabled_alias_injects_nothing PASSED
ResolveInjectionTests::test_invalid_alias_injects_nothing PASSED
ResolveInjectionTests::test_malformed_store_fails_closed_with_error PASSED
ResolveInjectionTests::test_matched_alias_injects_entity PASSED
ResolveInjectionTests::test_no_match_injects_nothing PASSED
ResolveInjectionTests::test_none_store_injects_nothing PASSED
OrchestrationInjectionTests::test_alias_only_when_prompt_has_no_direct_match PASSED
OrchestrationInjectionTests::test_anchor_direct_and_alias_compose PASSED
OrchestrationInjectionTests::test_no_dup_when_alias_entity_already_directly_resolved PASSED
OrchestrationInjectionTests::test_no_store_returns_selection_unchanged PASSED

33 passed in 0.14s
```

Scenario mapping:

- **Saved AC alias injects the climate entity the prompt never named** —
  `OrchestrationInjectionTests::test_anchor_direct_and_alias_compose`,
  `ResolveInjectionTests::test_matched_alias_injects_entity`
- **Token overlap below threshold does not match** —
  `MatcherTests::test_sub_threshold_overlap_does_not_match`,
  `MatcherTests::test_no_token_overlap_does_not_match`
- **A short two-character alias token still matches** —
  `MatcherTests::test_two_character_token_matches_without_length_floor`
- **Disabled alias is never injected** —
  `ValiditySplitTests::test_disabled_alias_skipped_not_invalid`,
  `ResolveInjectionTests::test_disabled_alias_injects_nothing`
- **Invalid alias (entity unavailable or not allowlisted) is never injected** —
  `ValiditySplitTests::test_missing_entity_is_unavailable`,
  `ValiditySplitTests::test_hidden_entity_is_not_allowlisted`,
  `ResolveInjectionTests::test_invalid_alias_injects_nothing`
- **Malformed store fails closed with no injection** —
  `StoreContractTests::test_unsupported_version_fails_closed`,
  `StoreContractTests::test_duplicate_alias_ids_fail_closed`,
  `ResolveInjectionTests::test_malformed_store_fails_closed_with_error`
- **Aggregate alias injects all of its source entities** —
  `EntityIdExtractionTests::test_aggregate_returns_all_entities`,
  `ResolveInjectionTests::test_aggregate_alias_injects_all_present_entities`

---

## Eval — anchor artifact on disk

```
python3 evals/semantic_memory_store_envelope.py
```

Injection CASE output (the anchor artifact — seeded store + resolved result):

```json
CASE semantic_alias_injection
{
  "case_id": "semantic_alias_injection",
  "given": {
    "entity_catalog": [
      { "entity_id": "sensor.kitchen_temperature", "label": "Kitchen Temperature", "visible_to_agent": true },
      { "entity_id": "climate.kitchen_ecobee", "label": "Kitchen Ecobee", "visible_to_agent": true }
    ],
    "prompt": "show kitchen temp and when the AC was running",
    "semantic_memory_store": {
      "store_version": 1,
      "config_entry_id": "fake-config-entry",
      "aliases": [
        {
          "alias_id": "whole_house_ac",
          "natural_names": ["AC", "AC running"],
          "meaning": { "type": "state_interval", "entity_id": "climate.kitchen_ecobee", "active_values": ["cool", "heat"] },
          "source": "user_confirmed",
          "created_from_prompt": "show kitchen temp and when the AC was running",
          "enabled": true
        }
      ]
    }
  },
  "when": { "operation": "resolve_alias_injection" },
  "then": {
    "matched_alias_ids": ["whole_house_ac"],
    "injected_entity_ids": ["climate.kitchen_ecobee"],
    "store_error": null
  }
}
PASS semantic_alias_injection
PASS semantic_memory_store_envelope
```

---

## Full suite

```
python3 -m pytest tests/ -q
```

```
3 failed, 484 passed in 15.54s
```

The 3 failures are the pre-existing codegen-sandbox subprocess flake
(`tests/test_codegen_sandbox_anchor.py`), identical on the clean baseline and
unrelated to this change.
