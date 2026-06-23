# Semantic Alias Save — Tranche 2 BDD Evidence

**Run timestamp:** 2026-06-23 20:42 UTC (`0.1.42`)

**BDD file:** `bdd/semantic-memory/semantic-alias-save-tranche2-bdd.md`
**Spec:** `docs/specs/semantic-alias-save-tranche2.md`

---

## Unit / integration test command and output

```
python3 -m pytest tests/test_semantic_alias_save_tranche2.py -v
17 passed in 0.25s
```

```
AliasDerivationTests::test_entity_id_to_alias_id_slugifies PASSED
AliasDerivationTests::test_derive_natural_names_keeps_distinctive_prompt_tokens PASSED
AliasDerivationTests::test_derive_natural_names_strips_action_words PASSED
AliasDerivationTests::test_derive_natural_names_falls_back_to_label PASSED
AliasDerivationTests::test_sanitize_prompt_truncates_and_strips PASSED
AliasDerivationTests::test_sanitize_prompt_drops_secret_like_material PASSED
SaveAliasTests::test_save_new_alias_appends_and_is_immediately_available PASSED
SaveAliasTests::test_save_replaces_existing_alias_by_id PASSED
SaveAliasTests::test_save_appends_distinct_alias_ids PASSED
SaveAliasTests::test_save_rejects_invalid_alias_via_store_envelope PASSED
SaveAliasTests::test_schedule_save_called_with_ha_store PASSED
SaveAliasTests::test_module_save_validates_alias_before_storage PASSED
SaveAliasTests::test_validate_semantic_alias_contract PASSED
SaveTranche2IntegrationTests::test_remember_true_saves_alias PASSED
SaveTranche2IntegrationTests::test_remember_false_saves_nothing PASSED
SaveTranche2IntegrationTests::test_save_failure_is_non_blocking PASSED
SaveTranche2IntegrationTests::test_saved_alias_skips_clarification_on_next_request PASSED
```

## Eval (clarification → save → inject round trip)

```
python3 evals/semantic_memory_store_envelope.py
PASS semantic_alias_injection
PASS semantic_alias_save_and_reuse     # NEW: derive -> save_alias -> resolve_alias_injection
PASS semantic_memory_store_envelope
```

## Full suite

```
python3 -m pytest tests/ -q
512 passed, 3 failed
```

The 3 failures are the pre-existing codegen-sandbox matplotlib subprocess flake
(not introduced by this packet).

---

## Scenario evidence

### Scenario: Use once — no alias saved

- `remember: false` answer for `climate_kitchen_ecobee`.
- `semantic_memory_store_for(hass, entry_id)` returns `None` (no store written).
- Test: `test_remember_false_saves_nothing` ✓

### Scenario: Use and remember — alias saved

- Prompt `"show me the air conditioning"`, answered with `remember: true` for
  `climate_kitchen_ecobee`.
- Raw in-memory store after save:

```json
{
  "store_version": 1,
  "config_entry_id": "e1",
  "created_at": "2026-06-23T20:42:15.120031+00:00",
  "updated_at": "2026-06-23T20:42:15.120031+00:00",
  "aliases": [
    {
      "alias_id": "climate_kitchen_ecobee",
      "natural_names": ["air conditioning"],
      "meaning": {"type": "entity", "entity_id": "climate.kitchen_ecobee"},
      "source": "user_confirmed",
      "created_from_prompt": "show me the air conditioning",
      "created_at": "2026-06-23T12:00:00+00:00",
      "enabled": true
    }
  ]
}
```

- `alias_id`=`climate_kitchen_ecobee`, `source`=`user_confirmed`,
  `meaning`=`{"type":"entity","entity_id":"climate.kitchen_ecobee"}`,
  `natural_names`=`["air conditioning"]` (action words stripped).
- Test: `test_remember_true_saves_alias` ✓

### Scenario: Duplicate alias_id is replaced

- Saving the same `alias_id` twice leaves exactly one record (the newer one).
- Test: `test_save_replaces_existing_alias_by_id` ✓

### Scenario: Save failure is non-blocking

- `save_alias` patched to return `{"accepted": False}`; the clarification answer
  still succeeds and the snapshot is not `failed` (WARNING logged).
- Test: `test_save_failure_is_non_blocking` ✓

### Scenario: Saved alias is matched on next request (Tranche 1 + 2)

- After saving from `"show me the air conditioning"`, a new job with the reworded
  prompt `"when was the air conditioning on"` resolves
  `climate.kitchen_ecobee` via injection — status is **not**
  `clarification_needed`, and the job renders to `complete`.
- Tests: `test_saved_alias_skips_clarification_on_next_request`,
  eval `semantic_alias_save_and_reuse` ✓

### Scenario: Complete snapshot shows matched aliases

- The reused-alias job's complete snapshot carries
  `aliases: [{"name": "air conditioning", "meaning": "climate.kitchen_ecobee (entity)"}]`.
- Test: `test_saved_alias_skips_clarification_on_next_request` (asserts the
  `aliases` field) ✓

---

## Notes

- The `clarification/answer` handler runs in an executor thread, so `save_alias`
  is synchronous + `Store.async_delay_save` (mirrors `worker_token_lifecycle`).
  See spec acceptance deviations.
- The `IntegrationJobSnapshot.aliases` field already existed in both schema
  copies; only the `append_validated_job_snapshot` passthrough was added.
