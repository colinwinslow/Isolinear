# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-16 (Allowlist picker and unresolved catalog live regression fixed)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Live HACS 0.1.8 dashboard allowlist/catalog verification`
**Current readiness:** `READY FOR LIVE TEST`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-16** — `Allowlist picker and unresolved catalog live regression` — Live `0.1.7` retest showed the allowlist text no longer fused separators, but a one-entry allowlist for `sensor.bathrrom_sensor_temperature` still produced generic dashboard `NO_APPROVED_ENTITIES_AVAILABLE`, and HACS did not show the Isolinear icon. The options flow now uses a Home Assistant multi-entity selector while preserving legacy text/list normalization, orchestration surfaces failed catalog setup as `unknown_allowlisted_entity` with the exact missing entity ID before any history read, retry preserves that same structured failure, and the repo now includes root `brand/icon.png` plus `brand/icon@2x.png` for HACS while keeping package-local Home Assistant brand assets. Bumped the visible package version to `0.1.8` and refreshed config-flow/options, job-orchestration, HACS, and approved-catalog evidence. Verification: focused pytest (`27 passed` config-flow/job-orchestration/HACS), full pytest (`338 passed`), config-flow/job-orchestration/HACS/approved-catalog/WebSocket/dashboard-resource evals all `PASS`, `git diff --check` clean aside from normal CRLF warnings.
- **2026-06-16** — `Options allowlist runtime catalog live regression` — Live `0.1.6` retest accepted pasted JSON allowlist text but reopened the options field as fused entity IDs and left the running dashboard path with an empty approved catalog, producing `NO_APPROVED_ENTITIES_AVAILABLE`. Stored allowlists now redisplay with comma separators and round-trip through the existing normalizer, config-entry setup registers an options update listener, and options edits refresh the config-entry approved catalog plus allowlist-derived history/orchestration setup metadata before the next dashboard command. Bumped the visible package version to `0.1.7` for HACS/Lovelace retest and refreshed config-flow/options, approved-catalog, HACS, and dashboard-resource evidence. Verification: focused pytest (`21 passed` config-flow/catalog, `19 passed` HACS/resource/integration), full pytest (`337 passed`), config-flow/catalog/HACS/resource/integration/job-state evals all `PASS`, module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings.
- **2026-06-16** — `Dashboard orchestration fallback live regression` — Closed the live `0.1.5` follow-up where card commands reached Isolinear but `job/start` returned the obsolete job-state scaffold (`waiting for a later orchestration packet`, validation `not_run`) instead of the first-real-slice orchestration path. Registered WebSocket dispatch now routes through orchestration once a config entry has completed orchestration setup, even when the approved catalog is empty or unavailable, so an empty allowlist produces deterministic approved-entity failure instead of `orchestration_not_implemented`. Follow-up commands now hit the orchestration job boundary for configured entries, the visible package version is `0.1.6`, WebSocket/resource/HACS evidence was refreshed, and a future large-install allowlist picker UI packet was queued. Verification: focused pytest (`38 passed`), WebSocket/dashboard-resource/HACS/integration evals all `PASS`, module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, architecture re-review OK after earlier standalone review concerns were addressed.
- **2026-06-16** — `Dashboard WebSocket routing schema live regression` — Closed the live `0.1.4` follow-up after a fresh browser proved the cached/legacy placeholder problem was resolved and `config_entry_id: auto` reached the card's WebSocket request. Home Assistant then rejected the valid `isolinear/v1/job/start` envelope as `extra keys not allowed` before Isolinear could strip transport `id`. Registered handlers now use a permissive Home Assistant routing schema so card transport envelopes reach Isolinear's deterministic validator, while unexpected card payload keys still fail closed before orchestration. Bumped the visible integration package version to `0.1.5`, refreshed WebSocket/resource/HACS BDD and evidence, and updated handoff/live retest notes. Verification: focused WebSocket pytest (`14 passed`), dashboard long-running plus first-real-slice pytest (`8 passed`), dashboard-resource plus HACS packaging pytest (`14 passed`), WebSocket/dashboard-resource/HACS/integration evals all `PASS`, module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, standalone architecture review OK.
- **2026-06-15** — `Dashboard legacy config-entry placeholder normalization` — Closed the live `0.1.3` follow-up where Home Assistant showed the correct `/api/isolinear/static/isolinear-card.js?v=0.1.3` resource but the card editor still received the obsolete `fake-config-entry` value. The dashboard card now normalizes that legacy placeholder to `auto` before editor display or WebSocket command submission, with mounted-card regression coverage for both paths. Added package-local Home Assistant brand icons under `custom_components/isolinear/brand/`, bumped the visible integration package version to `0.1.4`, rebuilt the root and packaged card bundles, and refreshed dashboard-card/HACS/resource specs, BDD, eval outline, and evidence. Verification: frontend tests (`9 passed`), frontend build passed, focused dashboard-card/HACS/resource/integration pytest via repo venv (`27 passed`), HACS packaging pytest (`6 passed`), dashboard-card/HACS/dashboard-resource/integration evals all `PASS`, module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, standalone architecture review OK.
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Allowlist picker and unresolved catalog live regression`

- [x] Capture the live `0.1.7` failure: one configured allowlist entity still produced generic `NO_APPROVED_ENTITIES_AVAILABLE`, and HACS did not show the Isolinear icon
- [x] Replace the raw allowlist default UI with a Home Assistant multi-entity selector while preserving explicit entity-ID storage and legacy text/list normalization
- [x] Surface rejected catalog setup as `unknown_allowlisted_entity` with exact missing IDs before any history read instead of generic empty-catalog failure
- [x] Add repository-root HACS brand icons with byte parity against the package-local Home Assistant brand icons
- [x] Bump the visible integration package version to `0.1.8` and refresh config-flow/options, job-orchestration, HACS, and approved-catalog evidence

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Aggregate-style ambiguous entity clarification executable eval
- (b) Aggregate alias creation/reuse executable eval
- (c) Post-MVP floorplan heatmap renderer requiring explicit user-provided room
  geometry and area/entity mappings
- (d) Keep remaining worker/orchestration work split into smaller packets:
  token rotation UI or real Home Assistant Repairs/automatic repair semantics,
  automatic/durable provider retry semantics, durable retry queue/scheduler
  behavior, and any additional durable polling production-hardening follow-up
  requested by review should each land separately.
- (e) Redownload Isolinear `0.1.8` through HACS, restart Home Assistant,
  recreate the dashboard card, confirm the registered Lovelace resource URL
  includes `?v=0.1.8`, confirm the picker default is `config_entry_id: auto`,
  confirm the options flow uses the list-style entity selector and stores the
  exact selected entity IDs,
  confirm HACS shows the repository-root Isolinear brand icon,
  and run the served-artifact prompt path against live Home Assistant sensor
  history.
- (f) Move setup-time schema file reads off the Home Assistant event loop; live
  `0.1.2` logs show blocking-call warnings in worker token lifecycle,
  readiness, and health polling validation.

## Blockers

- None.
