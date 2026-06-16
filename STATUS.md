# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-16 (Snapshot poll timeout and single-flight live regression fixed)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Live HACS 0.1.12 snapshot-poll timeout verification`
**Current readiness:** `READY FOR LIVE TEST`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-16** — `Snapshot poll timeout and single-flight live regression` — Live `0.1.11` retest showed the clarification continuation reached `job_orchestration_clarification_continuation_ready`, likely started the Ollama planner, then the dashboard card switched to local `SNAPSHOT_POLL_FAILED` while waiting for `job/snapshot`. The card now retries bounded transient snapshot poll failures such as Home Assistant frontend timeouts instead of immediately replacing an active job with a local failed snapshot, while terminal Isolinear rejections such as `unknown_job` still render visible failure. The backend snapshot artifact/render path now has per-job single-flight protection: overlapping snapshot polls during planner/render work return the current active planning snapshot with `job_orchestration_artifact_snapshot_in_progress` and do not start duplicate planner calls; later polls reuse the completed served PNG artifact. Bumped the visible package version to `0.1.12` for HACS/Lovelace retest and refreshed long-running card/artifact-serving evidence. Verification: focused frontend smoke (`7 passed`), full frontend suite (`11 passed`), focused registered-command smoke (`4 passed`), first-real artifact tests (`10 passed`), adjacent artifact/render/provider/clarification/HACS/resource/integration tests (`61 passed`), relevant evals `PASS`, frontend build passed, architecture review `OK`, BDD-evidence review `OK`, full Python suite (`345 passed`).
- **2026-06-16** — `Read-only model-provider config mapping live regression` — Live `0.1.10` retest showed the clarification path now correctly failed before placeholder artifact success, but the selected-entity continuation could not render because runtime model-provider setup reported `model_provider_planner_not_configured`. The planner setup path still required config-entry `data` to be a plain `dict`; Home Assistant can supply read-only mapping-like config data, the same shape already seen on the allowlist/options side. Model-provider planner setup now accepts mapping-like config-entry data, focused coverage proves `mappingproxy` config data configures the planner and completes with a served PNG artifact, and the visible package version is `0.1.11` for HACS/Lovelace retest. Verification: focused pytest (`10 passed` first-real slice), adjacent pytest (`40 passed` clarification/artifact/card/config/catalog plus `14 passed` HACS/resource), full pytest (`342 passed`), clarification-continuation/artifact-storage/HACS/dashboard-resource evals `PASS`, module `py_compile` passed.
- **2026-06-16** — `Clarification artifact placeholder live regression` — Live `0.1.9` retest showed an ambiguous temperature prompt correctly reached deterministic clarification, but selecting one entity could complete with scaffold placeholder artifact metadata and a broken `/api/isolinear/artifacts/*.png` image. The first-real render path now fails before artifact metadata storage when no configured model-provider planner is available, producing a card-facing failed snapshot with `model_provider_planner_not_configured` instead of placeholder success. Focused coverage now proves the clarification-answer continuation with a configured planner renders a real served PNG for the selected entity and that missing planner state writes no artifact metadata or PNG. Bumped the visible package version to `0.1.10` for HACS/Lovelace retest. Verification: focused pytest (`9 passed` first-real slice), adjacent pytest (`46 passed` first-real/artifact-storage/clarification/card/resource/HACS/integration), full pytest (`341 passed`), clarification-continuation and artifact-storage evals `PASS`.
- **2026-06-16** — `Read-only allowlist mapping live regression` — Live `0.1.8` retest showed the Home Assistant multi-entity picker accepted a dozen temperature sensors, but the dashboard still failed at `approved_entity_catalog` with generic `NO_APPROVED_ENTITIES_AVAILABLE`. Attached logs showed the separate known setup-time schema `read_text` blocking warnings, but no catalog-specific failure. The catalog normalizer now treats config-entry `data` and `options` as mapping-like values rather than requiring plain `dict`, so Home Assistant read-only mapping options from the selector build the runtime catalog instead of silently falling back to an empty allowlist. The options-update regression proof now uses `mappingproxy`, BDD/eval/evidence cover the read-only mapping path, and the visible package version is `0.1.9` for HACS/Lovelace retest. Verification: focused pytest (`62 passed` catalog/config-flow/orchestration/WebSocket/dashboard-resource/HACS), full pytest (`339 passed`), approved-catalog/config-flow/HACS/dashboard-resource/WebSocket/job-orchestration/integration evals all `PASS`.
- **2026-06-16** — `Allowlist picker and unresolved catalog live regression` — Live `0.1.7` retest showed the allowlist text no longer fused separators, but a one-entry allowlist for `sensor.bathrrom_sensor_temperature` still produced generic dashboard `NO_APPROVED_ENTITIES_AVAILABLE`, and HACS did not show the Isolinear icon. The options flow now uses a Home Assistant multi-entity selector while preserving legacy text/list normalization, orchestration surfaces failed catalog setup as `unknown_allowlisted_entity` with the exact missing entity ID before any history read, retry preserves that same structured failure, and the repo now includes root `brand/icon.png` plus `brand/icon@2x.png` for HACS while keeping package-local Home Assistant brand assets. Bumped the visible package version to `0.1.8` and refreshed config-flow/options, job-orchestration, HACS, and approved-catalog evidence. Verification: focused pytest (`27 passed` config-flow/job-orchestration/HACS), full pytest (`338 passed`), config-flow/job-orchestration/HACS/approved-catalog/WebSocket/dashboard-resource evals all `PASS`, `git diff --check` clean aside from normal CRLF warnings.
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Snapshot poll timeout and single-flight live regression`

- [x] Capture the live `0.1.11` behavior: clarification continuation reached ready, then card-local `SNAPSHOT_POLL_FAILED`
- [x] Prove transient snapshot poll timeout keeps polling and later renders a served PNG
- [x] Prove terminal Isolinear snapshot rejections still render visible dashboard failure
- [x] Prove overlapping registered snapshot polls are single-flight and do not duplicate planner calls
- [x] Bump the visible integration package version to `0.1.12` and refresh long-running/artifact evidence

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
- (e) Redownload Isolinear `0.1.12` through HACS, restart Home Assistant,
  recreate the dashboard card, confirm the registered Lovelace resource URL
  includes `?v=0.1.12`, confirm the picker default is `config_entry_id: auto`,
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
