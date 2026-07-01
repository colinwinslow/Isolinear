# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-07-01 (ADR-0029 packet 3 IMPLEMENTED — the standalone amd64 worker Dockerfile `worker/Dockerfile` + `.dockerignore`, statically verified, build/run deferred to a Docker host, suite unchanged; on branch `adr-0029-worker-codegen-eval`)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `(on branch \`adr-0029-worker-codegen-eval\`) ADR-0029 packet 4 — codegen path in the model provider + real repair model. Then packet 5 (end-to-end proof + accept/repair reliability eval — the data the keep/remove decision rests on). Still deferred from packet 3: live build + run of the worker image on a linux/amd64 Docker host (CT103) to confirm \`/v1/health\` → \`ready\` and the 3 matplotlib tests un-skip, and to promote the worker-container-image spec draft→accepted. PARKED on main pending the worker-codegen experiment outcome: live HACS retest of 0.1.48 (door timeline + temp/AC overlay via real Ollama); extend legend manifest to timeline/histogram/aggregate_bar; night mode spec+ADR.`
**Current readiness:** `Packet 3 done (worker-only; NO integration code changed; NO version bump — matches packets 1–2). New \`worker/Dockerfile\` (single-stage \`python:3.12-slim\`) + \`worker/.dockerignore\` package the self-contained \`isolinear_worker\` package into a linux/amd64 image. Load-bearing choice: matplotlib installs into the interpreter's SYSTEM site-packages (no venv/\`--user\`), so the sandbox's \`python -I\` subprocess can import it and \`GET /v1/health\` flips not_ready→ready — the packet's whole purpose (dissolves the ADR-0017 matplotlib-on-HAOS blocker). Non-root \`worker\` user (uid/gid 10001); chowned \`work_root\` VOLUME; 12-factor env matching \`load_config_from_env\` (\`ISOLINEAR_WORKER_TOKEN\` runtime-only, never an ENV/layer; fail-closed if missing); stdlib-only HEALTHCHECK gated on \`health.status == "ready"\`; \`ENTRYPOINT ["python","-m","isolinear_worker.http_server"]\`; HA-agnostic (build context \`worker/\`). Docker is NOT installed here, so the image BUILD + container RUN proofs are DEFERRED to a linux/amd64 Docker host (CT103/10.0.1.39): 6 of 9 BDD scenarios (A–F) marked \`DEFERRED (needs Docker host)\` with exact reproduction commands; the 3 STATIC scenarios (G entry-point, H config-contract, I suite-green) carry real raw outputs. Spec left DRAFT (not accepted) until the live build passes — the core proof is that build. Suite unchanged: 595 passed, 3 skipped (the matplotlib skips only flip inside the container). BDD-evidence review OK; architecture review OK (no invariant violations — invariant #3 untouched; base image/non-root/healthcheck/VOLUME within ADR-0029 scope, no new ADR; optional note: digest-pin the base image when first built). Deploy target: CT103/10.0.1.39 standalone amd64 GPU-less Docker via the homelab docker_host role.`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-07-01** — `ADR-0029 packet 3 — standalone amd64 worker Dockerfile (branch \`adr-0029-worker-codegen-eval\`)` — **Worker-only; NO integration code changed; NO version bump (matches packets 1–2).** Committed the implementation `6321215` (`worker/Dockerfile` + `worker/.dockerignore`) plus this doc closeout. A single-stage **`worker/Dockerfile`** (`python:3.12-slim`) packages the self-contained `isolinear_worker` package into a linux/amd64 image. **Load-bearing choice:** matplotlib installs (`pip install -r requirements.txt`, as root) into the interpreter's **SYSTEM site-packages** — no venv, no `--user` — because the sandbox runs generated code under `python -I` (isolated mode excludes user site-packages); only a system-site install lets the packet-2 readiness probe's `python -I -c "import matplotlib"` succeed, so **`GET /v1/health` flips not_ready→ready** and the worker can render. That flip is the whole purpose of this packet (dissolves the ADR-0017 matplotlib-on-HAOS/aarch64 blocker). Non-root **`worker` user (uid/gid 10001)**; chowned `work_root` **VOLUME**; 12-factor env matching packet-2's `load_config_from_env` exactly (**`ISOLINEAR_WORKER_TOKEN` runtime-only — never an `ENV`/layer; fail-closed if missing/short**); **stdlib-only `HEALTHCHECK`** (no curl/wget) that reads token+port from runtime env and exits 0 only on 200 AND `health.status == "ready"`; **`ENTRYPOINT ["python","-m","isolinear_worker.http_server"]`** (packet-2 `__main__` guard). **HA-agnostic by construction:** build context `worker/`, so nothing from `custom_components`/`src`/`frontend` is reachable (`.dockerignore` trims the rest). **Docker is NOT installed here**, so the **image BUILD + container RUN proofs are DEFERRED to a linux/amd64 Docker host (CT103/10.0.1.39):** 6 of 9 BDD scenarios (A–F: build, fail-closed startup, `/v1/health`→ready, `/v1/render` PNG, the 3 matplotlib tests un-skipping, no-HA-code-in-image) marked `DEFERRED (needs Docker host)` with exact reproduction commands — no build log fabricated (repo's live-retest deferral pattern); the 3 STATIC scenarios (G entry-point, H config-contract, I suite-green) carry real raw outputs. **Spec left DRAFT** (not accepted) until the live build passes — the core proof is that build. **Verify:** suite unchanged `595 passed, 3 skipped` (the matplotlib skips only flip inside the container); no integration code touched; no version bump. **BDD-evidence review OK** (all 9 scenarios present; STATIC real, DEFERRED honest with commands). **Architecture review OK** (no invariant violations — #3 sandbox model untouched: system-site matplotlib only makes an already-allowlisted import present, allowlist still governs generated code; #8 base image/non-root/healthcheck/VOLUME within ADR-0029 scope, no new ADR; optional note: digest-pin `python:3.12-slim` at first build). **Next:** packet 4 — codegen path in the model provider + real repair model.

- **2026-07-01** — `ADR-0029 packet 2 — the standalone worker HTTP server (branch \`adr-0029-worker-codegen-eval\`)` — **Worker-only; NO integration code changed; NO version bump (matches packet 1).** Stood up **`worker/isolinear_worker/http_server.py`**: a long-running HTTP front door wrapping the packet-1 `isolinear_worker.codegen_sandbox` public API on the Python stdlib `http.server`/`ThreadingHTTPServer` — **no new runtime dependency** (invariant #8), keeping the packet-3 image minimal. Serves the ADR-0012 transport **`POST /v1/render`** + the ADR-0014 **`GET /v1/health`** readiness probe. **Fail-closed ordering, every request:** auth → API-version → schema → sandbox; bearer auth via constant-time `hmac.compare_digest`; **no sandbox subprocess for an unauthenticated request**; token redacted to `Bearer <redacted>` in responses/logs. **Transport/sandbox split:** sandbox-level failures (`unsafe_code`/`runtime_error`/`timeout`) ride **inside HTTP 200** as `{"render_result": ...}` (a valid render outcome, not a fault); transport faults are non-200 — 401 `unauthorized`, 400 `unsupported_api_version`/`invalid_request`. **12-factor/HA-agnostic config:** `ISOLINEAR_WORKER_TOKEN` (≥24 chars, **fail-closed at startup** — missing/short exits 1 with no socket bound), bind host/port, `work_root`; `create_worker_app(config)` is socket-free/unit-testable, `serve(config)` / `python -m isolinear_worker.http_server` bind and serve. **Imports nothing from `custom_components`/`src`** (import-graph test); the only cross-boundary import lives in the wire-interop *eval*, not the server. **`GET /v1/health`** returns the `integration-worker-health` `response` sub-schema under `{"health": ...}` (200 in both states); on the dev box reports **`not_ready`/matplotlib-`unavailable`** because `-I` can't import user-site matplotlib (expected — flips to `ready` in the packet-3 container). Single `invoke_codegen_sandbox` call (no repair loop — packet 4); `image_path` returned as-is (no base64 — packet 5). New **`tests/test_worker_http_server.py`**; **`evals/worker_http_server.py`** drives the **real `HttpJsonWorkerRenderClient`** against a loopback server. **Verify:** suite `595 passed, 3 skipped` (the 3rd skip is the new matplotlib-render scenario, same `-I`/user-site limitation as packet 1's 2 skips); `evals/worker_http_server.py` PASS; `evals/codegen_sandbox.py` PASS. **BDD-evidence review OK** (all 9 scenarios A–I present with raw outputs, recent run timestamp, no drift); **architecture review OK** (no invariant violations; #2/#3/#8 + the ADR-0029 HA-agnostic boundary clean; note: `_read_body` returns `b""` on oversized/invalid Content-Length → generic `invalid_request` 400, acceptable fail-closed, deferred refinement). Spec + BDD promoted draft→accepted (+ specs README). **Not version-bumped** (worker-only). **Next:** packet 3 — standalone amd64 Dockerfile with matplotlib.

- **2026-06-30** — `ADR-0029 packet 1 — promote codegen sandbox to a self-contained worker module (branch \`adr-0029-worker-codegen-eval\`)` — **Worker-only; NO integration code changed.** Promoted the proven codegen sandbox from the `src/Isolinear/codegen_sandbox_anchor.py` anchor into a new self-contained, HA-agnostic worker package **`worker/isolinear_worker/`**: `codegen_sandbox.py` (sandbox, scaffolding/fixtures/verifier stripped), a standalone `_schema_validation.py` (deliberate subset-copy of `contracts.py` — the worker must not import `src`/`custom_components`), 5 schemas bundled under `worker/isolinear_worker/schemas/`, `__init__.py` re-exporting the public API, and `worker/requirements.txt`. **Public-API changes (documented in the spec's deviation note):** `invoke_codegen_sandbox(render_request, *, policy, work_root, attempt_number)` — dropped `repo_root` (schemas bundled), `output_directory`→`work_root`; `invoke_codegen_with_repair(..., *, repair, max_attempts, work_root)` — anchor's `repaired_python_codes` list replaced by an injected `repair(prev_code, error)->next_code` callable (real repair model = packet 4); `static_safety_check` keeps the `accepted` key. New **`tests/test_codegen_sandbox.py`** drives the public API for sandbox-codegen scenarios A-G + promotion B/D/E (self-containment via `sys.modules` import-graph in a clean subprocess; schema-drift guard; injected-repair loop; timeout), with the **matplotlib-rendering scenarios `skipUnless` the `-I` sandbox can import matplotlib** (user-site-only on the dev .venv → skip; runs on the worker container). Shared fixtures in `tests/codegen_sandbox_fixtures.py`; `evals/codegen_sandbox.py` repointed to the module (drives public API, matplotlib branch conditional). **Anchor retired:** deleted `src/Isolinear/codegen_sandbox_anchor.py` + `tests/test_codegen_sandbox_anchor.py`. **Verify:** suite `584 passed, 2 skipped` (was `581 passed, 3 pre-existing codegen-sandbox failures` — those 3 matplotlib-in-`-I` failures are now honest skips); `evals/codegen_sandbox.py` `PASS`; real 1×1 PNG produced through the promoted public API and eyes-on-confirmed via `file`. BDD-evidence review OK; architecture review **OK** (no invariant violations — sandbox security model preserved at parity; HA-agnostic boundary verified) — its one recommendation (guard the duplicated schemas against drift) applied as `test_bundled_worker_schemas_match_canonical_docs_schemas`. Spec + BDD promoted draft→accepted (+ specs README); ADR-0029 stays draft (experiment kill-condition pending). **Not version-bumped** (worker-only). **Next:** packet 2 — the worker HTTP server.

- **2026-06-30** — `Worker revival for codegen evaluation — ADR-0029 + packet 1 spec (planning; branch \`adr-0029-worker-codegen-eval\`)` — **No integration code changed.** Opened as a rewrite-vs-refactor evaluation (Colin suspected brittleness from pre-pivot "codex off the rails"). **Finding:** architecture is sound; brittleness concentrates in `job_orchestration.py` (7.2K LOC). The "dead weight" worker tree is **NOT** safe-delete — it's load-bearing (`__init__.py` aborts setup without `worker_token_lifecycle`; `job_orchestration.py:55` imports `worker_renderer`) and ADR-0017 *defers* it deliberately. **Direction (Colin):** rendering model-generated matplotlib was always the plan; the in-process Pillow pivot happened only because matplotlib won't install on HAOS/aarch64 (Alpine). A worker dissolves that (matplotlib in its own amd64 image). **Decided:** revive the worker as a deployment-agnostic HTTP service running the existing sandbox (`src/Isolinear/codegen_sandbox_anchor.py`) to evaluate codegen quality on a 3060-class local model — **experiment with a kill condition:** if codegen isn't good enough, delete the worker subsystem and refactor to in-process only. Hard part already exists (sandbox + integration client); **missing = the worker HTTP server.** Wrote **ADR-0029** (draft) + **data-boundary clarification** (entity selection/allowlist/history stay integration-side; only normalized allowlisted data crosses; worker never queries HA — defense-in-depth with the sandbox) + **packet 1 spec/BDD** (`codegen-sandbox-module-promotion`: promote anchor → self-contained `worker/isolinear_worker/`, retire anchor at green parity; doc indexes synced). **Deploy target pinned:** CT103/10.0.1.39 (the ollama box), standalone amd64 GPU-less Docker via the homelab `docker_host` Ansible role (two-repo split: Isolinear publishes the image, homelab deploys; waits on the in-flight docker_host role). 3 commits on branch, not pushed; memory updated (worker = revived-core, not dead weight; deployment note). **Verify:** suite `581 passed, 3 pre-existing codegen-sandbox failures` (unchanged baseline — no implementation this session). **Next:** implement packet 1 (BDD-first), then packet 2 (HTTP server).

- **2026-06-27** — `ADR-0028 model-validated composition membership (0.1.48) + 0.1.47 live retest` — **0.1.47 live retest:** card legend, model summary caption, AC split swatch, histogram, aggregate_bar, fuzzy/90-day window resolution, `no_long_term_statistics` gate, and reasoning streaming all **PASS** live. Two prompts failed at `model_provider_planner_not_chart_spec_ready`: "when was the kitchen door open today" and "show kitchen temp and when the AC was running". **Root cause (diagnosed from the live debug log + reproduced against live `gemma4:e4b`):** NOT a planner bug — an entity-selection **over-composition** bug. `select_prompt_entity_ids` composes any numeric + state match sharing a prompt token, and "kitchen" noise-matched `sensor.kitchen_ecobee_temperature`: for the door prompt the temp sensor became the chart *primary* and the door was demoted to an overlay (planner clarified "which entity tracks the door?"); for the temp+AC prompt `binary_sensor.kitchen_door` entered as a *spurious second overlay* that tipped the planner into clarification. The overlay path short-circuited at `job_orchestration.py:2146` **before** the ADR-0024 D2 validation pass ever ran. **Fix (ADR-0028, lean-on-model per Colin's steer):** route the multi-match composition through the existing D2 `select_entity` selector to prune noise matches, gated on `_composition_has_shared_token`; the pruned set re-routes through the deterministic `_resolve_render_family` by kind (invariant #9 intact) and is re-validated against the allowlist (invariant #1 intact). New `_prune_composition_with_model` + `_composition_has_shared_token`; fail-soft to the deterministic composition on model abstain/failure/no-planner. Empirically the live selector prunes both cases correctly from friendly names alone (no schema/disclosure change needed). **Verify:** `tests/test_composition_membership.py` (9), `evals/composition_membership_prune.py` (3 CASEs), full suite `581 passed, 3 pre-existing matplotlib-sandbox flakes`; BDD evidence with raw live-model outputs; architecture review `CONCERNS→resolved` (its one finding — spec described kind/area/matched_tokens disclosure the code doesn't build — fixed by aligning the spec to the id+label implementation). ADR-0028/spec/BDD promoted draft→accepted. Bump `0.1.48`. **Next:** live HACS retest of the two prompts.

_(older sessions — ADR-0027/0.1.47, ADR-0023/0.1.44, ADR-0026/0.1.43 and earlier — live in git history)_
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Worker revival for codegen evaluation (ADR-0029)` — PLANNING (branch `adr-0029-worker-codegen-eval`, not pushed)

- [x] Rewrite-vs-refactor review: architecture sound; worker tree is load-bearing, not dead weight; brittleness centers on `job_orchestration.py`
- [x] ADR-0029 (draft) — revive worker to evaluate sandboxed codegen; kill condition if 3060-class model codegen is insufficient
- [x] ADR-0029 data-boundary constraint — entity selection/allowlist/history stay integration-side; only normalized allowlisted data crosses; worker never queries HA
- [x] Packet 1 spec + BDD (`codegen-sandbox-module-promotion`, draft) — promote anchor → self-contained `worker/isolinear_worker/`; doc indexes synced
- [x] Deploy target pinned: CT103/10.0.1.39 standalone amd64 GPU-less Docker via homelab `docker_host` role; two-repo split; memory recorded
- [x] **Packet 1 implementation** — stood up `worker/isolinear_worker/` (sandbox + standalone validator + bundled schemas + requirements), `tests/test_codegen_sandbox.py` parity A-G via public API (+ self-containment + schema-drift guard), repointed eval, retired anchor; suite `584 passed, 2 skipped`; spec+BDD accepted
- [x] **Packet 2 implementation** — stood up `worker/isolinear_worker/http_server.py` (stdlib `http.server`, no new dep — invariant #8) wrapping the packet-1 sandbox: `POST /v1/render` + `GET /v1/health`, fail-closed auth→version→schema→sandbox ordering, sandbox failures inside 200 / transport faults 401/400, 12-factor `ISOLINEAR_WORKER_TOKEN` (≥24 chars, fail-closed startup)/host/port/work_root, HA-agnostic (import-graph verified); `tests/test_worker_http_server.py` + wire-interop `evals/worker_http_server.py` (real `HttpJsonWorkerRenderClient`); suite `595 passed, 3 skipped`; both reviews OK; spec+BDD accepted; NOT version-bumped
- [x] **Packet 3 — standalone amd64 Dockerfile with matplotlib** — `worker/Dockerfile` (single-stage `python:3.12-slim`) + `worker/.dockerignore`: matplotlib installed into SYSTEM site-packages so the `-I` sandbox imports it and `/v1/health` flips ready; non-root `worker` (uid/gid 10001), chowned `work_root` VOLUME, 12-factor env (`ISOLINEAR_WORKER_TOKEN` runtime-only), stdlib-only HEALTHCHECK gated on `status == "ready"`, `python -m isolinear_worker.http_server` entry point, HA-agnostic (context `worker/`); committed `6321215`; suite unchanged `595 passed, 3 skipped`; both reviews OK; NOT version-bumped. **Build/run proof DEFERRED to a linux/amd64 Docker host** (6 of 9 BDD scenarios A–F deferred with exact commands; spec left draft until it passes)
- [ ] **Live: build + run the worker image on a linux/amd64 Docker host (CT103/10.0.1.39)** — confirm the image builds, `/v1/health` → `ready`, `/v1/render` returns a PNG, the 3 matplotlib-gated tests un-skip in-container, and no HA code ships; then promote the `worker-container-image` spec draft→accepted
- [ ] Packet 4 — codegen path in the model provider + real repair model
- [ ] Packet 5 — end-to-end proof + codegen accept/repair reliability eval (the data the keep/remove decision rests on)
- [ ] **Coordination:** homelab worker-service deploy waits on the in-flight `docker_host` role landing

### `ADR-0028 model-validated composition membership (0.1.48)` — SHIPPED

- [x] `select_prompt_entity_ids` carries `candidate_items` on the `numeric_with_overlay` result
- [x] `_composition_has_shared_token` gate (fires only when ≥2 candidates share a prompt token)
- [x] `_prune_composition_with_model` — routes the composition through the ADR-0024 D2 `select_entity` selector; uses the pruned subset, fails soft to the deterministic composition on abstain/failure/no-planner/empty/unchanged
- [x] New branch in `_resolve_entity_selection_with_model` for `source: numeric_with_overlay`; pruned set re-routes through `_resolve_render_family` by kind (invariant #9) and re-validates against the allowlist (invariant #1)
- [x] No schema / `model_provider.py` change — friendly-name disclosure prunes both cases (live-confirmed)
- [x] `tests/test_composition_membership.py` (9) + `evals/composition_membership_prune.py` (3 CASEs); full suite `581 passed, 3 pre-existing matplotlib flakes`
- [x] BDD evidence with raw live `gemma4:e4b` outputs; architecture review `CONCERNS→resolved` (spec aligned to id+label disclosure)
- [x] ADR-0028 + spec + BDD promoted draft→accepted; decisions README updated; version bumped `0.1.48`
- [ ] **Live HACS retest:** "when was the kitchen door open today" → door timeline; "show kitchen temp and when the AC was running" → temp + AC overlay; both complete with no spurious clarification

### `ADR-0027 card-owned legend + model summary/overlay labels (0.1.47)` — SHIPPED

- [x] Renderer emits `render_metadata.legend` manifest (`{label, entity_id, color, kind, states?}`); in-PNG legend removed for `time_series`/`time_series_overlay`
- [x] Model authors `chart_spec.summary` (required in constrained-decoding schema) and `planner_result.overlay_labels` `{entity_id: label}`; prompt updated
- [x] `_compose_state_overlays` applies model overlay label with deterministic fallback (model → friendly name → `"<id> — running state"`)
- [x] `summary` + `legend` threaded through artifact into `snapshot.chart`; alias display entries gain `entity_id`
- [x] Card: caption = summary↦title (no prompt echo); interactive **Legend** (swatch + label, flip-down with entity_id + matched alias, split swatch + per-state children, label guard, graceful empty state)
- [x] 6 schemas extended (chart-spec, planner-result, render-result, artifact-metadata, job-snapshot; docs + cc copies synced; all optional/back-compat)
- [x] ADR-0027 + spec + BDD + evidence written, promoted draft→accepted; doc indexes updated
- [x] 565 Python tests pass (3 pre-existing matplotlib flakes excluded); 21 frontend tests (8 new); anchor PNG eyes-on clean; BDD-evidence + architecture reviews OK
- [x] Version bumped to `0.1.47`; pushed origin/main `7ceddc5`
- [x] **Live HACS retest (2026-06-27):** summary caption reads as a sentence, the AC split swatch expands to cooling/heating children, legend labels descriptive — all PASS via real Ollama
- [ ] **Follow-up (deferred, discussed):** extend the legend manifest + external legend to `timeline` / `histogram` / `aggregate_bar`

### `ADR-0023 render-family capability envelope — histogram + aggregate_bar (0.1.44)` — SHIPPED

- [x] `_resolve_render_envelope` in `job_orchestration.py` — wraps `_resolve_render_family`, produces `families` / `shape` / `default_family`; single_numeric → 3-family; all others → existing single-member
- [x] `validate_model_provider_chart_family` gate — rejects out-of-envelope `chart_type` post `validate_chart_spec_contract`, no-op for single-member (backward compat)
- [x] `load_planner_result_schema` extended with `envelope` arg — multi-family: widens `chart_type`+`render_as` enums, allows `source.type: aggregate` when aggregate_bar in envelope; entity_id pin unchanged
- [x] Multi-family prompt guidance in `_chat_payload` — intent-based family guidance replaces hardcoded single rule
- [x] `_render_histogram_png` — bins numeric history, Pillow bars+axes, fail-soft (zero points → failure, any other count → thin valid PNG)
- [x] `_render_aggregate_bar_png` — groups by day/hour, applies 5 operations (mean/min/max/sum/count), Pillow bars, same fail-soft rule
- [x] `render_in_process_chart` dispatch extended: histogram branch + bar branch alongside existing time_series/timeline
- [x] Spec+BDD promoted draft→accepted; `bdd/rendering/render-family-capability-envelope-evidence.md` written (8 scenarios A–H)
- [x] 42 new tests in `tests/test_render_family_capability_envelope.py`; 3 new eval CASEs in `evals/timeline_render_family_routing.py`
- [x] Full suite `554 passed, 3 pre-existing codegen-sandbox flakes`; all 7 eval CASEs PASS
- [x] Version bumped to `0.1.44`
- [x] **Live HACS retest (2026-06-27):** "show the distribution of bathroom temp" → histogram and "family room average temperature per day" → aggregate bar both complete via real Ollama — PASS

### `Semantic alias Tranche 2 — propose/confirm/save (0.1.42)` — SHIPPED

- [x] `derive_alias_natural_names` + `_entity_id_to_alias_id` + `_sanitize_prompt_for_storage` + `validate_semantic_alias_contract` in `semantic_memory.py`
- [x] `SemanticMemoryStorageHelper.save_alias` — synchronous (executor-thread safe), validates store envelope, updates in-memory, `async_delay_save(…,0)`; module `save_semantic_alias`
- [x] `can_remember` opt-in param on `_clarification_option_for_item` (entity selection passes `True`; other types default `False`); `job["alias_suggestions"]` precomputed in `_append_clarification_snapshot`
- [x] `_maybe_save_semantic_alias` wired into clarification-answer handler (remember:true, non-blocking on failure)
- [x] Complete snapshot `aliases` display via `_alias_display_entries` + `append_validated_job_snapshot` passthrough (schema field pre-existing; no schema change)
- [x] Spec accepted with deviation notes (sync save, schema already present, version 0.1.42); BDD evidence written
- [x] 17 unit/integration tests; eval CASE `semantic_alias_save_and_reuse`
- [x] Architecture review OK; review suggestions applied (can_remember gate, `_schedule_save` delay=0 comment)
- [x] Full suite `512 passed, 3 pre-existing codegen-sandbox failures`; bump `0.1.42`
- [ ] **Live HACS `0.1.42` retest:** answer an entity clarification with "Use and remember", then confirm the same concept reworded skips clarification next time

### `ADR-0024 D2 expansion (0.1.41)` — SHIPPED

- [x] `_resolve_entity_selection_with_model` unifies residue + expansion gating at both orchestration call sites; `_run_model_entity_selection` gained `d1_selected_ids`
- [x] Expansion runs after confident `catalog_label`/`catalog_label_specificity` D1 results against the full catalog; skipped for explicit-id/overlay/semantic_alias and full-catalog-covered cases
- [x] Safe fall-back: model abstain/absent/off-catalog → D1 result stands (off-catalog fails closed, invariant #1)
- [x] HA domain hint added to `select_entity` prompt (`model_provider.py`)
- [x] Spec + ADR-0024 expansion note + BDD Scenarios F–I + evidence updated
- [x] 11 new tests; full suite `495 passed, 3 pre-existing failures` at packet close; bump `0.1.41`
- [x] Architecture review OK
- [ ] **Live HACS `0.1.41` retest:** "show kitchen temp and when the AC was running" resolves both the temp sensor and `climate.kitchen_ecobee` with no clarification (no alias needed)

### `Semantic alias live wiring Tranche 1 (0.1.40)` — SHIPPED

- [x] `SemanticMemoryStorageHelper` — dual-backend (HA Store / in-memory), per-entry scoped, `async_load` + `store_for` + `seed_store`
- [x] `prepare_semantic_memory_for_planning` — schema + duplicate-alias-ID validation, use-time validity (unavailable/not-allowlisted), never mutates store
- [x] `alias_matches_prompt` — `[a-z0-9_]+` tokenization, `MATCH_RATIO=0.6`, no 4-char length floor, trivial stop words stripped
- [x] `resolve_alias_injection` — full pipeline; `_inject_semantic_aliases` composes with direct selection, de-duplicated, `source: "semantic_alias"` recorded
- [x] Wired into `async_setup_entry` via `async_setup_semantic_memory`; wired into `job_orchestration.py` after `select_prompt_entity_ids`
- [x] 33 unit tests passing; 7 BDD scenarios; eval anchor CASE `semantic_alias_injection` in `evals/semantic_memory_store_envelope.py`
- [x] Architecture review: 9 invariants checked, no violations (allowlist boundary preserved, no store write, deterministic)
- [x] Spec `docs/specs/semantic-alias-live-wiring.md` status updated to `accepted`
- [x] Evidence file `bdd/semantic-memory/semantic-alias-live-wiring-evidence.md` written
- [x] Full suite: `484 passed, 3 failed` (pre-existing codegen-sandbox flake); bump `0.1.40`

### `Concurrent polling fix — reasoning now visible in card (0.1.38)` — SHIPPED

- [x] Root cause: snapshot poll loop was sequential (await response → schedule next); first post-submit poll acquires `planning_lock` for ~40 s → no second poll during think pass → in-progress snapshots never delivered
- [x] Fix (`isolinear-card.ts`): call `scheduleSnapshotPoll(generation)` before `await getSnapshot()` so polls fire at 1 s intervals regardless of response time; concurrent polls hit held lock, return in-progress snapshot with reasoning
- [x] Tests: bump smoke test poll interval 5 ms → 20 ms so mock response (5 ms) always resolves before pre-scheduled poll fires
- [x] Drift: ADR-0025 D3 unchanged; evidence file updated with 0.1.38 fix note
- [x] Architecture review: not run (frontend-only polling bug fix, no invariant affected, no new decision)
- [x] Verify: `451 passed, 3 failed` (pre-existing codegen flake), frontend `13 passed`, `prompt_to_chart_basic` + `dashboard_card_anchor` evals PASS, BDD-evidence review OK, bump `0.1.38`
- [x] **Live HACS `0.1.38` retest (Edge/Windows):** temperature+AC prompt still failed — `climate.kitchen_ecobee` IS in the allowlist but entity name has no token overlap with "AC"; temperature sensor wins specificity scoring (3 tokens vs 2). Reasoning streaming still not visible — polling code IS correct in deployed bundle; most likely cause is Edge serving cached pre-0.1.38 JS despite `?v=0.1.38`. Diagnostic: Edge DevTools → Network → filter "isolinear" to confirm URL. Root fixes: semantic alias live wiring (packet #1) for AC; browser cache investigation for streaming.

### `Planning rules fix — clarify on unavailable entities (0.1.37)` — SHIPPED

- [x] Root cause: `_chat_payload` planning rule 2 said "Return status chart_spec_ready with a ChartSpec for this packet" unconditionally; with the 0.1.36 format-constrained pass the model satisfied it on out-of-allowlist prompts by relabeling/reusing one approved entity into two series (e.g. one temperature sensor → "Room Temperature" + "Kitchen AC Status")
- [x] Fix (`model_provider.py` `_chat_payload` rules): replaced the unconditional rule with three — (1) `clarification_needed` when the prompt references a device/sensor/concept not represented by any approved entity (never invent/relabel/reuse); (2) `chart_spec_ready` only if every requested piece is satisfiable with approved entities; (3) each series must be a distinct approved entity, never multiple series for the same `entity_id`
- [x] Drift: none — `plan_chart` docstring documents the two-pass streaming mechanism, not the prompt rule content; statuses + clarify-not-guess behavior already documented (Invariant 1, entity-clarification/allowlist BDD). No schema/spec/ADR/BDD change for a prompt-engineering fix
- [x] Verify: tested live against Ollama (the "maren's room temperature and when the AC was running" out-of-allowlist prompt now returns `clarification_needed`); full suite `451 passed, 3 failed` (pre-existing codegen flake), model-provider planning eval PASS, BDD-evidence review OK, bump `0.1.37`

### `Two-pass reasoning streaming (0.1.36)` — SHIPPED

- [x] Root cause: 0.1.35 dropped `format` from streaming calls to unblock `think`, but without constrained decoding the model produced structurally invalid JSON on harder prompts → `invalid_planner_result` on out-of-allowlist prompts
- [x] Fix (`model_provider.py`): two-pass approach when `on_reasoning` is provided — Pass 1 `stream:true, think:true, no format` (reasoning, content discarded, failures non-fatal); Pass 2 `stream:false, format:result_schema, no think` (reliable validated result). Applied to both `plan_chart` and `select_entity`
- [x] `on_reasoning is None` path unchanged (sole call = Pass 2 / D6 fallback)
- [x] Drift: ADR-0025 D1 "two-pass correction (0.1.36)" note + streaming spec "Streaming planner transport (D1)" section rewritten for two-pass; no contract/schema/BDD change
- [x] Tests: updated 5 cases in `tests/test_live_planner_reasoning_streaming.py` for the two-call pattern (route fake_urlopen on the `stream` flag); `30 passed`
- [x] Verify: full suite `451 passed, 3 failed` (pre-existing codegen flake, identical on clean baseline via `git stash`), planning eval PASS, BDD-evidence review OK, bump `0.1.36`
- [ ] **Live HACS `0.1.36` retest (non-blocking):** confirm the previously-failing "show me temperature and when the AC was running" out-of-allowlist prompt now returns valid structure (Pass 2 constrained decoding) while reasoning still streams (Pass 1)

### `Reasoning-streaming think/format fix + temperature stopword fix (0.1.35)` — SHIPPED

- [x] Fix 1 (`model_provider.py`): make `think` and `format` mutually exclusive — streaming (reasoning) calls send `think: true` only; non-streaming calls keep `format`. Ollama suppresses thinking when `format` is set, so this was the last blocker to live reasoning streaming for thinking-capable models
- [x] Fix 1: add `_strip_markdown_json` to strip code fences thinking-mode models wrap around JSON when `format` is absent (applied in both planner + entity-selector JSON parse sites)
- [x] Fix 2 (`job_orchestration.py`): remove `"temperature"` from the distinctive-token exclusion set so it counts toward specificity scoring (ecobee temp sensor outscores a co-located door sensor instead of tying)
- [x] Drift: correction note added to ADR-0025 D1 + streaming spec line 94 (the `format`-governs-content claim the discovery invalidated); entity-resolution ADRs/spec needed no change (scoring described abstractly, stopword set not enumerated)
- [x] Refresh live-planner-reasoning BDD evidence raw block (`30 passed`, was stale at `23`) + 0.1.35 fix note
- [x] Verify: full suite `451 passed, 3 failed` (pre-existing codegen flake, identical on clean baseline), model-provider/streaming/entity-resolution evals PASS, BDD-evidence review OK, bump `0.1.35`
- [ ] **Live HACS `0.1.35` retest (non-blocking):** confirm reasoning text appears in the chart slot during planning with a thinking-capable Ollama model; "last 4 hours" resolves to a 4-hour window

### `ADR-0025 live planner reasoning streaming (0.1.32) + bug fixes (0.1.33) + redaction hardening (0.1.34)` — SHIPPED

- [x] 0.1.32: streaming planner (`stream: true`), `sanitize_reasoning` + 2000-char rolling cap, per-job live-reasoning slot, `progress.reasoning` + phase label on planning snapshot, replaced by chart on completion, never persisted; spans both model calls; Lit card chart-slot rendering; frontend bundle rebuilt + synced
- [x] 0.1.33 bug fix 1: send `"think": true` on streaming planner + entity-selector requests so thinking-capable Ollama models actually stream
- [x] 0.1.33 bug fix 2: `_parse_window_timestamp` treats naive ISO 8601 datetimes as UTC instead of forcing the 24h fallback
- [x] 0.1.34 (closeout): `sanitize_reasoning` now also redacts named secret vocabulary (`access_token`/`*_token`/`ollama_api_key`/`api_key`) + bare `sk-…`/JWT tokens (architecture-review finding; invariant-3 / ADR-0025 D5 gap); 4 new redaction tests
- [x] Verify: full suite `451 passed, 3 failed` (pre-existing codegen flake), all evals PASS, BDD-evidence review OK, architecture review CONCERNS→resolved, bump `0.1.34`

### `Render-family capability envelope (ADR-0023) — ACCEPTED, not implemented`

- [x] ADR-0023 **accepted** (commit `5010302`); `docs/specs/render-family-capability-envelope.md` + `bdd/rendering/render-family-capability-envelope-bdd.md` remain `draft` (accept when the implementation anchor lands)
- [ ] Implement per the spec's order: histogram anchor → out-of-envelope gate → aggregate_bar → fail-soft/no-data coverage → single-member regression

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
- (e) Live HACS `0.1.23` retest of the model-resolved window + statistics path
  (the `0.1.20` Pillow load + render was already confirmed live; `0.1.21`
  legibility/fonts shipped on top; live `0.1.22` confirmed single-entity
  long-term-statistics charts render correctly). Confirm: a fuzzy/relative
  prompt (e.g. "attic temperature last weekend") resolves a sane bounded window
  and renders; a long window (e.g. "last 90 days") against a `state_class`
  sensor renders a **daily statistics** chart with a min/max band (not 24h, not
  empty); a **numeric** non-`state_class` entity over a beyond-retention window
  shows a card-facing `no_long_term_statistics` failure (not a silent empty
  chart). Also confirm the `0.1.23` executor hygiene fixes landed: the
  setup-time schema `read_text`/`open` blocking warnings and the recorder
  "accesses the database without the database executor" warnings
  (`get_significant_states`, `statistics_during_period`) **no longer appear** in
  HA logs. Capture HA logs for any `statistics_during_period` TypeError/signature
  mismatch.
- (f) ~~Move setup-time schema file reads off the Home Assistant event loop~~
  **(done in `0.1.23`)** — schema reads are now memoized + executor-preloaded
  and recorder reads run on the recorder DB executor; pending only live `0.1.23`
  confirmation that the warnings are gone (folded into item (e)).
- (g) Diagnose the `binary_sensor.kitchen_door` "not on the approved list"
  failure seen during `0.1.22` live testing. Catalog was **not** wiped (other
  requests still worked), so the all-or-nothing catalog rebuild was not the
  cause; no isolinear log line was captured because card-facing failures are
  written to runtime-only diagnostic records, not surfaced as visible logs.
  Likely a planner-emitted entity-id mismatch (`entity_not_in_approved_catalog`)
  or non-numeric binary-sensor history downstream. Worth: (1) surfacing
  card-facing failure codes as visible WARNING logs for diagnosability, and
  (2) deciding whether the all-or-nothing catalog rebuild (one unresolvable
  allowlist entry clears the whole catalog) should fail per-entity instead.
  **Part (1) done in `0.1.24`** (card-facing failed snapshots now log at
  WARNING with `failure_code`/`failure_stage`); the `kitchen_door` failure
  itself was diagnosed and fixed in `0.1.25` (it was
  `model_provider_chart_spec_hidden_entity` from a binary entity forced down the
  numeric path; binary entities now render as timelines — ADR-0022). Part (2)
  (per-entity vs all-or-nothing catalog rebuild) still open.
- (i) ~~**0.1.26 — numeric line + binary `shaded_intervals` overlay**~~
  **(done in `0.1.26`)** — "temperature and when the AC was running" composes a
  numeric line + binary overlay band; multi-entity resolution + deterministic
  overlay injection + renderer overlay pass landed (ADR-0022 D4/D5, BDD
  Scenarios M–O). Follow-ups still open: overlay for ≥2 numeric (multi-axis),
  overlay on the `timeline` family, and a dedicated `timeline_history_unavailable`
  code for beyond-retention binary windows.
- (h) **Night mode (dark theme)** — new feature, decisions captured 2026-06-18.
  Scope: **chart PNG + card UI**. Theme source: **auto-follow Home Assistant
  theme** (no user toggle / no options-flow surface). Two coupled surfaces:
  (1) the Pillow renderer (`in_process_renderer.py`) bakes a white background
  `(255,255,255)` + dark text/grid at render time, so a dark variant needs a
  second palette **and** the resolved theme plumbed card → `job/start` →
  planner/render request (schema-touching: add a theme/appearance field to the
  job-start command + render path); (2) the Lit card (`isolinear-card.ts`)
  already consumes HA theme CSS vars with light *fallbacks* plus a few
  hardcoded light values (e.g. `#f7f9fb`) to clean up, and must detect HA
  dark/light (e.g. `hass.themes.darkMode` / `prefers-color-scheme`) to pass the
  chosen theme through each request. Needs a spec (and likely an ADR for how
  the theme is resolved/plumbed) per invariant #8 + the BDD-first workflow
  before implementation. Pushed here because the night-mode context gate
  (≥70% context remaining) was not met when the logging packet closed.
- (j) ~~**Multi-concept planning failure on `gemma4:e4b`**~~ **(resolved in
  `0.1.48`, ADR-0028).** Re-diagnosed at the `0.1.47` live retest: NOT a planner
  prompt/capability issue. The live debug log showed the failing prompts disclosed
  the *wrong* entity set — "kitchen" noise-matched `sensor.kitchen_ecobee_temperature`,
  so the temp sensor became the chart primary (door demoted to overlay) and a
  spurious `binary_sensor.kitchen_door` overlay entered the temp+AC prompt. The
  planner correctly clarified on a nonsensical disclosure; with the clean disclosure
  it plans both fine (reproduced against live gemma). Fixed by the ADR-0028
  composition prune pass. Pending only the live HACS retest checkbox in the
  ADR-0028 active-work block.
- (k) **Cosmetic: planning-phase label during deferred selection** — after
  ADR-0026, some in-progress polls during the planning phase show
  `progress.message` = "Approved entities are staged for model planning." (the
  static deferral-snapshot message) instead of "Planning chart…"; reasoning
  still streams. `apply_live_reasoning` should also normalize the message/stage
  to the active phase label on the entities-bearing planning snapshot.

## Blockers

- None.
