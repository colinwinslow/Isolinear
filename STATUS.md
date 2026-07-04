# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-07-04, tenth session (**SHIPPED to `main` + live bring-up: reached the worker, fixed three real bugs found live (0.2.8→0.2.11)**. **Merged `adr-0029-worker-codegen-eval`→`main`** — and caught that Colin's earlier GitHub **PR #3 had shipped a STALE 0.2.1** (it merged the 4th-session commit `4d0e153`, missing the entire 5th–9th-session line and still carrying the deleted machinery); rebuilt the current tip on top of the PR merge (no force-push) → `main` now `1d923c6` = **0.2.11**. **Live bring-up hit + fixed three bugs, each shipped:** (1) **`0.2.9` editable endpoints (`8ea4a7f`)** — `model_endpoint_url`+`worker_endpoint_url` were setup-time-only, so a fresh install's worker endpoint was stuck on a placeholder → `worker_connection_error` fallback; both are now editable in the Configure form (above the entity picker), persisted to config-entry data, live-rebuild on save. (2) **`0.2.10` repair-visibility fix (`de7ec4f`)** — codegen `unsafe_code` fell back on EVERY attempt regardless of `max_codegen_repair_attempts`: `_sandbox_error_view` dropped `details.violations`, and a static failure has no traceback, so the model repaired **blind**; violations now flow into the repair prompt (proven: live gemma fixes unsafe code in one pass once it can see them). This is why the packet-5 ~94%-with-repair eval never showed in prod. (3) **`0.2.11` failure logging (`1d923c6`)** — integration logs a WARNING on codegen fallback (stage/code/attempts + compact violation detail, HA system-log-reachable); worker logs each `/v1/render` outcome (`docker logs` shows `status=failed error=unsafe_code violations=[code@Lline]`); worker image rebuilt on CT103. **Live status: the chain reached the worker** (two `POST /v1/render` from `10.0.1.200` confirmed) — the endpoint fix worked; the render fell back on the (now-fixed) repair-blind bug. Colin has SSH to CT103 now (Termius ed25519 key installed in root's authorized_keys; CT103 root is key-only). Suite **408 passed / 4 skipped**; evals PASS. Everything pushed to `origin/main`.)
**Phase:** `Live end-to-end all but done — the full chain (HA → model → CT103 worker → sandboxed PNG) is proven to connect; awaiting Colin's 0.2.11 retest (redownload + repair-attempts=2) to confirm a clean codegen render. A NEW BUG was found during live testing (2026-07-04) — deferred to next session (see open-queue item (n)).`
**Next bounded packet:** `(A) CONFIRM FIRST CLEAN CODEGEN RENDER: Colin redownloads 0.2.11 + sets max_codegen_repair_attempts=2 + re-asks; watch the CT103 worker log (docker logs isolinear-worker) for a clean render + a grounded answer. If it still falls back, the new logging shows the exact violation on the first try. (B) The NEW BUG (open-queue (n)) — Colin to describe at session start. THEN: (C) registry follow-ups (pearson_r alignment; corpus-requested metrics). PARKED: packet 5 (output-modality) + packet 6 (visual validator + progressive UX); anchored-window tranche-2; open-queue (l) refinement + saved cards; split job_orchestration.py; also consider raising the default max_codegen_repair_attempts above 1 (currently stingy).\`
**Current readiness:** `Version 0.2.11 on \`main\` (HACS-tracked). Worker live + healthy on CT103 (compose service, image rebuilt with logging). The full path connects end-to-end; the only remaining confirmation is a clean codegen render after Colin redownloads 0.2.11 (live HA was on 0.1.48 → 0.2.1 from the stale PR → now needs 0.2.11). Endpoints editable in Configure; token stored via ADR-0032; repair loop now sees violations; both sides log failures. Homelab \`main\` carries the worker compose service (\`311eac9\`).\`

> **⚠️ Direction (2026-07-02, supersedes the 2026-06-12 banner):** ADR-0030 —
> matplotlib codegen via the sandboxed worker is the PRIMARY render path;
> Pillow is the fallback; the model is empowered to transform data in generated
> code. The 2026-06-12 reality pivot completed: the simulated scaffold is
> deleted (commit `f8f7760`), pytest is the single source of behavioral truth
> (`docs/reality-pivot-review.md` is historical context).

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-07-04 (10th session)** — `Shipped to main + live bring-up: reached the worker, fixed three live-found bugs (0.2.8→0.2.11), all on \`main\`` — **The integration went live and the debugging happened against real HA.** **Merge:** completed the ship by merging \`adr-0029-worker-codegen-eval\`→\`main\` — and caught that Colin's GitHub **PR #3 had merged a STALE commit (\`4d0e153\`, 0.2.1)**, so \`origin/main\` was a half-shipped 0.2.1 missing the 5th–9th-session work and still carrying the deleted machinery; rebuilt the current tip on top of the PR merge (kept it in history, no force-push). **Three live bugs, each root-caused + fixed + shipped:** (1) **`0.2.9` (`8ea4a7f`) editable endpoints** — `model_endpoint_url`+`worker_endpoint_url` were setup-time-only → a fresh install's worker endpoint stuck on a placeholder → `worker_connection_error`; now editable in the Configure form above the entity picker, persisted to config-entry data (extracted before options validation like the token), live-rebuild on save; +8 tests. (2) **`0.2.10` (`de7ec4f`) repair blind to `unsafe_code`** — `_sandbox_error_view` fed the repair prompt only code/message/traceback, but a static failure has no traceback and its `details.violations` were dropped, so the model repaired blind and one disallowed construct exhausted the repair budget every time → Pillow fallback (why the packet-5 ~94%-with-repair eval never showed in prod); violations now flow into the repair prompt, proven live (gemma fixes unsafe code in one pass once it sees them); +4 tests. (3) **`0.2.11` (`1d923c6`) failure logging** — integration WARNING on codegen fallback (stage/code/attempts + compact violation detail, HA system-log-reachable) + worker per-render outcome log (`docker logs` shows `error=unsafe_code violations=[code@Lline]`), worker image rebuilt on CT103; +5 tests. **Live proof:** two `POST /v1/render` from `10.0.1.200` confirmed the chain reaches the worker (endpoint fix worked); the render fell back on the now-fixed repair-blind bug. **Infra:** Colin's Termius ed25519 key installed in CT103 root's authorized_keys (root is key-only) so he reads the SOPS token himself via `docker exec … env`. **Verify:** suite **408 passed / 4 skipped** (+17 across the three fixes), evals PASS; inline invariant check OK (no sandbox/allowlist/schema/service change — config-flow endpoints route to config data; repair view + logging are additive/diagnostic). **Deferred:** a NEW bug Colin found during live testing → open-queue (n), to describe next session. **Next: confirm a clean codegen render on 0.2.11 (repair-attempts=2), then the new bug.**

- **2026-07-04 (9th session)** — `Live-deploy path: packet 3 (scipy+seaborn) shipped + worker deployed as a CT103 compose service + ADR-0032 wires the deployment token (0.2.6→0.2.8; branch \`adr-0029-worker-codegen-eval\` through \`54eaffb\` + homelab \`main\` \`311eac9\`, ALL PUSHED)` — **Three landings toward the first live render.** **(1) Packet 3 — scipy+seaborn (`8964bc1`, 0.2.7):** libs into `worker/requirements.txt` + sandbox allowlist (exact-match `scipy`/`scipy.stats`/`scipy.signal`/`scipy.optimize`/`seaborn`); the stale `_CODEGEN_PROMPT_RULES` "import nothing except matplotlib" rule (contradicted the packet-2 pandas hint) now enumerates the five libs. **Proven live on CT103 (Scenario H):** image **719MB** (was 526MB), in-container worker suite **27 passed / 0 skips**, all five import together under the `-I` sandbox 1024MB cap, `scipy.stats` correlation + `seaborn.heatmap` → valid PNG; evidence appended to `bdd/model-authored-analysis/...-evidence.md`. **(2) Homelab compose service (`311eac9` on `main`):** the worker (`isolinear-worker:dev`, local tag, `pull_policy: never`) is now a managed `docker_host` service — GPU-less, port 8080, bearer token from SOPS (`docker_host.isolinear_worker_token`), tmpfs work root; spec+BDD `isolinear-worker-service` A–E proven live (`/v1/health` ready with token+version, 401 without, 400 missing-version, re-apply `changed=0`, ollama/frigate/plex/caddy uptimes untouched). Handler `restarted`→`present` so an additive service block doesn't bounce the stack. **(3) ADR-0032 — deployment token (`54eaffb`, 0.2.8):** the live deploy exposed the scaffold mismatch — the integration self-provisioned a token the SOPS-token worker never knew (guaranteed 401). Now the token is deployment config: write-only options-flow password field → integration-owned HA Store (`worker_token_storage.py`), extracted before options validation (`config_schema` secret fail-closed intact), rebuilds the renderer client in the options flow (HA fires listeners only on options change — arch-review catch). **Deleted ~3.1K LOC** of uncovered ADR-0015/0016 durability machinery: 8 modules (`worker_token_lifecycle`/`worker_readiness`/`worker_health`/`worker_health_polling*`) + 5 schemas ×2 copies + the `__init__` lifecycle-abort/readiness/health/polling chain; health is on-demand via the client's `check_health()`. **Live-proven** (`evals/deployment_worker_token.py`): real client → compose-managed CT103 worker with the SOPS token → `ready`; wrong token → surfaced 401; no token material in any output. **Verify:** suite **391 passed / 4 skipped** (+18), five worker-path evals PASS (`codegen_sandbox`, `codegen_generation_path`, `worker_http_server`, `model_authored_analysis`, `home_assistant_hacs_install_packaging`); architecture review (fresh-context subagent) CONCERNS→resolved (broken packaging eval fixed, token-only re-paste rebuild added + test, spec/ADR drift aligned with deviations recorded); BDD-evidence review OK (stale counts in the token evidence corrected at closeout). **Next: merge branch→main + HACS ship 0.2.8, then Colin enters endpoint+token in HA options → first end-to-end live render; OR the demand-driven registry follow-ups.**

- **2026-07-03 (8th session)** — `Grounding-check proof req #4 — floor-model claim-emission rate measured with production scoring (0.2.5→0.2.6; branch \`adr-0029-worker-codegen-eval\`; commits \`079431d\`/\`e1c6ef7\` + closeout, ALL PUSHED)` — **Two bounded changes.** **(1) Anchored-claim prompt shape (`079431d`):** packet 4d shipped anchor re-detection check-side, but `_CODEGEN_PROMPT_RULES` only documented the absolute `{start,end}` claim window — no model could ever emit the event-anchored form. The spec §1/§1a anchored window (anchor `entity`/`to`/`from`/`occurrence`/`search`/`resolved_at` + `direction`/`duration_ms`) is now documented with the same compute-not-guess discipline as value/verdict (`resolved_at` must be the transition timestamp the code actually found); prompt-rule test added. **(2) Proof req #4 benchmark (`e1c6ef7`):** the answer-family benchmark scores emitted claims with the REAL production checker (`custom_components.isolinear.answer_grounding`) against fresh real HA history (7-day extract, 16 entities, 16,318 points — gitignored) — no parallel reimplementation of "well-formed". Corpus: 18 prompts (`claim`/`claim_window` expectation flags + `anchor-01`, the registry-verifiable anchored case); `answer_question` category added to `evals/prompts/benchmark_prompts.json` (proof req #4 names both files); `num_predict` 3000→6000 (the cap truncated claim-bearing generations; production doesn't cap). **Three live `gemma4:e4b` runs, one variable at a time (FINDINGS.md): emission is reliable** — every claim-expected prompt whose code executed emitted claims (6/6, then 5/5); structure mostly right (6/6, 4/5 well-formed); **registry-verified: 0 in every run**, three causes now measured, not guessed: (a) run 1's "value formatted into the sentence" wording made gemma stringify 13/13 values (`'3.0°F'`) → the production prompt now demands a **raw JSON number**, which fixed the type on every subsequent claim; (b) free metric naming (`mean_difference`, `percentage_running`, …) lands honest-but-unregistered metrics in the caveat box — correct per D3, renaming would fabricate `value_mismatch`; (c) the registry's exact-timestamp `pearson_r` intersection returns no reference on real irregular data — the spec's "prescribe the alignment" open item, **confirmed live**. Anchored windows never emitted (0/2 every run — event logic in code, absolute bounds in the record): acceptable tranche-1 (value↔data holds; only event identity unconfirmed), recorded as the reason 4d won't exercise at the floor yet. **The check produced no false "verified" and caught a genuine live `verdict_contradicted` (pd-05).** **Proof req #4 is ANSWERED**: the floor model reliably emits and mostly forms the recipe; the fail-soft three-state boundary — not the strong guarantee — carries floor-model UX, exactly as §3b anticipated. **Closeout:** BDD evidence moved to the conventional path `bdd/answer-grounding-check/answer-grounding-check-evidence.md` (was misplaced at `docs/bdd/.../answer-grounding-check-bdd.md`, a path the BDD never named) + proof-req-#4 section appended; stale packets-1–4d "uncommitted/unpushed" notes corrected (all pushed). **Verify:** suite **372 passed / 4 skipped** (+1 prompt-rule test), eval `model_authored_analysis` PASS; architecture review skipped (benchmark/eval extension, no new integration surface); BDD-evidence review OK (path + staleness findings fixed in this closeout). **Next: packet 3 + live deploy path, or the demand-driven registry follow-ups (pearson_r alignment, corpus-requested metrics).**
- **2026-07-03 (7th session)** — `Sub-packet 4d — event anchors implemented, ADR-0031 D8a fully shipped (0.2.4→0.2.5; branch \`adr-0029-worker-codegen-eval\`)` — **Implement 4d (the last open sub-packet).** `_anchor_criteria_ok` validates spec §1a's four reproducibility criteria (delivered raw-state entity of kind `binary_state`/`categorical_state`, reusing the ADR-0022 kind taxonomy; crisp non-empty string `to`/`from`, no fuzzy matching; non-zero `occurrence`, 1-based/negative-from-end; numeric `search`/`resolved_at`) — any failure is `grounding_anchor_unreproducible` (caveat, irreproducible by construction, never attempted further). `_detect_transitions` scans the full ordered raw-state timeline (`raw_state` or `attrs[attribute]`) for exact transitions filtered to the search bounds; `_select_occurrence` applies the same indexing a model would use; `_resolve_anchor` combines them. No match → `grounding_anchor_unfound` (contradicted — the fabricated-event proof case); a match at a different instant than the claimed `resolved_at` → `grounding_anchor_mismatch` (contradicted — identity, not just existence); a correct match resolves absolute `{start, end}` bounds from `direction`/`duration_ms` that flow through the **same** span-check + registry recompute as any absolute window, extending the full value↔data guarantee to event-scoped claims. Window-shape validation moved ahead of the re-detection scan (architecture-review nit, applied) so a malformed window doesn't pay for walking the series. **No schema change** — `claims[].window` was already an open object; confirmed byte-identical across all three render-result copies. **Tests:** 5 new (`TestScenarioD` — fabricated/mismatch/verified/two irreproducible-by-construction cases); the pre-existing stub test renamed `test_malformed_anchor_shape_is_caveat`, now asserting the real code (`grounding_anchor_unreproducible`) instead of the old blanket `grounding_anchor_deferred`. **Reviews:** BDD-evidence review (inline) OK — Scenario D added to the evidence file with raw pytest output + a run timestamp (previously absent); architecture review (fresh-context subagent) OK, no invariant violations, one non-blocking nit applied. **Verify:** suite **371 passed / 4 skipped** (+5), frontend unchanged **35 passed**, eval `model_authored_analysis` PASS, schema byte-parity green. Version bumped **0.2.4→0.2.5** (completed implementation packet). **ADR-0031 D8a is now fully shipped end to end.** **NOTE (corrected at the 8th-session closeout): since committed as `523cb57` and PUSHED along with packets 1–2 (`068d7ef`/`c833991`) and packet 4 (`4af08f1`).** **Next: floor-model claim-emission-rate benchmark (proof req #4), or the live-test path (packet 3 + deploy).**
- **2026-07-03 (6th session)** — `Packet 4 — answer-grounding check implemented (ADR-0031 D8a; 0.2.3→0.2.4; branch \`adr-0029-worker-codegen-eval\`)` — **Implement (4a/4b/4c); 4d deferred to tranche 2.** New **`custom_components/isolinear/answer_grounding.py`**: pure-Python metric registry (mean / delta / pearson_r / rolling_mean / daily_max / daily_min / hours_above — recompute over normalized `ts_epoch_ms` history, `pearson_r` hand-rolled so no numpy/scipy is needed on the Pi) + `run_grounding_check` (the 6-step claim check, sentence-initial yes/no tripwire, three-state verified / unverified-caveat / contradicted boundary, `_TOLERANCE=0.05` value↔reference, borderline non-flap at band edges, longest-word-boundary verdict match for negation safety, two-tier guarantee verbatim). **Wired into `_record_codegen_worker_dispatch`** after sandbox success + before serve: `{pass, verified, unverified_caveat}` serve immediately; `{repair_contradicted, repair_soft}` feed a `synthetic_error` into the **shared** codegen repair loop (same `max_codegen_repair_attempts` budget); on exhaustion the saved successful render is served with the answer **withheld** (contradicted) or **caveated** (soft), `answer_verification="unverified"`. `answer_verification`/`withheld_answer` thread `_finish_codegen_success`→`_record_worker_rendered_artifact`→`_build_worker_artifact_metadata`→snapshot chart→card. Worker `_normalize_render_metadata` passes `claims` through (check-only; delete-it→byte-identical, the D3 reconciliation); `_CODEGEN_PROMPT_RULES` extended to emit a well-formed claim. Anchored windows → `grounding_anchor_deferred` caveat (4d re-detection slots in later, no schema churn). Card renders verified / unverified+caveat / withheld, the caveat a **separate** element (verdict prose never edited). **Schemas:** `render_metadata.claims` (×3) + `chart.answer_verification` (artifact + snapshot, ×2 each), all byte-identical; bundle rebuilt+synced. **BDD evidence** `docs/bdd/answer-grounding-check/answer-grounding-check-bdd.md` (scenarios A/B/C/E/F/G/H/J + negation + edge). **Verify:** suite **363 passed / 4 skipped** (+36 grounding tests), frontend **35 passed** (+9), eval `model_authored_analysis` PASS, schema byte-parity + bundle sync green. **NOTE (corrected at the 8th-session closeout): packet 4 since committed as `4af08f1` and PUSHED, as are packets 1–2.** **Next: 4d anchors OR floor-model claim-emission benchmark; or the live-test path (packet 3 + deploy).**

_(older sessions — ADR-0031 drafted + hardened by a real-data benchmark (`c9d6ad3`→`ac71de8`, 4th session, 0.2.1); ADR-0030 implemented in code: pandas/1024MB/repair-everything/codegen-primary + Pillow fallback (`4532ba5`/`a038b9b`/`940887b`, 3rd session, 0.2.1), ADR-0029 KEEP decision + ADR-0030 + the great scaffold purge (`f8f7760`/`255b0c3`, 2nd session), ADR-0029 packet 5 codegen reliability eval (`9320cf0`), packet 3 worker PROVEN LIVE on CT103 + OpenBLAS `RLIMIT_AS` fix (`2bb2747`), packet 4/0.1.49 (`b22992b`), packet 3 Dockerfile (`6321215`) + packets 1–2, ADR-0028/0.1.48, ADR-0027/0.1.47, ADR-0023/0.1.44, ADR-0026/0.1.43 and earlier — live in git history)_
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `ADR-0030 implementation — codegen primary` — DONE (2026-07-02, 3rd session, 0.2.1)

- [x] pandas into the worker image (`worker/requirements.txt` + allowlist; rebuilt `isolinear-worker:dev` 526MB on CT103; a pandas `resample().mean()` render returned a valid PNG in-container over HTTP — proven live)
- [x] Raise sandbox memory cap 256MB → 1024MB (policy default; schema already permitted 1024; test now pins 1024 + asserts pandas allowlisted)
- [x] Repair policy in `job_orchestration.py`: ALL sandbox failure classes repairable incl. `unsafe_code`, bounded by `max_codegen_repair_attempts`; worker re-runs the full static check each dispatch; spec + BDD + evidence revised (`a038b9b`)
- [x] Flip render default: `codegen_enabled` bool → `render_path` select (`auto`|`pillow`, default `auto`); codegen failures FALL BACK to Pillow and complete, surfaced via `render_path` + `render_fallback_reason` on artifact+snapshot + a card notice; explicit `pillow` = no fallback reason; version 0.2.1 (`940887b`); invariant #6 aligned in AGENTS.md + CLAUDE.md
- [ ] ~~Follow-up spec: model-authored transforms~~ — **MERGED into ADR-0031** (answers + transforms; next packet)

### `ADR-0031 — model-authored analysis: answers, not just charts` — D8a COMPLETE (accepted; tranche 1 packets 1–2 + grounding check 4a-4d all shipped)

- [x] **ADR-0031 ACCEPTED** (2026-07-03, `7d266cb`): draft→accepted; proof-gate para dropped (met by the committed benchmark); `CLAUDE.md`/`AGENTS.md` identity line "visualization"→"data-analysis assistant"
- [x] **Spec `model-authored-analysis` + BDD — ACCEPTED** (`9d52103`→`0436eef`): all 7 tranche-1 contract surfaces (answer channel, grounding, D9 timestamps, modality signal, two-part validation + progressive UX, scipy/seaborn, transforms)
- [x] **Packet 1 — answer channel** (`068d7ef`, 0.2.1→0.2.2): `answer_text` passthrough (sandbox `_normalize_render_metadata`) → additive/optional on render-result/artifact/job-snapshot (all copies) → worker-artifact→snapshot `chart.answer_text` → card renders under the caption; codegen grounding prompt (compute AND f-string, verdicts derived). Grounded deterministically (71.2/71.8 → "71.50 degF" at sandbox + over HTTP)
- [x] **Packet 2 — epoch-ms timestamp boundary / D9** (`c833991`, 0.2.2→0.2.3): additive `ts_epoch_ms` (history-series, 3 copies); `_timestamp_to_epoch_ms` + `_history_series_with_epoch_ms` at both codegen build sites; `_codegen_request_view` strips raw `ts`; safe/Pillow untouched
- [x] **Packet 4 spec `answer-grounding-check` + BDD — ACCEPTED** (Fable-designed, human-ratified incl. a recompute-fidelity hardening pass): the claims ledger; research note `answer-verdict-grounding-check` promoted-to-spec
- [x] **Packet 4 — implement (4a/4b/4c)** (0.2.3→0.2.4): new `answer_grounding.py` (pure-Python registry — mean/delta/pearson_r/rolling_mean/daily_max/daily_min/hours_above — + the 6-step check + yes/no tripwire + 3-state boundary + borderline non-flap + longest-match negation safety + allowlist enforcement on `claim.inputs`); wired into `_record_codegen_worker_dispatch` before serve, failures via the shared repair loop, exhaustion → withhold/caveat; `answer_verification`/`withheld_answer` thread artifact→snapshot→card; `render_metadata.claims` (×3) + `chart.answer_verification` (×2 each) schemas byte-identical; card 3-state render + two-tier-guarantee caveat (separate element). Suite 366 passed / 4 skipped (+39), frontend 35 passed (+9); architecture review CONCERNS→resolved (allowlist gap closed)
- [x] **Packet 4d — event anchors** (0.2.4→0.2.5, UNCOMMITTED): `_anchor_criteria_ok`/`_detect_transitions`/`_select_occurrence`/`_resolve_anchor` in `answer_grounding.py` implement spec §1a reproducibility + re-detection over the delivered raw-state timeline; wired into `_check_claim` step 4 ahead of registry recompute. `grounding_anchor_unreproducible` (caveat, by construction) / `grounding_anchor_unfound` / `grounding_anchor_mismatch` (contradicted). No schema change (window was already open). 5 new tests; BDD-evidence + architecture reviews both OK. Suite 371 passed / 4 skipped (+5), frontend unchanged 35 passed. **ADR-0031 D8a is now fully shipped end to end.**
- [x] **Packet 4 proof req #4 — floor-model claim-emission rate** (0.2.5→0.2.6, `079431d`/`e1c6ef7`, 8th session): benchmark extended (18 prompts, `claim`/`claim_window` flags + `anchor-01`), emitted claims scored by the REAL production `answer_grounding` checker against fresh real HA history (gitignored); three live `gemma4:e4b` runs → **emission reliable (6/6, 5/5 of executing claim-expected prompts), well-formedness high, registry-verified 0** (three measured causes: value-stringification → raw-JSON-number prompt hardening shipped; free metric naming → caveat, correct per D3; exact-timestamp `pearson_r` intersection → the "prescribe the alignment" open item confirmed live); anchored windows 0/2 (acceptable tranche-1); no false "verified"; live `verdict_contradicted` (pd-05) caught. `_CODEGEN_PROMPT_RULES` now documents the anchored-claim window shape (+ prompt-rule test). FINDINGS.md carries the evidence
- [x] **Packet 3 — scipy+seaborn** into the worker image (`8964bc1`, 0.2.6→0.2.7, 9th session): libs into `worker/requirements.txt` + sandbox allowlist (exact-match `scipy`/`scipy.stats`/`scipy.signal`/`scipy.optimize`/`seaborn`); stale `_CODEGEN_PROMPT_RULES` "import nothing except matplotlib" rule fixed to enumerate the five libs. **Live on CT103 (Scenario H):** image 719MB, in-container suite 27 passed / 0 skips, all five import under the `-I` 1024MB cap, `scipy.stats` correlation + `seaborn.heatmap` → valid PNG. Evidence in `bdd/model-authored-analysis/...-evidence.md`
- [ ] **Packet 5 — output-modality signal** (`output_modality` on planner-result; normalize to `both` for slice 1) — PARKED
- [ ] **Packet 6 — visual validator + progressive-verification UX** (Ollama `/api/show` vision probe; checklist prompt; `verification_status`; card non-terminal states; bounded visual-repair) — PARKED
- [x] Extend `evals/prompts/benchmark_prompts.json` + `evals/analysis_benchmark/` with the answer-family (grounding checks + floor-model claim-emission rate) — done in the proof-req-#4 packet above (`e1c6ef7`)
- [x] **Push packets 1–4d + the proof-req-#4 work** — ALL PUSHED to `origin/adr-0029-worker-codegen-eval` at the 8th-session closeout (`068d7ef`/`c833991`/`4af08f1`/`523cb57`/`079431d`/`e1c6ef7` + closeout commit)

### `ADR-0032 — deployment-configured worker token; retire ADR-0015/0016 machinery` — SHIPPED (accepted, 0.2.8, `54eaffb`, 9th session)

- [x] **ADR-0032 + spec `deployment-worker-token` + BDD — ACCEPTED** (direction: Colin 2026-07-03; implemented + live-proven 2026-07-04). Decisions/specs README indexes synced
- [x] **`worker_token_storage.py`** — integration-owned HA Store (`isolinear_worker_deployment_token`, one doc keyed by entry_id, semantic-memory shape); `save_token`/`clear_token`/`token_for` + `stored_worker_token`; ≥24-char floor; summary is presence-only (never token values)
- [x] **Options-flow write-only `worker_api_token` password field** (`config_flow.py`): `extract_worker_token_action` (keep/save/clear/too-short) splits the token out **before** options validation (options/config data never carry it — `config_schema` secret fail-closed intact); never pre-filled; `_apply_worker_token_action` persists + rebuilds the renderer client in the flow (HA fires listeners only on options change — arch-review finding)
- [x] **`setup_worker_renderer`** now builds the client from `worker_endpoint_url` + `stored_worker_token`; missing either → disabled `worker_renderer_token_missing` → `render_path: auto` renders via Pillow (ADR-0030 surfaced fallback, no new failure mode). `check_health()` is the on-demand health surface
- [x] **Deleted ~3.1K LOC** of uncovered ADR-0015/0016 machinery: 8 modules (`worker_token_lifecycle`/`worker_readiness`/`worker_health`/`worker_health_polling{,_constants,_contract,_state,_storage}`) + 5 schemas ×2 copies + the `__init__` lifecycle-abort/readiness/health/polling chain; `semantic_memory.py` stale docstrings cleaned; deletion-guard test pins modules/schemas gone + no imports (custom_components AND evals)
- [x] **Live-proven** (`evals/deployment_worker_token.py`): real client → compose-managed CT103 worker with the SOPS deployment token → `ready`; wrong token → surfaced 401; no token material in output. Suite 391 passed / 4 skipped (+18); arch review CONCERNS→resolved; BDD A–F evidence at `bdd/integration/deployment-worker-token-evidence.md`
- [ ] **Colin: enter `worker_endpoint_url`=http://10.0.1.39:8080 + paste the SOPS token** in HA options once 0.2.8 ships (token via `cd ~/repos/homelab && sops -d secrets/docker-host.enc.yaml | grep isolinear_worker_token`)

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
- [x] **Coordination:** homelab worker-service deploy DONE (9th session, homelab `311eac9` on `main`) — the worker runs as a `docker_host` compose service on CT103; spec+BDD `isolinear-worker-service` A–E proven live

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
- (d) ~~Keep remaining worker/orchestration work split into smaller packets:
  token rotation UI or real Home Assistant Repairs/automatic repair semantics,
  automatic/durable provider retry semantics, durable retry queue/scheduler
  behavior, durable polling production-hardening~~ — **largely RETIRED by
  ADR-0032 (9th session):** token rotation is now a deployment action
  (change SOPS + re-apply + re-paste; no UI); the durable token-lifecycle /
  readiness / health-polling machinery is deleted. Any future
  integration-managed credentials (e.g. an HA add-on wrapper) is a new ADR on
  the deployment-configured baseline, not a revival of ADR-0015/0016.
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
- (l) **STUB (Colin, 2026-07-02): conversational refinement + saved live
  visualizations** — likely one or two future ADRs, after ADR-0031 lands.
  (1) *Refinement:* back-and-forth with the model to refine a chart —
  mechanically the codegen repair loop with human feedback instead of sandbox
  errors (previous code + instruction → revised code). (2) *Saved live cards:*
  "save" a refined visualization as `{generated python_code, entity_ids,
  RELATIVE window, render policy}` in an integration-owned versioned store
  (SemanticAlias-style, use-time invalidation when an entity leaves the
  allowlist); the *integration* refreshes on a schedule (`async_track_time_
  interval`) — re-fetch history through the allowlist path, re-resolve the
  relative window deterministically, dispatch the SAVED code to the worker
  (static check re-runs every dispatch; worker stays stateless, never queries
  HA) — **no model call in the refresh cycle**. Refresh failures fail soft:
  keep the last good render + a stale/error badge (bounded model-repair on
  refresh failure = an ADR knob, lean no for slice 1). Card creation stays
  user-driven (`custom:isolinear-card` in saved-viz mode pointing at a saved ID
  — the integration does NOT write Lovelace config; invariant #2 intact).
  Synergy with ADR-0031: the answer channel refreshes for free (live-updating
  computed numbers, not just the PNG). Could ship saving before refinement
  (one-shot "pin this"). **OPEN QUESTION (axes drift):** a viz created in
  winter has winter-scaled temp axes; summer data will clip or cramp. Colin's
  proposal: instruct the model to always write axis limits scaled to the
  data's high/low. Alternatives to weigh in the ADR: just *omit* explicit
  limits (matplotlib autoscales by default — simplest and robust) vs.
  data-scaled-with-padding vs. fixed-at-creation; note autoscale makes a live
  card's y-scale jump between refreshes (visual comparability suffers, can
  exaggerate noise on quiet days) — maybe quantized/padded bounds, or a
  refresh-time policy outside the generated code. Decide in the saved-viz ADR.
- (m) **Default `max_codegen_repair_attempts` is 1** — stingy now that repair
  actually works (0.2.10). Consider raising the default to 2–3 (the packet-5
  eval showed gemma needs a couple of repair passes for static failures).
- (n) **NEW BUG (Colin, 2026-07-04 live testing) — details TBD.** Found during
  the 0.2.11 live bring-up; Colin deferred it to the next session and will
  describe it at session start. Placeholder so it is not lost; fill in the
  symptom + repro when Colin reports it.

## Blockers

- None.
