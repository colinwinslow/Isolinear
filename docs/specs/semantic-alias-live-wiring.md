---
status: accepted
date: 2026-06-23
depends-on-adrs: [0010, 0009, 0024, 0003, 0006, 0005]
---

# Semantic alias live wiring: load saved aliases from the per-entry store and inject matched entities into planning

## Status

Accepted. Defines the first live tranche of ADR-0009/0010 semantic memory: the
integration **loads** a persisted per-config-entry alias store, **matches** its
valid aliases against the prompt, and **injects** the matched entity IDs into
the entity selection that feeds planning. Save/propose/confirm (Tranche 2) is
out of scope here.

## Related docs

- [docs/specs/semantic-memory-spec.md](semantic-memory-spec.md) — the memory contract (envelope, read/invalidity/duplicate policy) this wiring obeys
- [bdd/semantic-memory/semantic-alias-live-wiring-bdd.md](../../bdd/semantic-memory/semantic-alias-live-wiring-bdd.md) — observable behavior (paired evidence alongside)
- [docs/bdd/semantic-memory.feature](../bdd/semantic-memory.feature) — source Gherkin (live-wiring scenarios appended)
- [bdd/semantic-memory/persistent-store-envelope-bdd.md](../../bdd/semantic-memory/persistent-store-envelope-bdd.md) — existing store-load/validity proofs reused here (not re-proven)
- [docs/decisions/0009-semantic-memory-storage.md](../decisions/0009-semantic-memory-storage.md) — semantic memory is product-owned, deterministic, reusable
- [docs/decisions/0010-semantic-memory-store-envelope.md](../decisions/0010-semantic-memory-store-envelope.md) — versioned, config-entry-scoped store envelope
- [docs/specs/entity-resolution-spec.md](entity-resolution-spec.md) — the deterministic selector this wiring augments (ADR-0024)
- [STATUS.md](../../STATUS.md) — current phase and active work

## Context

The deterministic entity selector (`select_prompt_entity_ids`, ADR-0024) resolves
an approved entity by overlapping the prompt's tokens with each catalog item's
distinctive tokens. It works only when the prompt's words appear in the entity's
own name/area/device metadata. It cannot resolve a concept whose words are absent
from every approved entity: the live failure of record is "show kitchen temp and
when **the AC** was running" — `climate.kitchen_ecobee` is in the allowlist, but
"AC" shares no token with `climate.kitchen_ecobee` (and the selector's distinctive
tokens drop sub-4-char words anyway), so the climate entity is never selected and
the temperature sensor wins alone.

Semantic memory is the product's answer (ADR-0009): a user confirms once that
"AC" means a specific entity/state/threshold, and the integration reuses that
mapping deterministically thereafter. The store envelope (ADR-0010) and the
`SemanticAlias` / `semantic-memory-store` schemas already exist, and reference
load/validity logic already exists in `src/Isolinear/fake_slice.py`
(`prepare_semantic_memory_for_planning`, `_invalid_semantic_alias_entities`,
`_validate_semantic_memory_store_alias_ids`). What is missing is the **live**
path: a Home Assistant `Store`-backed loader, a generic prompt matcher (the
reference code only hard-codes the "dishwasher running" phrase), and the
injection point into orchestration. This spec defines that path.

## Behavior contract

### 1. Per-entry store load (deterministic, integration-owned)

A new storage helper, mirroring `WorkerTokenLifecycleStorageHelper`, loads the
alias store for one config entry:

```python
class SemanticMemoryStorageHelper:
    storage_key = "isolinear_semantic_memory"   # one HA Store, keyed internally by entry_id
    version = 1
    async def async_load(self) -> None: ...
    def store_for(self, entry_id: str) -> dict | None: ...   # the SemanticMemoryStore envelope, or None
```

- Backed by Home Assistant `Store` when `hass` is available; an in-memory backend
  is used in tests/scaffold (same dual-backend shape as the token lifecycle
  helper).
- The persisted document is keyed by `config_entry_id` (ADR-0010): a load for
  entry A never exposes entry B's aliases.
- **Fail closed** (semantic-memory-spec "Store version and migration policy"): a
  missing store, an unsupported future `store_version`, malformed JSON, or a
  schema-invalid envelope yields **no injected aliases** and a recorded
  `store_error` for diagnostics — never a partial or guessed read.

### 2. Use-time validity (ported, not reinvented)

`prepare_semantic_memory_for_planning(store, entity_catalog)` is ported verbatim
in behavior from the reference implementation:

- Validate the envelope against `semantic-memory-store.schema.json` and the
  duplicate-`alias_id` guard; on failure return `store_error` and zero aliases.
- Skip `enabled: false` aliases (user-suppressed; not invalid, not injected).
- For each enabled alias, compute invalid entities against the **current**
  catalog: a referenced entity absent from the catalog is `entity_unavailable`;
  one present but not `visible_to_agent` is `entity_not_allowlisted`. An alias
  with any invalid entity is excluded from injection (it is surfaced for repair,
  never silently reused — invariant #7).
- Validity is computed at use time and **never mutates the persisted store**
  (semantic-memory-spec "Invalidity policy").

Only aliases that are enabled **and** fully valid are eligible for matching.

### 3. Prompt matcher — token overlap (the design decision)

An eligible alias matches the prompt when **any** of its `natural_names` clears a
token-overlap ratio against the prompt. Defined precisely so it is deterministic
and auditable:

```
prompt_tokens   = tokens(prompt)                       # lowercase [a-z0-9_]+ runs
name_tokens     = tokens(natural_name) − TRIVIAL       # TRIVIAL = {the, a, an, is, was, are, of, and, to, on}
overlap         = |name_tokens ∩ prompt_tokens|
ratio           = overlap / |name_tokens|
match(name)     = name_tokens is non-empty AND overlap ≥ 1 AND ratio ≥ MATCH_RATIO
match(alias)    = any(match(name) for name in natural_names)
```

- `MATCH_RATIO = 0.6` (a single named module constant; the one tuning knob).
  At 0.6, single- and two-token natural names require **all** their tokens
  present (since `0.5 < 0.6`), so a 2-token alias cannot fire on one weak shared
  word — e.g. "dishwasher running" does **not** match "when was the AC running"
  on "running" alone. Names of three or more tokens tolerate one missing token
  (`2/3`, `3/4`, …). This keeps the scoring behavior the decision asked for while
  avoiding single-common-token false positives that would inject a wrong entity.
- **No `len ≥ 4` floor.** The entity selector drops sub-4-char distinctive tokens
  (appropriate for noisy HA entity names); alias `natural_names` are short,
  user-authored phrases where a 2-char token like `ac` is the entire signal.
  Inheriting the floor would defeat the motivating case, so the alias matcher
  tokenizes without it.
- Tokenization reuses the selector's `[a-z0-9_]+` rule so the two systems agree
  on what a "token" is; only the length floor differs, by design.

Worked example: `natural_names: ["AC running"]` → `name_tokens = {ac, running}`;
prompt "show kitchen temp and when the AC was running" → both present →
`ratio = 1.0 ≥ 0.6` → match. `natural_names: ["AC"]` → `{ac}` → "is the AC on?"
→ `ratio = 1.0` → match. Counter-example: `natural_names: ["dishwasher running"]`
against "when was the AC running" → only `running` shared → `ratio = 0.5 < 0.6`
→ no match (no wrong-entity injection).

### 4. Injection into selection (deterministic; not a silent guess)

For every matched valid alias, the entity IDs named by its `meaning` are computed:

| meaning.type | injected entity IDs |
|---|---|
| `entity` | `[entity_id]` |
| `state_interval` | `[entity_id]` |
| `threshold_interval` | `[entity_id]` |
| `aggregate` | `entity_ids` (all) |

These IDs are injected as **resolved selection candidates** at the orchestration
selection site (`select_prompt_entity_ids` in `job_orchestration.py`), composed
with whatever the prompt resolved directly:

- The injected IDs are already approved and `visible_to_agent` (validity in §2
  guarantees it), so selecting them honors the allowlist boundary absolutely
  (invariant #1, ADR-0008/0024).
- Selecting a **user-confirmed** mapping is, by definition, not a silent guess
  (invariant #1): the user already disambiguated "AC" → this entity. So an alias
  match does not trigger clarification for the aliased concept.
- Composition is deterministic and order-stable: directly-resolved entities first,
  then injected alias entities not already present, de-duplicated by `entity_id`.
- The resolution result records `source: "semantic_alias"` (and the matched
  `alias_id`s) so the path is auditable in logs and snapshots, parallel to the
  existing `catalog_label` / `catalog_label_specificity` / `numeric_with_overlay`
  sources.

If no alias matches, selection behaves exactly as today (zero behavior change on
the no-alias / no-match path).

### 5. Tranche boundary

This packet ships **load → match → inject** only. It does **not** write to the
store: there is no propose/confirm/save flow, no card affordance, and no service
or WebSocket command to mutate aliases. Aliases are seeded directly into the
persisted store document for live testing (the documented manual workaround).
Propose/confirm/save is Tranche 2 and gets its own spec + BDD.

## Anchor artifact

The simplest concrete observable proof: with a seeded store holding one enabled,
valid alias `{"alias_id": "whole_house_ac", "natural_names": ["AC", "AC running"],
"meaning": {"type": "state_interval", "entity_id": "climate.kitchen_ecobee",
"active_values": ["cool", "heat"]}}` and a catalog where `climate.kitchen_ecobee`
is approved and visible, the prompt "show kitchen temp and when the AC was running"
resolves to **both** `sensor.kitchen_temperature` (direct) **and**
`climate.kitchen_ecobee` (alias-injected) with `source: "semantic_alias"` — built
before any store-write affordance exists.

## Implementation order

1. **Anchor:** `SemanticMemoryStorageHelper` (in-memory backend) +
   `prepare_semantic_memory_for_planning` port + the token-overlap matcher +
   `alias_entity_ids`, proving the AC alias yields `climate.kitchen_ecobee` as an
   injected candidate from a seeded store, end to end in a unit test.
2. Wire the loader + matcher + injection into `job_orchestration.py` at the
   `select_prompt_entity_ids` site; add `source: "semantic_alias"` and matched
   `alias_id`s to the result and DEBUG logs.
3. HA `Store` backend wired through setup (mirroring
   `get_worker_token_lifecycle_storage`), with the in-memory fallback preserved.
4. Fail-closed coverage: malformed / unsupported-version / schema-invalid store →
   `store_error`, zero injection; disabled alias → not injected; invalid alias
   (`entity_unavailable`, `entity_not_allowlisted`) → not injected.
5. No-match regression: a prompt with no alias overlap resolves identically to the
   pre-wiring selector.

## Proof requirements

1. Unit tests green: store load (happy + each fail-closed branch), validity split
   (disabled / unavailable / not-allowlisted), matcher (match, sub-threshold
   no-match, 2-char token match, trivial-word-only no-match), `alias_entity_ids`
   per meaning type, and the orchestration injection/composition (direct-only,
   alias-only, both, de-dup, no-match passthrough).
2. BDD scenarios in `bdd/semantic-memory/semantic-alias-live-wiring-bdd.md` pass,
   with raw outputs captured in the paired evidence file: AC alias resolves the
   climate entity; disabled/invalid aliases are not injected; malformed store
   fails closed. Store-load/validity is reused from the existing
   `persistent-store-envelope` proofs, not re-proven.
3. Eval: the catalog/selection eval stays green; add or extend an eval CASE
   covering alias-injected resolution.
4. Real-artifact proof on disk: the seeded store document and the resolution
   result showing `source: "semantic_alias"` with both entity IDs.
5. Full suite green except the documented codegen-sandbox flake; patch version
   bump in `manifest.json` + `const.py`.

## Non-goals

- Any store **write**: propose/confirm/save, card affordance, or a mutate
  service/WS command (Tranche 2).
- Memory-management / repair UI, alias deletion or disabling UX (options surface).
- Aggregate/threshold/state-interval **rendering** of the aliased meaning — this
  tranche injects the referenced *entities* into selection; deriving an aggregate
  series or threshold/state overlay from a matched alias is later work.
- Schema migrations beyond version 1 (only `store_version: 1` is persisted today).
- Any change to the allowlist boundary, read-only/sandbox posture, or the
  deterministic render-family routing.

## References

- ADR-0009 (semantic memory is product-owned/deterministic), ADR-0010 (store
  envelope), ADR-0024 (deterministic + model-driven entity selection, augmented
  here), ADR-0003 (allowlist/semantic resolution), ADR-0006 (deterministic plan
  validation), ADR-0005 (schema-first contracts).
- `docs/schemas/semantic-alias.schema.json`,
  `docs/schemas/semantic-memory-store.schema.json`.
- Reference logic: `src/Isolinear/fake_slice.py`
  (`prepare_semantic_memory_for_planning`, `_invalid_semantic_alias_entities`,
  `_validate_semantic_memory_store_alias_ids`).
- Storage precedent: `custom_components/isolinear/worker_token_lifecycle.py`.
- Injection site: `custom_components/isolinear/job_orchestration.py`
  (`select_prompt_entity_ids`).
</content>
</invoke>
