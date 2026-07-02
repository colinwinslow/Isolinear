# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-07-02, second session (DECISION + CLEANUP: ADR-0029 kill condition resolved to **KEEP** by the human; **ADR-0030 accepted** — matplotlib codegen becomes the PRIMARY render path, Pillow the surfaced fallback; the pre-pivot simulated scaffold purged outright — 135 files / ~40K lines deleted; ADRs consolidated. Suite now **309 passed / 4 skipped in ~7s** (was 623/4 — half the old suite tested deleted scaffold). **Version bumped 0.1.49 → 0.2.0** — a minor bump marking the ADR-0030 direction change; on branch `adr-0029-worker-codegen-eval`)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Implement the ADR-0030 decisions in code: (1) pandas into the worker image (worker/requirements.txt + Dockerfile rebuild on CT103); (2) raise the sandbox memory cap 256MB -> 1024MB (+ update the test asserting memory_limit_mb <= 256); (3) repair policy in job_orchestration.py — ALL sandbox failure classes repairable, including static security rejections, bounded by max_codegen_repair_attempts (packet-4 currently makes unsafe_code terminal; every attempt still re-runs the full static check in the sandbox); (4) flip the render default — codegen primary when a healthy worker is configured, Pillow fallback surfaced in render_metadata + card (replaces the codegen_enabled default-False posture; needs spec update). AFTER that, in rough order: model-authored transforms spec (cross-series math in generated code — the "average two sensors" capability, ADR-0030 decision 4); simplify the deprecated-0015/0016-era worker durability machinery in custom_components (~3.4K LOC, still load-bearing in __init__.py); split job_orchestration.py (7.7K lines). PARKED: live HACS retest of 0.1.48/0.1.49; legend manifest for timeline/histogram/aggregate_bar; night mode spec+ADR; homelab worker deploy (waits on the docker_host role).`
**Current readiness:** `DECISION SESSION DONE (docs + deletion only; NO integration behavior change; NO version bump — still \`0.1.49\`). (1) The human resolved the ADR-0029 kill condition: KEEP — recorded in ADR-0029 (draft→accepted, outcome section) and the new ADR-0030 (accepted): matplotlib codegen = PRIMARY render path when a healthy worker is configured; Pillow = fallback (surfaced, never silent) + explicit option; ChartSpec stays the planning contract + data boundary; model-authored transforms in generated code (cross-series math — the closed transform enum stops being the ceiling); pandas into the worker image; memory cap 256→1024MB; ALL sandbox failure classes repairable incl. static security rejections (bounded; every attempt re-runs the static check + sandbox). CLAUDE.md invariant #6 rewritten; stale out-of-scope list replaced. Consolidation: 0004 superseded by 0030; 0015/0016 deprecated → docs/decisions/archive/; 0017 labeled historical; 0018 + its spec promoted draft→accepted (implemented + live since ~0.1.20). (2) THE PURGE (\`f8f7760\`): deleted the entire pre-pivot simulated universe — src/Isolinear (~15K LOC anchors + 3,334-line fake_slice), 29 anchor test files, 48 fake-path evals, 23 scaffold specs — 135 files, ~40,156 deletions; production code imported none of it (verified); the 7 real-path evals + evidence.py retained. Suite 309 passed / 4 skipped in ~7s (was 623/4 in ~40s — half the old suite tested deleted scaffold); timeline_render_family_routing + codegen_sandbox evals PASS. Next: implement ADR-0030 decisions (pandas / cap / repair policy / render default flip).\`

> **⚠️ Direction (2026-07-02, supersedes the 2026-06-12 banner):** ADR-0030 —
> matplotlib codegen via the sandboxed worker is the PRIMARY render path;
> Pillow is the fallback; the model is empowered to transform data in generated
> code. The 2026-06-12 reality pivot completed: the simulated scaffold is
> deleted (commit `f8f7760`), pytest is the single source of behavioral truth
> (`docs/reality-pivot-review.md` is historical context).

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-07-02 (2nd session)** — `ADR-0029 KEEP decision + ADR-0030 (codegen primary) + the great scaffold purge (branch \`adr-0029-worker-codegen-eval\`)` — **Docs + deletion only; NO integration behavior change; NO version bump (still `0.1.49`).** The human resolved the ADR-0029 kill condition to **KEEP** and declared the bigger pivot: lean into matplotlib codegen, empower the model, clean up the project (explicit immutability exception for stale ADRs). **Commit `f8f7760` — the purge:** deleted the entire pre-pivot simulated universe (`src/Isolinear/` ~15K LOC of `*_anchor.py` + the 3,334-line `fake_slice.py`; 29 anchor test files; 48 fake-path evals; 23 scaffold specs) — **135 files, ~40,156 deletions**; production code imported none of it (verified by grep — only docstring mentions remain); the 7 real-path evals + `evidence.py` retained. Suite **309 passed / 4 skipped in ~7s** (was 623/4 — half the old suite tested deleted scaffold). **Commit `255b0c3` — [ADR-0030] + consolidation:** ADR-0030 (accepted) records KEEP + the render-strategy decisions — codegen PRIMARY when a healthy worker is configured; Pillow fallback (surfaced, never silent) + explicit option; ChartSpec stays the planning contract/data boundary; **model-authored transforms in generated code** (cross-series math like averaging two sensors — the closed transform enum stops being the capability ceiling; follow-up spec needed); **pandas into the worker image**; **memory cap 256→1024MB**; **ALL sandbox failure classes repairable incl. static security rejections** (bounded by max attempts; every attempt re-runs the full static check + sandbox — the boundary enforces, repair just retries the gate). Consolidation: 0004 superseded by 0030; 0029 draft→accepted with outcome; 0018 + spec draft→accepted (implemented/live since ~0.1.20); 0015/0016 deprecated → `docs/decisions/archive/`; 0017 labeled historical; decisions README restructured; **CLAUDE.md invariant #6 rewritten** (codegen-primary, fallback-safe) + stale out-of-scope list replaced. **Next:** implement the ADR-0030 decisions (pandas, cap, repair policy, render-default flip), then the transforms spec, then simplify the deprecated worker-durability machinery + split `job_orchestration.py`. **Closeout addendum (same session): version bumped 0.1.49 → `0.2.0`** (human's call — the minor bump marks the ADR-0030 direction change; suite re-verified 309/4 post-bump; `test_hacs_install_packaging` derives from `INTEGRATION_VERSION`, no pin to update).

- **2026-07-02** — `ADR-0029 packet 5 — codegen reliability eval + sandbox codegen-friendliness fixes (branch \`adr-0029-worker-codegen-eval\`)` — **Worker-only; NO integration change; NO version bump (still `0.1.49`, matches packets 1–3).** Ran the **codegen accept/reject/repair reliability eval** (`evals/codegen_reliability.py`) — the data the ADR-0029 keep/remove decision rests on — driving the new **42-prompt real benchmark corpus** (`evals/prompts/benchmark_prompts.json` + README; 35 chartable) through **`gemma4:e4b`** and **`qwen2.5-coder:7b`**: each model **generates** matplotlib from a schema-valid ChartSpec + synthetic history, rendered **LIVE through the CT103 worker sandbox**, with an integration-orchestrated **repair loop (max 2 repairs)**. **Both models accept 33/35 (3 via repair each)** — gemma **24/35 strict → 33/35**, qwen **30/35 → 33/35** — with **no sandbox false positives**: the 4 remaining rejects are all legitimate (gemma `ov-02` forbidden `locals()` — terminal security gate; qwen `ov-03`/`ov-04` a real numpy `isfinite` `TypeError`; gemma `agg-03` `output_missing`). **Refined repair policy** (built in the eval, recommended for the integration): SECURITY violations (`forbidden_import`/`forbidden_attribute`/`forbidden_call`/`dunder_attribute`/`scope_escape`) stay **TERMINAL**; `syntax_error`/`import_not_allowlisted`/`runtime_error` are **REPAIRABLE**. **Key finding (strong KEEP signal):** the models fail **differently** — gemma trips STATIC checks it can repair (syntax/imports), qwen trips RUNTIME limits (256MB address-space cap); 3060-class local models produce good, safe matplotlib at **~94% accept with repair**. Report gallery via `evals/prompts/gen_report.py` → `reliability_results.json` + `reliability_report.md` + `renders/` (66 PNGs). **Batch of worker-only sandbox codegen-friendliness fixes** — boundary-preserving corrections of an under-specified allowlist, NOT security relaxations: **from-imports that target an allowlisted module** (checks the module after `from`; forbidden + relative still rejected — **security-reviewed OK**, `40b9464`); expanded safe builtins + `datetime._strptime` (`a11ae4f`); `numpy`/`itertools`/`functools`/`collections` whitelist + `replace`-attribute false-positive unblock (`str.replace` safe; `os.replace` unreachable + audit-blocked, `03fa792`); `typing` whitelist (`bfd99a0`); **READ-ONLY** matplotlib font-cache pre-warm in the Dockerfile (`ISOLINEAR_WORKER_MPL_CACHE`, ~20% faster renders, no write-policy relaxation, `882af2e`). Packet-5 eval landed as `9320cf0`. **Verify:** suite `623 passed, 4 skipped` throughout; version unchanged `0.1.49`. **Three open decisions recorded for the human (non-blocking):** (1) pandas support in the worker image (gemma reached for it; image-size call); (2) raise the 256MB sandbox memory cap (qwen's remaining rejects + earlier MemoryErrors hit it; a test asserts `memory_limit_mb <= 256`; resource-policy call); (3) adopt the security-vs-recoverable repair distinction in `job_orchestration.py` (packet-4 treats all `unsafe_code` as terminal). **Next:** the ADR-0029 keep/remove DECISION (the human's call).

- **2026-07-01** — `ADR-0029 packet 4 — model codegen generation + integration-orchestrated repair (branch \`adr-0029-worker-codegen-eval\`)` — **Integration + worker; version bumped 0.1.48→0.1.49 (`b22992b`).** Implemented the opt-in codegen render path: an **`codegen_enabled`** options toggle (default **False** — trusted chart-spec renderer stays the default, invariant #6) gates a path where the model **generates** the matplotlib code and, on a retryable sandbox error, **repairs** it. Separately configurable **`codegen_model`** (config field) **defaults to the planner model** when unset. **`generate_chart_code`/`repair_chart_code`** on the Ollama client (`model_provider.py`) emit **freeform Python** (one `/api/chat` each, **no constrained `format`**), markdown-stripped via `_strip_markdown_json`; repair feeds the previous code + `error.code`/`error.message`/traceback back. Only the validated ChartSpec + normalized render data cross into the prompt via the **data-boundary projection `_codegen_request_view`** (strips request_id/tokens/secrets — no HA/worker/model token, invariants #1/#3). The **repair loop is INTEGRATION-ORCHESTRATED** in `job_orchestration.py`: dispatch **`render_mode: codegen`** (`codegen.python_code`) over the existing **`HttpJsonWorkerRenderClient`**; on a retryable error (`runtime_error`/`timeout`/`output_missing`/`output_too_large`) the integration's **own** model repairs and re-dispatches up to `max_codegen_repair_attempts` (each a fresh `POST /v1/render`; the worker re-runs static safety every attempt); **`unsafe_code` is terminal** (never repaired); the worker-local **`invoke_codegen_with_repair` is NOT used over HTTP** — the data boundary forbids the worker holding a model client. **Fail-closed `codegen_render_failed`** on exhaustion / generation-failure / `unsafe_code` — **NO silent fallback** to the trusted renderer (keeps the packet-5 accept/reject/repair eval honest). **PROVEN LOCALLY only:** full orchestration against an in-process sandbox worker + the real packet-2 **`isolinear_worker.http_server` on an ephemeral port** for the wire end-to-end (`evals/codegen_generation_path.py`) — NO CT103 / remote host touched (that's packet 5). **Reviews OK:** architecture — no invariant violations (#1 allowlist + #9 render-family upheld — the model only replaces the render step; planner still produces the validated ChartSpec; #3 sandboxed; #6 codegen off by default; #8 covered by ADR-0029, no new ADR); BDD-evidence — OK (all 7 scenarios A–G with raw outputs; referenced tests exist and pass). **Docs:** evidence `pytest -v` block regenerated complete; `codegen-generation-path` spec + BDD promoted draft→ACCEPTED; specs README updated; STATUS/HANDOFF updated. **Verify:** suite `620 passed, 4 skipped` (595 prior + 25 new; skips = 3 prior matplotlib-in-`-I` + 1 new matplotlib-over-wire, documented dev-box limitation); both evals PASS (`codegen_generation_path.py`, `worker_http_server.py` — no regression). **Next:** packet 5 — the live CT103 end-to-end proof + the codegen accept/reject/repair reliability eval (the data the ADR-0029 keep/remove decision rests on).

- **2026-07-01** — `ADR-0029 packet 3 PROVEN LIVE on CT103 + OpenBLAS sandbox fix (branch \`adr-0029-worker-codegen-eval\`)` — **Worker-only; NO integration code changed; NO version bump (matches packets 1–2).** The packet-3 worker image was **built and run live on the deploy target CT103** (docker-host/10.0.1.39, Debian 13 trixie, x86_64, Docker 29.5.2, 6 cores) from a fresh clone at commit `2bb2747`. **All 6 previously-DEFERRED BDD scenarios (A–F) now PASS** with raw CT103 outputs recorded: image builds (matplotlib-3.11.0 from prebuilt wheels, 418MB); `GET /v1/health` → `ready` (matplotlib importable under `python -I` from system site-packages); a **real matplotlib chart rendered end-to-end over `POST /v1/render`** (valid 16557-byte PNG, sig `89504e470d0a1a0a`, at `/var/lib/isolinear-worker/work/codegen-sandbox-anchor.png`); the **3 matplotlib-gated tests un-skip and pass in-container** (`24 passed`, zero skips); the image is **HA-agnostic** (in-image `find` empty); the container **HEALTHCHECK reports `healthy`**; fail-closed on missing/short token. **OpenBLAS FINDING + FIX (the most important thing the live build surfaced):** health was `ready` (matplotlib *imports*), but the FIRST live render FAILED with `OpenBLAS error: Memory allocation still failed after 10 retries, giving up.` Root cause: numpy's OpenBLAS backend reserves per-core address space at import (scaled to the 6-core host), exceeding the sandbox's 256MB `RLIMIT_AS` cap and aborting before any chart is drawn — invisible on the dev box because the matplotlib tests skip there. Fixed in **`2bb2747`**: pin `OPENBLAS_NUM_THREADS`/`OMP_NUM_THREADS`/`MKL_NUM_THREADS`/`NUMEXPR_NUM_THREADS`/`VECLIB_MAXIMUM_THREADS` to `1` in the sandbox `_sandbox_environment` + policy `explicit_environment_keys` (`worker/isolinear_worker/codegen_sandbox.py`). These vars only *reduce* resource use → sandbox NOT weakened (invariant #3 intact). After rebuilding at `2bb2747`, all scenarios pass. **De-risks the ADR-0029 experiment:** proves the sandbox can actually render matplotlib in the target deployment before packet 4 (codegen model) and packet 5 (reliability eval). **Docs:** evidence file (A–F now verified/PASS with raw outputs + OpenBLAS finding subsection; G/H/I unchanged), BDD retagged A–F verified-on-Docker-host, **spec promoted draft→ACCEPTED** (proof trigger met), specs README updated, STATUS/HANDOFF updated. **Verify:** dev-box suite unchanged `595 passed, 3 skipped`; the proven `isolinear-worker:dev` image (418MB) retained on CT103; ephemeral token never printed; temp clone removed. **Next:** packet 4 — codegen path in the model provider + real repair model.

- **2026-07-01** — `ADR-0029 packet 3 — standalone amd64 worker Dockerfile (branch \`adr-0029-worker-codegen-eval\`)` — **Worker-only; NO integration code changed; NO version bump (matches packets 1–2).** Committed the implementation `6321215` (`worker/Dockerfile` + `worker/.dockerignore`) plus this doc closeout. A single-stage **`worker/Dockerfile`** (`python:3.12-slim`) packages the self-contained `isolinear_worker` package into a linux/amd64 image. **Load-bearing choice:** matplotlib installs (`pip install -r requirements.txt`, as root) into the interpreter's **SYSTEM site-packages** — no venv, no `--user` — because the sandbox runs generated code under `python -I` (isolated mode excludes user site-packages); only a system-site install lets the packet-2 readiness probe's `python -I -c "import matplotlib"` succeed, so **`GET /v1/health` flips not_ready→ready** and the worker can render. That flip is the whole purpose of this packet (dissolves the ADR-0017 matplotlib-on-HAOS/aarch64 blocker). Non-root **`worker` user (uid/gid 10001)**; chowned `work_root` **VOLUME**; 12-factor env matching packet-2's `load_config_from_env` exactly (**`ISOLINEAR_WORKER_TOKEN` runtime-only — never an `ENV`/layer; fail-closed if missing/short**); **stdlib-only `HEALTHCHECK`** (no curl/wget) that reads token+port from runtime env and exits 0 only on 200 AND `health.status == "ready"`; **`ENTRYPOINT ["python","-m","isolinear_worker.http_server"]`** (packet-2 `__main__` guard). **HA-agnostic by construction:** build context `worker/`, so nothing from `custom_components`/`src`/`frontend` is reachable (`.dockerignore` trims the rest). **Docker is NOT installed here**, so the **image BUILD + container RUN proofs are DEFERRED to a linux/amd64 Docker host (CT103/10.0.1.39):** 6 of 9 BDD scenarios (A–F: build, fail-closed startup, `/v1/health`→ready, `/v1/render` PNG, the 3 matplotlib tests un-skipping, no-HA-code-in-image) marked `DEFERRED (needs Docker host)` with exact reproduction commands — no build log fabricated (repo's live-retest deferral pattern); the 3 STATIC scenarios (G entry-point, H config-contract, I suite-green) carry real raw outputs. **Spec left DRAFT** (not accepted) until the live build passes — the core proof is that build. **Verify:** suite unchanged `595 passed, 3 skipped` (the matplotlib skips only flip inside the container); no integration code touched; no version bump. **BDD-evidence review OK** (all 9 scenarios present; STATIC real, DEFERRED honest with commands). **Architecture review OK** (no invariant violations — #3 sandbox model untouched: system-site matplotlib only makes an already-allowlisted import present, allowlist still governs generated code; #8 base image/non-root/healthcheck/VOLUME within ADR-0029 scope, no new ADR; optional note: digest-pin `python:3.12-slim` at first build). **Next:** packet 4 — codegen path in the model provider + real repair model.

_(older sessions — ADR-0029 packets 1–2, ADR-0028/0.1.48, ADR-0027/0.1.47, ADR-0023/0.1.44, ADR-0026/0.1.43 and earlier — live in git history)_
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `ADR-0030 implementation — codegen primary` — NEXT (branch `adr-0029-worker-codegen-eval`)

- [ ] pandas into the worker image (`worker/requirements.txt` + rebuild `isolinear-worker:dev` on CT103; verify a pandas-using render in-container)
- [ ] Raise sandbox memory cap 256MB → 1024MB (policy default + the `memory_limit_mb <= 256` test)
- [ ] Repair policy in `job_orchestration.py`: ALL sandbox failure classes repairable (incl. `unsafe_code`), bounded by `max_codegen_repair_attempts`; update `codegen-generation-path` spec + BDD
- [ ] Flip render default: codegen primary when healthy worker configured; Pillow fallback surfaced in `render_metadata` + card; `codegen_enabled` semantics revisited (spec update; version bump)
- [ ] Follow-up spec: model-authored transforms (cross-series math in generated code — ADR-0030 decision 4)

### `Worker revival for codegen evaluation (ADR-0029)` — DECIDED: KEEP (2026-07-02, ADR-0030)

- [x] Rewrite-vs-refactor review: architecture sound; worker tree is load-bearing, not dead weight; brittleness centers on `job_orchestration.py`
- [x] ADR-0029 (draft) — revive worker to evaluate sandboxed codegen; kill condition if 3060-class model codegen is insufficient
- [x] ADR-0029 data-boundary constraint — entity selection/allowlist/history stay integration-side; only normalized allowlisted data crosses; worker never queries HA
- [x] Packet 1 spec + BDD (`codegen-sandbox-module-promotion`, draft) — promote anchor → self-contained `worker/isolinear_worker/`; doc indexes synced
- [x] Deploy target pinned: CT103/10.0.1.39 standalone amd64 GPU-less Docker via homelab `docker_host` role; two-repo split; memory recorded
- [x] **Packet 1 implementation** — stood up `worker/isolinear_worker/` (sandbox + standalone validator + bundled schemas + requirements), `tests/test_codegen_sandbox.py` parity A-G via public API (+ self-containment + schema-drift guard), repointed eval, retired anchor; suite `584 passed, 2 skipped`; spec+BDD accepted
- [x] **Packet 2 implementation** — stood up `worker/isolinear_worker/http_server.py` (stdlib `http.server`, no new dep — invariant #8) wrapping the packet-1 sandbox: `POST /v1/render` + `GET /v1/health`, fail-closed auth→version→schema→sandbox ordering, sandbox failures inside 200 / transport faults 401/400, 12-factor `ISOLINEAR_WORKER_TOKEN` (≥24 chars, fail-closed startup)/host/port/work_root, HA-agnostic (import-graph verified); `tests/test_worker_http_server.py` + wire-interop `evals/worker_http_server.py` (real `HttpJsonWorkerRenderClient`); suite `595 passed, 3 skipped`; both reviews OK; spec+BDD accepted; NOT version-bumped
- [x] **Packet 3 — standalone amd64 Dockerfile with matplotlib** — `worker/Dockerfile` (single-stage `python:3.12-slim`) + `worker/.dockerignore`: matplotlib installed into SYSTEM site-packages so the `-I` sandbox imports it and `/v1/health` flips ready; non-root `worker` (uid/gid 10001), chowned `work_root` VOLUME, 12-factor env (`ISOLINEAR_WORKER_TOKEN` runtime-only), stdlib-only HEALTHCHECK gated on `status == "ready"`, `python -m isolinear_worker.http_server` entry point, HA-agnostic (context `worker/`); committed `6321215`; suite unchanged `595 passed, 3 skipped`; both reviews OK; NOT version-bumped. **Now PROVEN LIVE on CT103** (see next item)
- [x] **Live: build + run the worker image on a linux/amd64 Docker host (CT103/10.0.1.39)** — **DONE 2026-07-01 (commit `2bb2747`, fresh clone + rebuild):** image builds (matplotlib-3.11.0 from wheels, 418MB); `/v1/health` → `ready`; `/v1/render` returns a valid 16557-byte PNG; the 3 matplotlib-gated tests un-skip and pass in-container (`24 passed`, zero skips); no HA code ships (in-image `find` empty); HEALTHCHECK `healthy`; fail-closed on missing/short token. All 6 A–F BDD scenarios PASS with raw outputs recorded. **`worker-container-image` spec promoted draft→ACCEPTED.** The live build surfaced + fixed the OpenBLAS/`RLIMIT_AS` bug: the first render failed with `OpenBLAS error: Memory allocation still failed…` (numpy OpenBLAS per-core address-space reservation × 6 cores exceeded the sandbox 256MB `RLIMIT_AS`); the **OpenBLAS thread-pinning fix landed as `2bb2747`** (pin OPENBLAS/OMP/MKL/NUMEXPR/VECLIB thread vars to 1 in the sandbox env — strictly resource-reducing, sandbox not weakened). Proven image retained on CT103
- [x] **Packet 4 — codegen path in the model provider + real repair model** — opt-in `codegen_enabled` toggle (default False, invariant #6); separately configurable `codegen_model` defaulting to the planner; `generate_chart_code`/`repair_chart_code` (freeform Python, markdown-stripped) in `model_provider.py`; integration-orchestrated repair loop in `job_orchestration.py` (dispatch `render_mode: codegen` over `HttpJsonWorkerRenderClient`, model repairs retryable errors, `unsafe_code` terminal); fail-closed `codegen_render_failed`, no silent trusted fallback; data-boundary projection `_codegen_request_view`. Proven LOCALLY (in-process sandbox worker + real packet-2 HTTP worker on an ephemeral port). Suite `620 passed, 4 skipped`; both evals PASS; both reviews OK; spec+BDD accepted; version bumped `0.1.49` (`b22992b`)
- [x] **Packet 5 — codegen accept/repair reliability eval (the data the keep/remove decision rests on)** — `evals/codegen_reliability.py` drives the 42-prompt corpus (`evals/prompts/benchmark_prompts.json`; 35 chartable) through `gemma4:e4b` + `qwen2.5-coder:7b`, each generating matplotlib rendered LIVE through the CT103 worker sandbox with a max-2 repair loop. **Both models 33/35 accepted (3 via repair each)** — gemma 24→33, qwen 30→33 — no sandbox false positives (4 rejects all legitimate); refined repair policy splits terminal SECURITY violations from repairable syntax/import/runtime failures. **KEEP signal:** models fail differently (gemma STATIC/repairable vs qwen RUNTIME/256MB cap); ~94% accept with repair. Gallery: `evals/prompts/gen_report.py` → `reliability_results.json` + `reliability_report.md` + `renders/` (66 PNGs); eval landed `9320cf0`. Suite `623 passed, 4 skipped`; version unchanged `0.1.49`
- [x] **Sandbox codegen-friendliness fixes** (worker-only, boundary-preserving allowlist corrections, NOT security relaxations) — from-imports targeting an allowlisted module (security-reviewed OK, `40b9464`); expanded safe builtins + `datetime._strptime` (`a11ae4f`); `numpy`/`itertools`/`functools`/`collections` whitelist + `replace`-attribute unblock (`03fa792`); `typing` whitelist (`bfd99a0`); READ-ONLY matplotlib font-cache pre-warm (`882af2e`)
- [x] **Open decision (human): RESOLVED 2026-07-02** — keep/remove = **KEEP**; pandas = YES; memory cap = raise to 1024MB; repair policy = repair everything (incl. static security rejections), bounded. All recorded in ADR-0030; implementation is the next packet (see section above)
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
