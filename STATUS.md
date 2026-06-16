# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-16 (Dashboard WebSocket routing schema packet closed)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Live HACS 0.1.5 dashboard WebSocket routing verification`
**Current readiness:** `READY FOR LIVE TEST`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-16** — `Dashboard WebSocket routing schema live regression` — Closed the live `0.1.4` follow-up after a fresh browser proved the cached/legacy placeholder problem was resolved and `config_entry_id: auto` reached the card's WebSocket request. Home Assistant then rejected the valid `isolinear/v1/job/start` envelope as `extra keys not allowed` before Isolinear could strip transport `id`. Registered handlers now use a permissive Home Assistant routing schema so card transport envelopes reach Isolinear's deterministic validator, while unexpected card payload keys still fail closed before orchestration. Bumped the visible integration package version to `0.1.5`, refreshed WebSocket/resource/HACS BDD and evidence, and updated handoff/live retest notes. Verification: focused WebSocket pytest (`14 passed`), dashboard long-running plus first-real-slice pytest (`8 passed`), dashboard-resource plus HACS packaging pytest (`14 passed`), WebSocket/dashboard-resource/HACS/integration evals all `PASS`, module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, standalone architecture review OK.
- **2026-06-15** — `Dashboard legacy config-entry placeholder normalization` — Closed the live `0.1.3` follow-up where Home Assistant showed the correct `/api/isolinear/static/isolinear-card.js?v=0.1.3` resource but the card editor still received the obsolete `fake-config-entry` value. The dashboard card now normalizes that legacy placeholder to `auto` before editor display or WebSocket command submission, with mounted-card regression coverage for both paths. Added package-local Home Assistant brand icons under `custom_components/isolinear/brand/`, bumped the visible integration package version to `0.1.4`, rebuilt the root and packaged card bundles, and refreshed dashboard-card/HACS/resource specs, BDD, eval outline, and evidence. Verification: frontend tests (`9 passed`), frontend build passed, focused dashboard-card/HACS/resource/integration pytest via repo venv (`27 passed`), HACS packaging pytest (`6 passed`), dashboard-card/HACS/dashboard-resource/integration evals all `PASS`, module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, standalone architecture review OK.
- **2026-06-15** — `Dashboard resource cache-busting and websocket observability` — Closed the live `0.1.2` stale-dashboard-resource follow-up. Lovelace now registers the card bundle with a package-versioned resource URL (`/api/isolinear/static/isolinear-card.js?v=0.1.3`) while serving the same stable static asset path, and existing stale Isolinear resource metadata is updated in place instead of reused or duplicated. Registered WebSocket command decisions now record capped runtime-only observability with command type, requested/resolved config entry, acceptance, and code, and `config_entry_id: auto` resolves through Home Assistant's config-entry registry when runtime `hass.data[DOMAIN]` entry data is not enough. Bumped the visible integration package version to `0.1.3`, refreshed dashboard/WebSocket/HACS specs, BDD, eval evidence, and README. Verification: focused dashboard/WebSocket/HACS/integration pytest via repo venv (`39 passed`), frontend tests (`7 passed`), frontend build passed, dashboard-card/dashboard-resource/WebSocket/HACS/integration evals all `PASS`, module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, standalone architecture review OK after contract wording fixes.
- **2026-06-15** — `Dashboard card auto config-entry resolution` — Live dashboard use showed the card picker stub retained `config_entry_id: fake-config-entry`, making `Ask` look inert because the backend rejected the WebSocket command before the card surfaced an error. The card now defaults to `config_entry_id: auto`, start-command rejections render a visible failed snapshot, and the registered WebSocket boundary resolves `auto` to the only configured Isolinear entry while failing closed for zero or multiple entries before orchestration. Bumped the visible integration package version to `0.1.2`, rebuilt the packaged card bundle, refreshed bundled schema byte parity, and documented the explicit config-entry lookup fallback. Verification: focused dashboard/WebSocket/HACS/integration pytest via repo venv (`28 passed`), frontend tests (`7 passed`), frontend build passed, dashboard-card/WebSocket/HACS/integration evals all `PASS`, module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK for the new raw eval case, standalone architecture review OK.
- **2026-06-15** — `HACS options missing config-entry data regression` — Live HACS redownload/restart confirmed the prior commit but options editing still returned base-level `must_be_object` for both plain `sensor.family_room_sensor_temperature` and JSON-style list text. Added a regression proving an options flow whose existing config entry has missing stored setup data accepts the allowlist edit by validating against safe local-first config defaults, while explicit malformed/secret-bearing config data still fails closed. Bumped the visible integration package version to `0.1.1`, anchored manifest/constant version parity, and added the default future packet norm that completed implementation packets increment the patch version unless the human says otherwise. Verification: focused config-flow/integration-scaffold pytest via repo venv (`14 passed`), config-flow/options eval (`PASS`), integration scaffold eval (`PASS`, reports `0.1.1`), module `compileall` passed, stale-version search found no `0.1.0`/`0.2.0` package references, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, standalone architecture review OK.
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Dashboard WebSocket routing schema live regression`

- [x] Confirm live Home Assistant now receives `config_entry_id: auto` from a fresh browser/card module
- [x] Capture the new live failure: Home Assistant rejects `isolinear/v1/job/start` as `extra keys not allowed` before Isolinear strips transport `id`
- [x] Update registered WebSocket command routing schemas so Home Assistant forwards the full card transport envelope to Isolinear validation
- [x] Add focused regression coverage proving valid card envelopes route while unexpected card payload keys still fail inside Isolinear's validator
- [x] Bump the visible integration package version to `0.1.5` for HACS/Lovelace retest
- [x] Refresh focused BDD/evidence for WebSocket routing and resource/HACS version proofs

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
- (e) Redownload Isolinear `0.1.5` through HACS, restart Home Assistant,
  recreate the dashboard card, confirm the registered Lovelace resource URL
  includes `?v=0.1.5`, confirm the picker default is `config_entry_id: auto`,
  and run the served-artifact prompt path against live Home Assistant sensor
  history.
- (f) Move setup-time schema file reads off the Home Assistant event loop; live
  `0.1.2` logs show blocking-call warnings in worker token lifecycle,
  readiness, and health polling validation.

## Blockers

- None.
