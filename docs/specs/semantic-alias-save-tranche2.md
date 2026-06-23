---
status: draft
date: 2026-06-23
depends-on-adrs: [0009, 0010, 0024, 0003, 0005]
---

# Semantic alias propose and save (Tranche 2)

## Status

Draft. Defines the second live tranche of ADR-0009/0010 semantic memory: when
a user answers an entity-selection clarification with `remember: true`, the
integration **saves** a `SemanticAlias` to the persisted HA Store. Tranche 1
(load/match/inject) is a prerequisite; this spec extends it.

## Related docs

- [docs/specs/semantic-alias-live-wiring.md](semantic-alias-live-wiring.md) — Tranche 1 (load/match/inject)
- [docs/specs/semantic-memory-spec.md](semantic-memory-spec.md) — overall contract
- [bdd/semantic-memory/semantic-alias-save-tranche2-bdd.md](../../bdd/semantic-memory/semantic-alias-save-tranche2-bdd.md) — paired BDD
- [docs/decisions/0009-semantic-memory-storage.md](../decisions/0009-semantic-memory-storage.md)
- [docs/decisions/0010-semantic-memory-store-envelope.md](../decisions/0010-semantic-memory-store-envelope.md)

## Context

Tranche 1 wires the load → match → inject path: if a `SemanticAlias` for "AC"
exists in the HA Store, the next "show kitchen temp and when the AC was running"
prompt resolves `climate.kitchen_ecobee` automatically, without clarification.

Tranche 2 closes the loop: the user creates that alias in the first place.

**Why clarification still happens — and when it won't.** The motivating live
failure ("AC" never selected because `climate.kitchen_ecobee` lacks any
overlapping token with "AC") is being addressed by an expansion to ADR-0024 D2:
after D1 produces a result, D2 always runs as a validation/expansion pass to
catch concepts the prompt named that D1's token scoring missed. With the D2
expansion, a capable model should resolve "show kitchen temp and when the AC was
running" correctly on the first try — no clarification needed. See ADR-0024 D2
expansion note (2026-06-23).

**Why Tranche 2 is still needed.** D2 relies on a model being configured. When
no model is available, when the model abstains, or when the prompt is genuinely
ambiguous ("which thermostat?" with two climate entities), clarification remains
the correct fallback (ADR-0024 D5). Tranche 2 ensures that when the user DOES
answer a clarification, they can make that answer permanent — so the same
question never requires a model call or a clarification again. The semantic alias
system is the long-term memory layer; D2 is the intelligent first-pass resolver;
they are complementary.

The path is the existing `clarification/answer` WebSocket command, which already
carries a `remember: boolean` field (always ignored in the scaffold/Tranche 1).
Currently, `can_remember` is hardcoded `false` on every clarification option, so
the "Use and remember" button is disabled in the card. This spec enables it for
entity-selection clarifications and wires the save.

No new WebSocket command, no new schema shape for the command, and no new ADR
are needed — the architecture is already decided.

## Behavior contract

### 1. `can_remember: true` for entity-selection options

`_clarification_option_for_item` currently returns `can_remember: False` for
every option. Tranche 2 changes this to `True` for all entity-selection
clarifications (those with `question_id: "select_approved_entity"`). The card's
"Use and remember" button is then enabled for every entity option.

`can_remember` remains `False` for any other clarification type (there are none
in the live path today, but this leaves room for future threshold/state-interval
clarifications whose save flow is not yet specified).

### 2. Alias suggestion computed at question-build time

When `_append_clarification_snapshot` builds the clarification question, the
integration also computes a proposed `alias_suggestion` for each option and
stores it in `job["alias_suggestions"][option_id]`. This is **internal job
state only** — it is never serialised to the card-facing snapshot.

The suggestion contains:

```python
{
    "alias_id":     _entity_id_to_alias_id(entity_id),   # see §3
    "natural_names": derive_alias_natural_names(          # see §4
                        prompt, entity_id, entity_label),
    "entity_id":    entity_id,
}
```

### 3. Alias ID generation

```python
def _entity_id_to_alias_id(entity_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", entity_id.lower()).strip("_")
```

Examples: `climate.kitchen_ecobee` → `climate_kitchen_ecobee`.
`sensor.family_room_sensor_temperature` → `sensor_family_room_sensor_temperature`.

Alias IDs are deterministic and stable across sessions. If the same entity is
clarified again and `remember: true`, the existing alias is replaced (overwrite,
not duplicate). See §6 on collision handling.

### 4. Natural name derivation

```python
# Tokens stripped from the prompt before deriving natural names.
# Extends the Tranche 1 trivial set with common chart-action words so
# "show me when" does not pollute the alias name.
_ALIAS_EXCLUDE_TOKENS = {
    "the", "a", "an", "is", "was", "are", "of", "and", "to", "on",
    "show", "display", "chart", "graph", "plot", "when", "what", "how",
    "give", "get", "find", "render", "me", "my",
}

def derive_alias_natural_names(
    prompt: str,
    entity_id: str,
    entity_label: str,
) -> list[str]:
    """Return the natural name(s) to propose for a semantic alias.

    Takes the prompt tokens, removes trivial/chart-action words and the
    entity's own label tokens (length ≥ 4), and returns the remainder as a
    single phrase. Falls back to the entity label when no distinctive tokens
    remain.
    """
    prompt_toks = set(_TOKEN_RE.findall(prompt.lower()))
    prompt_toks -= _ALIAS_EXCLUDE_TOKENS

    entity_toks = set(_TOKEN_RE.findall(
        (entity_id.replace(".", " ") + " " + entity_label).lower()
    ))
    entity_toks = {t for t in entity_toks if len(t) >= 4}

    distinctive = sorted(prompt_toks - entity_toks)
    if distinctive:
        return [" ".join(distinctive)]
    return [entity_label]
```

This function lives in `semantic_memory.py` alongside the Tranche 1 helpers so
the token machinery is shared.

**Worked example** — entity-selection clarification for `climate.kitchen_ecobee`
(label "Kitchen Ecobee") on prompt "show kitchen temp and when the AC was
running":
- Prompt tokens (non-trivial, non-action): `{kitchen, temp, ac, running}`
- Entity tokens (≥ 4 chars): `{kitchen, ecobee}` (from `climate kitchen_ecobee`
  and `Kitchen Ecobee`)
- Distinctive: `{ac, running, temp}`
- → `natural_names: ["ac running temp"]`

This name matches a future prompt "when was the AC running?" (2/3 tokens ≥ 0.6)
and correctly does NOT match "show dishwasher running" (0/3 = 0.0 < 0.6).

The name is imperfect when the prompt mixes multiple concepts ("kitchen temp AND
the AC") because "temp" bleeds in. This is acceptable: the alias still fires on
the right future prompts, and users can revisit Tranche 3 (edit/delete) to
refine if needed.

### 5. Save on `clarification/answer` with `remember: true`

After the clarification entity is accepted (entity validated, snapshot appended)
and before `_defer_history_to_planning`, if `command["remember"] is True` AND
there is an alias suggestion for the selected `option_id` in
`job["alias_suggestions"]`:

1. Build the full `SemanticAlias` record:
   ```python
   {
       "alias_id":           suggestion["alias_id"],
       "natural_names":      suggestion["natural_names"],
       "meaning":            {"type": "entity", "entity_id": suggestion["entity_id"]},
       "source":             "user_confirmed",
       "created_from_prompt": _sanitize_prompt_for_storage(job["prompt"]),
       "created_at":         iso_utc_now(),
       "enabled":            True,
   }
   ```
2. Validate the alias against `semantic-alias.schema.json` before any write.
3. Await `helper.async_save_alias(entry_id, alias)` on the event loop (the
   clarification answer handler runs on the event loop before deferring to the
   executor).
4. On save success: INFO log. The new alias is immediately available for
   Tranche 1 injection in subsequent requests (the in-memory store is updated
   synchronously by `async_save_alias`).
5. On validation failure or save failure: log at WARNING; the job continues
   normally — save failure is non-blocking. A clarification answer with
   `remember: true` that fails to save is indistinguishable from `remember:
   false` from the user's perspective.

`_sanitize_prompt_for_storage(prompt)` strips control characters and truncates
to 200 characters — no secrets are expected but truncation prevents unbounded
storage growth.

### 6. `async_save_alias` in `SemanticMemoryStorageHelper`

```python
async def async_save_alias(self, entry_id: str, alias: dict[str, Any]) -> dict[str, Any]:
    """Persist one alias to the entry's store, replacing any existing record
    with the same alias_id.

    Returns {"accepted": True} on success or {"accepted": False, "error": ...}
    on failure. Always updates the in-memory store before returning, so the
    alias is immediately available for Tranche 1 matching in subsequent
    requests.
    """
```

Implementation:
1. Load the current store for `entry_id` from `self.data["stores"]`, or create a
   fresh valid `SemanticMemoryStore` envelope (version 1, new timestamps).
2. Replace any existing alias with the same `alias_id`; append if new.
3. Update `store["updated_at"]` to now.
4. Validate the whole store envelope before persisting.
5. Write `self.data["stores"][entry_id] = store` so the in-memory state is
   current.
6. Call `await self._ha_store.async_save(self.data)` when an HA store is
   available. In the in-memory backend (tests), skip the async write.
7. Return `{"accepted": True}` on success, `{"accepted": False, "error": ...}`
   on any exception.

### 7. `created_from_prompt` sanitization

`_sanitize_prompt_for_storage(prompt: str) -> str | None`:
- Strip leading/trailing whitespace.
- Truncate to 200 characters.
- Never store secrets: if the prompt matches any secret-like pattern (same
  heuristic as the entity command validator — `sk-…`, JWT, bearer-like tokens),
  store `None` instead.

In practice prompts rarely contain secrets, but this mirrors the existing
boundary hygiene.

## Schema changes

### `IntegrationJobSnapshot`: add optional `aliases` field

The card already reads `snapshot.aliases` in the `complete` render to show which
semantic aliases were used (alongside `snapshot.entities`). Add the field to the
schema so the live complete snapshot can populate it:

```json
"aliases": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["name", "meaning"],
    "additionalProperties": false,
    "properties": {
      "name":    { "type": "string", "pattern": "\\S" },
      "meaning": { "type": "string", "pattern": "\\S" }
    }
  }
}
```

Each entry is built from the matched alias during Tranche 1 injection. The
`name` is `alias["natural_names"][0]`; the `meaning` is a human-readable
string like `"climate.kitchen_ecobee (entity)"`.

The live complete snapshot path (`_produce_complete_snapshot_from_plan`) already
receives the job's entity selection result, which includes `matched_alias_ids`.
Look up each matched alias from the store and build the display entries.

If the store is unavailable or an alias ID can't be found, omit the entry (fail
open — missing display data is not an error).

## Implementation order

1. **`derive_alias_natural_names` + `_entity_id_to_alias_id`** in
   `semantic_memory.py` (pure functions; unit-testable in isolation).
2. **`async_save_alias`** in `SemanticMemoryStorageHelper` (unit-testable with
   the in-memory backend).
3. **`can_remember: True`** in `_clarification_option_for_item` and alias
   suggestion storage in `job["alias_suggestions"]` at question-build time.
4. **Save wiring** in `handle_job_orchestration_clarification_answer_ws_command`:
   when `remember: True` and suggestion exists, build alias → validate → save.
5. **Schema**: add `aliases` to `IntegrationJobSnapshot` (both
   `docs/schemas/integration-job-snapshot.schema.json` and the synced copy
   under `custom_components/isolinear/schemas/`).
6. **Complete snapshot**: populate `aliases` from `matched_alias_ids` in the
   live complete path.

## Proof requirements

1. Unit tests:
   - `derive_alias_natural_names`: prompt-only tokens kept, entity label tokens
     removed, action words removed, falls back to label when empty.
   - `_entity_id_to_alias_id`: correct slugification for domain.entity_id input.
   - `async_save_alias`: new alias appended; same-alias-id replaced; full store
     envelope validated before write; in-memory state updated before return.
   - Clarification answer with `remember: True` + valid suggestion → alias saved.
   - Clarification answer with `remember: True` + save failure → WARNING logged,
     job proceeds normally.
   - Clarification answer with `remember: False` → no save.
2. BDD scenarios (see paired BDD file): use-once, use-and-remember (alias
   saved + available for next request), duplicate alias_id replaced.
3. Complete snapshot `aliases` field populated when aliases were matched.
4. Full suite green except the pre-existing codegen-sandbox flake.
5. Version bump to `0.1.41`.

## Non-goals

- Proposing aliases from chart completion (no "remember this chart" flow).
- Threshold/state-interval alias saving (Tranche 3 — meaning types beyond
  `entity`).
- Alias edit, delete, or disable UX (options surface — future).
- `last_used_at` update when an alias is injected by Tranche 1 (follow-up).
- `natural_names` editing before save — the derived name is used as-is.
- Exposing the proposed natural name in the card-facing option (the "Use and
  remember" button text does not say "as 'AC running temp'" in this tranche).

## References

- ADR-0009 (semantic memory is product-owned/deterministic)
- ADR-0010 (store envelope, versioned, per-config-entry)
- ADR-0024 (deterministic + model-driven entity selection)
- `docs/schemas/semantic-alias.schema.json`
- `docs/schemas/semantic-memory-store.schema.json`
- `custom_components/isolinear/semantic_memory.py` (Tranche 1 implementation)
- `custom_components/isolinear/job_orchestration.py` (clarification/answer handler)
