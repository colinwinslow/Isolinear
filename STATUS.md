# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-07-07, nineteenth session (**Fixed open-queue (w): the live e2e-15 heatmap garbage — "ship simple" (0.2.26).** The single-numeric ADR-0023 envelope has no heatmap family, so the planner deterministically (6/6) routes "Show a heatmap … by hour of day and day" to `histogram` — then the ADR-0034 conduit hands codegen a `user_request` saying "heatmap", and codegen honours BOTH the histogram spec and the heatmap word → the live 1/2-bar epoch-ms nonsense (accept≠quality). Repros: `scripts/repro_e2e15{,_planner,_planner_fix}.py`. **Colin's call ("ship simple"):** degrade the ask to the histogram the planner already picks — a niche temporal heatmap isn't worth the codegen pivot idiom, and this keeps the WORD "heatmap" reserved for the future spatial/floorplan renderer (open-queue (c)); a temporal calendar heatmap, if ever built, gets its own NAMED family. **The frame that made it one rule, not three:** the bug is codegen overriding the planner's chart FAMILY via `user_request`, violating invariant #9 (the model never chooses `chart_type`) — family is the planner's job, `user_request` owns only the COMPUTATION. **Shipped (0.2.26):** one `_CODEGEN_PROMPT_RULES` sentence — render only line/histogram/bar; never draw a 2-D heatmap/matrix/grid (no `seaborn.heatmap`/`pcolormesh`/`imshow`/`hist2d`); a single-sensor heatmap ask degrades to a histogram of that sensor's values; `user_request` may change WHAT is computed, never the family. **Eval-gated** with new `evals/heatmap_rule_gate.py` (production codegen path, live histogram chart_spec + heatmap `user_request`, marker-gated with/without arms): **with-rule 3/3 clean histograms** (8 bins, 67.6–75.4 °F, first attempt), **without-rule 0/3** (all drew the 2-D grid — e2e-15 reproduced). Spec `model-authored-analysis` §2 updated; regression test `FamilyDegradePromptRuleTests`; suite **452/4** (+1). Integration-only (prompt text) — ships via HACS, NO worker rebuild, no new ADR. NEW open-queue: (aa) latent codegen stray-quote `transAxes'` guard-branch emission; (bb) multi-sensor heatmap-of-correlations degrades to lines not a histogram. _(prior)_ 2026-07-06, eighteenth session (**Verified 0.2.24 live — the e2e targets flipped — landed the open-queue (u) re-plan anchor, and root-caused e2e-14.** Ran the live e2e harness against **0.2.24** (18 prompts): **12 PASS / 3 PARTIAL / 3 FAIL** (prior 8/5/5). The three testable 0.2.24 alignment/planner targets ALL FLIPPED — e2e-12 (Kitchen−Basement delta series + computed "1.25 °F"), e2e-13 (real Pearson 0.13 on an isolated re-run; the batch run hit a transport blip → Pillow), e2e-18 (per-sensor deviation series; was the duplicate-source planner rejection the 0.2.24 satisfiability rule fixed). e2e-11 (mean) improved — the alignment artifact is gone — but the model plots a flat scalar average line, not a computed mean SERIES (transform intent unmet). **Root-caused e2e-14** (cross-metric correlation, failed `model_provider_planner_not_chart_spec_ready`) via new `scripts/repro_e2e14.py`: it is an **entity-resolution** gap — resolution discloses only the temp sensor, so the planner CORRECTLY clarifies that the kitchen-humidity sensor is required (friendly name "Kitchen ecobee Humidity" ≠ prompt "kitchen humidity"); disclosing both sensors plans the correlation fine. NOT a planner or re-plan bug. **Landed open-queue (u) — bounded re-plan on validation failure (spec + BDD + evidence + anchor, 0.2.25):** `_record_model_provider_plan` now wraps a renamed `_plan_once` in a bounded re-plan loop over the recoverable output-quality gates (`_PLANNER_REPLAN_TRIGGER_CODES` = `invalid_model_provider_chart_spec`, `invalid_planner_result`), reusing the existing validation gates + planner client; result carries `planner_replan_attempts`. **Opt-in, reader default 0** (`max_planner_replan_attempts`) so the landing is purely additive — and it deliberately **never re-plans `model_provider_planner_not_chart_spec_ready`** (post-`validate_planner_result_contract` that always means a legitimate `clarification_needed`/`cannot_resolve`; re-planning would override the model's correct choice — validated live by e2e-14). Tests 5/5, suite 451/4. **Fixed the harness diagnostic gap** Colin flagged: `evals/e2e_pipeline_harness.py` preserved only the last poll, discarding streamed selection/planning reasoning (ADR-0025) — the only reachable "why" for a planner-stage failure; it now accumulates it → `<id>_reasoning.txt` + manifest `reasoning_tail`. **Accepted ADR-0035** (v0.3 saved-viz + demolition; README synced; ARCHITECTURE spine noted). Version **0.2.25** — nothing behavior-changing ships (re-plan default-off; the harness/scripts/docs are non-integration). NEW open-queue items from the judged run: (v) e2e-14 resolution gap, (w) e2e-15 heatmap emits garbage codegen (epoch-ns x-axis, 1/2 y-values — worse than "degrades to histogram"), (x) e2e-09 door answer_text has zero-duration intervals, (y) e2e-03 two-line chart missing legend, (z) e2e-11 "average of X and Y" plots a scalar line not a mean series; and open-queue (s) histogram-unit looks FIXED (e2e-16 correct — confirm before closing). **See [[isolinear-model-choice-by-packet]] for the Fable-recommended packets** (demolition step-1 job_orchestration split = one Fable planning session; the heatmap (w) + e2e-11 (z) diagnoses are Fable-shaped). Full judged report: gitignored `evals/e2e_runs/20260706T205049Z/REPORT.md` (+ e2e-13 re-run `…220549Z`).)

_(prior)_ 2026-07-06, seventeenth session (**Closed the headline open-queue (q) gap: the model-authored analysis layer now FIRES live.** ADR-0034 (accepted) — **the user's request reaches the codegen model.** Diagnosis (design-first, Fable): the gap was structural, not model capability — the codegen payload never carried the user's prompt (its task was "render the ChartSpec"; the answer rule keyed on a "prompt" the model never saw = dead code), the 0.2.19 grounding rule hard-instructed raw-line plotting, and the planner was told analysis is unsatisfiable (gemma on the heatmap: "I cannot generate a true heatmap using the available chart types"). A production-path probe (`evals/analysis_intent_probe.py`, execution-truth judging) measured it: **baseline 0/12 fired vs the intent arm 12/12.** Implemented (0.2.23): `generate_chart_code`/`repair_chart_code` take a bounded `user_request` (a generation-time arg that NEVER enters the worker dispatch), the codegen task is reframed to "fulfill user_request", the plot rule becomes default-with-a-compute-exception, the answer rule keys on `user_request`, and a planner rule declares analysis prompts satisfiable (plan raw inputs; generated code does the math). **Live e2e re-run (0.2.23, all 18 prompts): the analysis layer fires** — grounded answers compute (e2e-06 "70.84°F", e2e-09 door-open duration, e2e-08 humidity delta), transforms plot (e2e-11 cross-sensor mean series, e2e-17 real rolling mean), and e2e-09 (binary door) went from an empty degenerate-axis line to a correct step track + duration answer. **Firing exposed a second tier of codegen-quality bugs the silence had masked** (accept≠quality, exactly what the harness is for), so two Fable-shaped follow-ups shipped same session (0.2.24): (1) **irregular-series alignment** — cross-series math on disjoint per-entity timestamps produced a union-index mean spiking above both inputs (e2e-11), an empty "nan °F" delta (e2e-12), and "no common timestamps" correlation (e2e-13, the 8th-session pearson_r gap live). The production rules had the D9 epoch-ms lesson but never the benchmark's "resample/align before combining" lesson. New `evals/alignment_rule_gate.py` reproduced all three offline (0/6) and gated the fix: a prose-ordered rule only reached 2/6 (gemma dropna'd the raw union frame first → all-NaN), but a LITERAL per-entity idiom (`Series(...).resample('5min').mean().interpolate()`, combine only after) hit **9/9 vs 0/6** — the ADR-0033 axvspan lesson generalized (floor models follow a code idiom where they scramble an equivalent prose ordering). (2) **e2e-18 invalid_model_provider_chart_spec** — a planner variance tail: a sample plans the computed result ("Deviation") as its own series, constrained decoding forces it onto an already-used approved entity_id → duplicate-source rejection (the 0.1.37 relabel-reuse class, new door). The satisfiability rule now prohibits planning the computed result as a series; re-check 7/7 chart_spec_ready + contract-valid. Suite 446/4; evals PASS. **0.2.23 accepted (pushed) then 0.2.24 (pushed). Also this session: architecture-tracking reset — accepted ADR-0034, drafted ADR-0035 (v0.3 north star: saved re-runnable analysis code + demolition plan), wrote `docs/ARCHITECTURE.md` (the current-state map — the fix for "34 ADRs is unholdable"), archived superseded ADR-0004.** _(prior)_ 2026-07-06, sixteenth session (**D + E from the open queue, plus a live e2e harness run that found a whole non-working capability.** (D, 0.2.22) **Retired the bare-non-ASCII codegen prompt rule (open-queue (o))** — eval-gated with a new `evals/codegen_rule_gate.py` that drives the PRODUCTION codegen path (real `generate_chart_code`/`repair_chart_code`, real `_CODEGEN_PROMPT_RULES` + prompt-view projection) with production-shaped °F/%-unit `ts_epoch_ms` data against live gemma4:e4b + a live worker, WITH vs WITHOUT the rule, 6 cases × 3 runs: **36 runs, ZERO bare-non-ASCII incidents in either arm** (both 18/18 accepted). The 0.2.17 unit-grounding rule keeps ° out of bare literals structurally, so the rule gated nothing; dropped. Integration-only (ships via HACS). (E, open-queue (p)) **Built the Claude-in-the-loop live e2e harness `evals/e2e_pipeline_harness.py`** — drives the REAL card path (`job/start` + snapshot polling over the HA WS API) for a fixed prompt set against live HA + worker + gemma, captures the served PNG + metadata into gitignored `evals/e2e_runs/<ts>/`, and Claude judges each by looking (no programmatic assertions, per Colin). Prompt set expanded to 18 (Colin's ask): humidity/%, state timeline, renderable short-window overlay, transforms, correlation, heatmap, histogram, smoothing. **Its runs found bugs synthetic checks miss.** WORKER FIX (committed, deployed to the CT103 `:dev` service): a generated non-string `render_metadata.warnings` entry made the worker's OWN response validation raise → HTTP 500 → the integration saw an unrepairable transport fault → Pillow fallback with zero repairs (same trap for model-stringified claim values). `_normalize_render_metadata` now coerces every model field to its contract type + `_coerce_claims` sanitizes/drops malformed claims + a residual leak degrades to a structured repairable `invalid_render_metadata` instead of a 500; also allowlisted `matplotlib.patches`/`lines`/`ticker`/`colors` (the ADR-0033 "e.g. a Patch" hint burned repair attempts on `import_not_allowlisted`). Second live run (18 prompts, worker fix live, HA still 0.2.20): **8 PASS / 2 PARTIAL / 8 FAIL, zero Pillow fallbacks.** HEADLINE: **the model-authored ANALYSIS layer does not fire live** — every transform/correlation/question prompt (average, delta, correlation, deviation, rolling, the answer_text question) collapsed to plotting the RAW input series with an analysis-flavored title and an EMPTY `answer_text`/claims; heatmap + cross-metric correlation failed at the planner. WIN: **ADR-0033 overlay bands proven live end-to-end at short window (e2e-10)** — the exact 0.2.21 fix, on the real pipeline. Secondary bugs: binary/timeline entity renders EMPTY through codegen (e2e-09, invariant-#9 gap — codegen has no timeline handling + degenerate multi-year axis); histogram misplaces the unit (°F on the density y-axis). Suite 437/4 (+3 worker coercion tests); new open-queue (q)/(r)/(s)/(t). Report: `evals/e2e_runs/20260706T035420Z/REPORT.md`. Nothing pushed (commit-only).**)

_(prior)_ 2026-07-05, fifteenth session (**Fixed the 0.2.18 empty-chart / wrong-unit regression Colin hit on `main` (basement-only + kitchen/basement weekend charts rendered COMPLETE but with NO data plotted and °C/"Value" axes on °F sensors). Reproduced live end to end (real planner → real HA history → live gemma, executing each generation) — NOT overflow (real prompts ~1.8–3.2K tok). Root cause: 0.2.18's pure per-series SUMMARY removed the concrete data that anchored the floor model's code. THREE interacting failures: (1) the summary renamed the point list to `sample_points` (absent at runtime — runtime uses `points`); caught gemma writing `series['sample_points']` → KeyError/empty. (2) With only a summary, gemma drove plotting/labels off the `chart_spec` (5/6 real runs) — which carries a planner-HALLUCINATED unit (`°C` on °F sensors) and `source.entity_id` (no top-level `entity_id`) → empty plots + wrong units. (3) The `PlannerResult` schema REQUIRES a `unit` the planner is never given → it guesses. **The fix (Colin's steer — bounded real points, count chosen by experiment; + fix the planner too):** `_history_series_prompt_view` now carries a bounded, evenly-downsampled PREVIEW of REAL points under the SAME runtime key `points` (+`points_truncated`), first+last kept (`_downsample_preview`, `_CODEGEN_PROMPT_PREVIEW_POINTS=12`). Live grounding experiment (execution-truth): summary=1/3 grounded (2/3 EMPTY); ≥6 pts = solid; picked 12 for margin (~+950 tok, 2 series → 3.2K). Prompt rules now make `history_series` the sole data authority (plot by iterating it directly; **chart_spec is intent-only** — never read data/units/series-list from it). Planner unit fixed deterministically: `_apply_catalog_units` overwrites each series' `unit` from the catalog `unit_of_measurement` after planning (°C→°F confirmed live). **Verified live on the fixed code: 5/5 runs plot the full data (was 2/3 empty), 4/5 clean °F; the 1/5 was an unrelated gemma runtime bug that STILL plotted the data → repair loop / surfaced Pillow fallback (reinforces open-queue (m)).** Suite 427 passed / 4 skipped (+6); evals `codegen_generation_path` + `model_authored_analysis` PASS; spec `model-authored-analysis` updated. Integration-only, NO worker/frontend rebuild. Version 0.2.19.**) **FOLLOW-ON 0.2.20 (same session): fixed the "Value ()" empty-axis Colin saw on the FIRST successful 0.2.19 render** — 0.2.19 restored data plotting (real kitchen+basement lines) but the y-axis read "Value ()" (empty unit). Reproduced live: the model reads the unit CORRECTLY from `history_series[i]['unit']` (6/6 runs) and renders it verbatim, so an empty label means the DATA's unit is empty. Root cause: the catalog snapshots `unit_of_measurement` at BUILD time, but cloud entities (ecobee) are often `unavailable` then (no unit attr) → the catalog cached `null` even though the live sensor now reports °F; `history_series.unit` (= catalog unit) and `_apply_catalog_units` both came up empty. Fix: `_approved_catalog_items` now backfills a missing unit from the entity's LIVE state (`backfill_catalog_units_from_state`, in `history_retrieval`, applied in BOTH `_approved_catalog_items` copies), never overriding a present catalog unit. Verified live end to end (real live state None→°F backfill, then 4/4 generations render "(°F)"). Suite 430 passed / 4 skipped (+3). NOTE: the axis WORD is still sometimes generic "Value" (vs "Temperature") — cosmetic, "Value (°F)" is informative; optional follow-up to surface device_class.**)

_(prior)_ 2026-07-05, fourteenth session (**Fixed the live `unsafe_code`/`syntax_error` fallbacks on 0.2.17: the codegen PROMPT carried the FULL recorder points → tens of thousands of tokens overflowed Ollama's ~4K default `num_ctx` → system prompt/rules evicted → gemma replied with prose → `syntax_error@L1`. `_history_series_prompt_view` switched to a per-series SUMMARY (metadata + point_count + range + stats + 3 sample_points), the dispatched render request still carries every point; `num_ctx=8192`; runtime overflow safety net (`prompt_eval_count >= num_ctx` → `codegen_context_overflow` fallback + card guidance). Suite 420/4; version 0.2.18. NOTE: the pure summary is what the 15th session had to correct — it removed the model's data grounding.**)

_(prior)_ 2026-07-05, thirteenth session (**🎉 FIRST LIVE CODEGEN CHART RENDERED END TO END — HA → gemma4:e4b → fenced matplotlib → CT103 sandbox → PNG bytes → served card. Three bugs fixed to get there, then polish. (1) `0.2.15` (`ec57839`) fence instruction: the initial gen hit `syntax_error@L11` but every repair degraded to `syntax_error@L1` — gemma replied with prose + UNFENCED code, so `_extract_python_code`'s no-fence fallback returned the raw text (prose = line 1). `_CODEGEN_SYSTEM_PROMPT` said "no markdown OUTSIDE a fence" but never to USE one; now it mandates a python code fence. (2) homelab tmpfs perms (`4e80bbc` on homelab `main`): code then ran but hit `PermissionError` on savefig — the compose tmpfs `/var/lib/isolinear-worker/work` was `root:root` but the worker runs uid 10001; added `uid=10001,gid=10001` (live-fixed on CT103 + committed to the IaC template). (3) `0.2.16` (`9e14b9e`) image bytes: worker reported `status=success` but the integration failed `missing_worker_image_bytes` — the result carried only `image_path` (unreachable from the HA box); the HTTP server now inlines `image_bytes_base64` on success (field already in schema; base64 is stdlib). Worker rebuilt on CT103. THEN it rendered live. (4) `0.2.17` (`0a02b51`) polish, all HACS-only: wrong unit (°C for an °F sensor — model guessed; the real unit was already in the prompt data `history_series[i]['unit']` but no rule used it → grounding rule reads it from data, which also keeps `°` out of a bare literal); tiny fonts (matplotlib defaults scaled down on a phone → legibility rule: figsize ~8×4.5 @ dpi 110, explicit font sizes, `bbox_inches='tight'`); card letterbox (`.result img` `object-fit:contain` in a forced 260px row → `height:auto`, fills width). Suite 415 passed / 4 skipped; frontend 35 passed; evals `codegen_sandbox`/`worker_http_server`/`codegen_generation_path`/`model_authored_analysis` PASS; spec `worker-http-server` corrected (base64 inlining now IMPLEMENTED, was marked deferred). Next: Colin HACS-redownloads 0.2.17 + retests — confirm unit/fonts/fit on the phone.**)

_(prior)_ 2026-07-04, twelfth session (**Second live codegen fallback fixed: `syntax_error@L19` from a bare `°` token. Diagnosed from live logs — worker `docker logs` showed `error=unsafe_code violations=[syntax_error@L19]`, and the HA system-log WARNING carried `invalid character '°' (U+00B0)`. The fence-extraction fix (0.2.12) worked (L1→L19), but the model wrote the degree symbol as a BARE Python token (e.g. `ax.set_ylabel(Temperature °F)` — no quotes), which `ast.parse` rejects; repair re-emitted it because the repair task only described disallowed imports/attrs/calls, not syntax errors. **0.2.13 (`345be4a`):** generation-side `_CODEGEN_PROMPT_RULES` rule (labels must be Python string literals; no bare non-ASCII tokens) + repair-task clarification. **0.2.14 (`458a8b7`) — the generic fix (Colin steered away from per-error prompt instructions):** worker `static_safety_check` now attaches `source_line` — the exact offending text — to EVERY line-numbered violation via `_attach_source_lines` (syntax_error + all unsafe_code); the repair task points at `source_line` generically and the hardcoded `°` example was removed. No schema change (`error.details` is `additionalProperties:true`); `_sandbox_error_view` already deep-copies violations so it flows to the repair prompt unchanged. Insight: the info was never missing (syntax errors have no traceback; the full diagnostic + prior code were already in the prompt) — small models just can't COUNT to line 19 in their own output; handing them the line text is the lever. Suite 414 passed / 4 skipped (+2), evals `codegen_sandbox` + `codegen_generation_path` PASS; spec `codegen-generation-path` updated. **DEPLOY SPLIT:** the generation-side prevention ships via HACS (integration-only); the `source_line` robustness is WORKER-side and needs an image rebuild + `docker compose up -d --force-recreate isolinear-worker` on CT103 to go live. Next: Colin HACS-redownloads 0.2.14 (+ optional worker rebuild) and retests "kitchen temperature".**
**Phase:** `LIVE END TO END + ANALYSIS FIRES — the codegen chart chain and the model-authored analysis layer (ADR-0034 conduit) both work live; 0.2.24 verified 12 PASS/3 PARTIAL/3 FAIL on the 18-prompt e2e harness. Remaining live gaps are being closed one bounded packet at a time via the harness accept gate: 19th session fixed the e2e-15 heatmap garbage (open-queue (w), family-degrade rule). Left: the planner/transform variance tails (e2e-11 mean-intent (z), e2e-14 resolution (v)), binary/timeline routing (r), the >2-day tiering wall (t), and cosmetics (legend (y), door-duration (x)). ADR-0035 (v0.3 saved-viz + demolition) is ACCEPTED — the demolition sequence (split job_orchestration.py first, Fable-shaped) is the strategic through-line whenever Colin starts it.`
**Next bounded packet:** `(A) DEPLOY + VERIFY — DONE (18th session): live e2e re-run on 0.2.24 confirmed the alignment/planner fixes — e2e-12/13/18 flipped, e2e-11 partial. (A2) FINISH open-queue (u): the config surface (config_schema + config_flow field + coercion), flip the reader default 0→1 (bundle with (m); update the failure-path call-count tests), add the Scenario-E (mixed-routing) test, and the live e2e-18 duplicate-source recovery proof. (v) e2e-14 entity-resolution gap — make "kitchen humidity" resolve to sensor.kitchen_ecobee_humidity (Opus-executable, root cause known). (w) e2e-15 heatmap garbage — FABLE-shaped diagnosis (first-class seaborn heatmap family vs codegen pivot). (z) e2e-11 mean-intent — FABLE-shaped (why the model draws a scalar line not a mean series). (B) NEW open-queue (u): a bounded re-plan-on-validation-failure pass — the planner variance tails (e2e-14 cross-metric corr still fails at planner; e2e-18's class) would close structurally with one deterministic re-plan when validate_chart_spec_contract rejects, instead of prompt-by-prompt hardening. (C) open-queue (m): raise default max_codegen_repair_attempts (still 1) — now more urgent, repairs do real analysis work. (D) open-queue (r): binary/timeline routing — e2e-09 IMPROVED (step track + duration answer via the conduit) but still a 0/1 line not a true categorical track; decide Pillow-step vs codegen-timeline. (E) open-queue (t): the >2-day state-overlay tiering wall (e2e-04). (F) heatmap (e2e-15): DONE (19th session, 0.2.26) — "ship simple": codegen family-degrade rule sends the heatmap ask to a histogram (the planner's pick), gated 3/3 vs 0/3; "heatmap" reserved for future spatial/floorplan (open-queue (c)). (G) cosmetics: axis word (device_class), histogram unit axis (open-queue (s)). PARKED: packet 6 visual validator; anchored-window tranche-2. **STRATEGIC: ADR-0035 (v0.3 saved-viz north star + demolition) is DRAFT awaiting Colin — if accepted, the demolition sequence (split job_orchestration.py, retire first_real_vertical_slice, shrink ChartSpec, retire Pillow histogram/aggregate) becomes the through-line.**\`
**Current readiness:** `main is 0.2.26 (19th-session closeout: the open-queue (w) heatmap family-degrade rule). 0.2.26 is integration-only (one codegen prompt rule) — ships via HACS, NO worker rebuild (the ADR-0034 conduit never crosses the data boundary; the CT103 \`:dev\` worker still carries the 16th-session metadata-500 coercion + matplotlib-submodule allowlist; healthy). HA runs 0.2.24; a 0.2.26 HACS redownload deploys the heatmap fix AND the dormant 0.2.25 re-plan code. The analysis layer FIRES live (answers compute, transforms plot). Standing tools: the live e2e harness (\`evals/e2e_pipeline_harness.py\`, 18 prompts), the intent probe (\`evals/analysis_intent_probe.py\`), the alignment gate (\`evals/alignment_rule_gate.py\`), the rule-gate eval (\`evals/codegen_rule_gate.py\`), the NEW heatmap gate (\`evals/heatmap_rule_gate.py\`), and the e2e-15 repros (\`scripts/repro_e2e15{,_planner,_planner_fix}.py\`). Docs: \`docs/ARCHITECTURE.md\` (current-state map), ADR-0034 (accepted), ADR-0035 (accepted). Endpoints editable in Configure; token via ADR-0032. Homelab \`main\`: tmpfs-perms (\`4e80bbc\`) + worker compose service (\`311eac9\`).\`

> **⚠️ Direction (2026-07-02, supersedes the 2026-06-12 banner):** ADR-0030 —
> matplotlib codegen via the sandboxed worker is the PRIMARY render path;
> Pillow is the fallback; the model is empowered to transform data in generated
> code. The 2026-06-12 reality pivot completed: the simulated scaffold is
> deleted (commit `f8f7760`), pytest is the single source of behavioral truth
> (`docs/reality-pivot-review.md` is historical context).

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-07-07 (19th session)** — `Fixed open-queue (w): the live e2e-15 heatmap garbage — codegen family-degrade rule, "ship simple" (0.2.25→0.2.26)` — **Root-caused and closed the last non-wall live e2e FAIL.** Repros (`scripts/repro_e2e15{,_planner,_planner_fix}.py`): the single-numeric ADR-0023 envelope has NO heatmap family, so the planner deterministically (6/6) routes "Show a heatmap … by hour of day and day" to `chart_type: histogram` (emitting the exact title on the live garbage render), then the ADR-0034 conduit hands codegen a `user_request` saying "heatmap" — codegen honours BOTH → the live 1/2-bar epoch-ms nonsense (accept≠quality). The counterfactual arm showed gemma CAN render a real calendar heatmap but 2/3 runs died on a repair-proof stray-quote emission (`transform=ax.transAxes')`). **Decision (Colin, "ship simple"):** degrade to the histogram the planner already picks — the temporal heatmap is niche, and this keeps the WORD "heatmap" reserved for the future spatial/floorplan renderer (open-queue (c)); a temporal calendar heatmap, if ever built, gets its own NAMED family. **The frame that made it one rule not three:** the bug is codegen overriding the planner's chart FAMILY via `user_request`, violating invariant #9 (the model never chooses `chart_type`) — family is the planner's job, `user_request` owns only the COMPUTATION. **Shipped (0.2.26):** one `_CODEGEN_PROMPT_RULES` sentence — render only line/histogram/bar; never draw a 2-D heatmap/matrix/grid (no `seaborn.heatmap`/`pcolormesh`/`imshow`/`hist2d`); a single-sensor heatmap ask degrades to a histogram of that sensor's values; `user_request` may change WHAT is computed, never the family. **Verify:** new gate `evals/heatmap_rule_gate.py` (production codegen path, live histogram chart_spec + heatmap `user_request`, marker-gated with/without arms, execution-truth judge = a clean 1-D histogram not a 2-D QuadMesh/image) — **with-rule 3/3 clean histograms** (8 bins, 67.6–75.4 °F, first attempt each), **without-rule 0/3** (all drew the 2-D grid — e2e-15 reproduced); suite **452/4** (+1 `FamilyDegradePromptRuleTests`); spec `model-authored-analysis` §2 updated. Inline invariant review OK (prompt text only; reinforces invariant #9; no schema/service/sandbox/data-boundary change; `user_request` still never crosses to the worker); arch subagent not spawned (bounded prompt-level change on the accepted ADR-0034 path), available on request. No BDD scenario (the eval gate is the proof artifact; no user-facing contract changed). Integration-only, ships via HACS, NO worker rebuild, no new ADR. Findings: `evals/prompts/heatmap_diagnosis_findings.md`. NEW open-queue: (aa) latent codegen stray-quote `transAxes'` guard-branch emission; (bb) multi-sensor heatmap-of-correlations degrades to lines not a histogram (coherent, weaker). **Next: open-queue (u) finish / (v) / (z) / (x) / (y).**

- **2026-07-06 (18th session)** — `Verified 0.2.24 live (e2e targets flipped), landed the open-queue (u) re-plan anchor, root-caused e2e-14, fixed the harness diagnostic gap (0.2.24→0.2.25)` — **Ran the live e2e harness on 0.2.24 (18 prompts): 12 PASS / 3 PARTIAL / 3 FAIL (prior 8/5/5).** The three testable alignment/planner targets ALL flipped: **e2e-12** (delta series + "1.25 °F" answer), **e2e-13** (real Pearson 0.13 — isolated re-run; batch run hit a transport blip → Pillow), **e2e-18** (deviation series; was the duplicate-source planner rejection). **e2e-11** improved (alignment artifact gone) but plots a scalar average line, not a mean series. **Root-caused e2e-14** via new `scripts/repro_e2e14.py`: an **entity-resolution** gap (only the temp sensor is disclosed; the planner correctly clarifies the humidity sensor is required — "Kitchen ecobee Humidity" ≠ prompt "kitchen humidity"; disclose both → plans fine). NOT a planner/re-plan bug — which **validated the (u) design** (never re-plan a clarify). **Landed open-queue (u)** — bounded re-plan on validation failure: spec + BDD + evidence + anchor. `_record_model_provider_plan` wraps `_plan_once` in a bounded loop over recoverable output-quality gates (`invalid_model_provider_chart_spec`, `invalid_planner_result`), reusing the existing gates; result carries `planner_replan_attempts`; **opt-in, reader default 0** (`max_planner_replan_attempts`) so purely additive; **excludes `model_provider_planner_not_chart_spec_ready`** by design (always a legitimate clarify/cannot_resolve). Tests 5/5. **Fixed the harness gap** (Colin's ask): `e2e_pipeline_harness.py` now preserves streamed selection/planning reasoning → `<id>_reasoning.txt` + manifest. **Accepted ADR-0035**; ARCHITECTURE spine + decisions README synced. **Verify:** suite **451 passed / 4 skipped** (+5 re-plan tests); BDD-evidence review OK (Scenario E + live proof flagged pending); inline invariant review OK (re-plan reuses existing gates, re-sends the already-projected request, no schema/sandbox/service/data-boundary change, default-off; arch subagent not spawned — bounded change on the accepted planning path, available on request). Integration change is default-off; **version 0.2.25**. NEW open-queue (v)/(w)/(x)/(y)/(z) + (s) likely-fixed (see queue). Fable-recommended packets flagged (see [[isolinear-model-choice-by-packet]]). Judged report gitignored at `evals/e2e_runs/20260706T205049Z/REPORT.md`.

- **2026-07-06 (17th session)** — `Closed open-queue (q): the analysis layer fires live (ADR-0034 conduit, 0.2.23) + fixed the quality bugs it exposed (0.2.24) + architecture-tracking reset` — **The headline gap is closed.** ADR-0034 (accepted, pushed): **the user's request reaches the codegen model.** Design-first diagnosis (Fable) found the gap was STRUCTURAL, not model capability — the codegen payload never carried the prompt (task = "render the ChartSpec"; the answer rule keyed on a prompt the model never saw), the 0.2.19 grounding rule hard-instructed raw-line plotting, and the planner was told analysis is unsatisfiable (live: gemma refused the heatmap as "not … using the available chart types"). Probe `evals/analysis_intent_probe.py` (production codegen path, execution-truth judging): **baseline 0/12 vs intent 12/12.** Impl (0.2.23): `generate_chart_code`/`repair_chart_code` take a bounded `user_request` (generation-time arg, NEVER crosses to the worker — test-asserted); task reframed to "fulfill user_request"; plot rule → default-with-compute-exception; answer rule keys on `user_request`; planner rule declares analysis prompts satisfiable (plan raw inputs, generated code computes). **Live e2e re-run (0.2.23, 18 prompts): the analysis layer FIRES** — answers compute (e2e-06 "70.84°F", e2e-09 door duration, e2e-08 humidity delta), transforms plot (e2e-11 cross-sensor mean, e2e-17 real rolling mean), e2e-09 binary door went empty-line→correct step track + duration. **Firing exposed a 2nd tier of codegen-quality bugs the silence masked** (accept≠quality — the harness's whole point), fixed same session (0.2.24, both Fable): (1) **irregular-series alignment** — cross-series math on disjoint per-entity timestamps gave a union-index mean spiking above both inputs (e2e-11), an empty "nan °F" delta (e2e-12), "no common timestamps" correlation (e2e-13 = 8th-session pearson_r gap, live). The rules had D9 epoch-ms but never the benchmark's "resample/align before combining" lesson. `evals/alignment_rule_gate.py` reproduced all three (0/6) and gated the fix: prose ordering only reached 2/6 (gemma dropna'd the raw union frame → all-NaN), a LITERAL per-entity idiom (`Series(...).resample('5min').mean().interpolate()`, combine after) hit **9/9 vs 0/6** — the ADR-0033 axvspan lesson generalized. (2) **e2e-18 invalid_model_provider_chart_spec** — planner variance tail: a sample plans the computed result ("Deviation") as its own series → constrained decoding forces it onto an already-used entity_id → duplicate-source rejection (0.1.37 relabel-reuse, new door); the satisfiability rule now forbids planning the computed result as a series → re-check 7/7 ready+valid. **Verify:** suite **446/4** (+conduit disclosure/bounding/absent, plot-default-with-exception, answer-keying, repair-carries-request, boundary-no-leak, orchestration threading, alignment idiom pin, planner satisfiability+no-extra-series pin); evals `codegen_generation_path` + `model_authored_analysis` PASS; probe 12/12, alignment gate 9/9 vs 0/6, planner re-check 7/7. Integration-only, no worker/frontend rebuild. **Also: architecture-tracking reset** (Colin: "I can't track 34 ADRs") — wrote `docs/ARCHITECTURE.md` (the current-state map: spine + 12 load-bearing decisions + weight-honest component table + demolition targets; CLAUDE.md doc-map points at it, syncs at /closeout), archived superseded ADR-0004, drafted **ADR-0035** (v0.3 north star: saved re-runnable analysis code, model-free refresh + the sequenced demolition plan). **Deploy state: 0.2.23 + 0.2.24 both PUSHED; HA updated to 0.2.23 for the live run (needs a 0.2.24 redownload to deploy the alignment/planner fixes). ADR-0035 is DRAFT awaiting Colin.** Evidence: `evals/e2e_runs/20260706T172905Z/REPORT.md` (judged 8 PASS/5 PARTIAL/5 FAIL), `evals/prompts/analysis_intent_probe_findings.md`, `evals/prompts/alignment_rule_gate_findings.md`. **Next: deploy 0.2.24 + re-run the harness (expect e2e-11/12/13/18 to flip); then open-queue (r)/(m)/(t)/(s) + the new re-plan-on-validation-failure item.**

- **2026-07-06 (16th session)** — `D + E from the open queue: retire the bare-° rule (eval-gated, 0.2.22) + build the Claude-judged live e2e harness — which found that the model-authored analysis layer doesn't fire live` — Colin picked open-queue (o) and (p). **(D) Retired the bare-non-ASCII prompt rule.** The old `evals/codegen_reliability.py` couldn't answer whether the rule still earns its place (it mirrors stale packet-5 rules + ASCII `degF` units — the ° class can't fire), so I built `evals/codegen_rule_gate.py`: it drives the PRODUCTION codegen path (real `generate_chart_code`/`repair_chart_code`, the real `_CODEGEN_PROMPT_RULES` + `_codegen_request_view` projection) with production-shaped °F/%-unit `ts_epoch_ms` data + ADR-0033 `derived_intervals`, 6 cases × with/without the rule × 3 runs, against live gemma4:e4b + a live worker sandbox. **36 runs, ZERO bare-non-ASCII incidents in either arm (both 18/18 accepted);** the only multi-attempt runs were `runtime_error` (a different class, all repaired). The 0.2.17 unit-grounding rule keeps ° out of bare literals structurally + 0.2.14 `source_line` recovers the class if it recurs, so the rule gates nothing — dropped from `_CODEGEN_PROMPT_RULES`; findings + results committed as evidence. Integration-only, 0.2.22, ships via HACS. **(E) Built the Claude-in-the-loop live e2e harness** `evals/e2e_pipeline_harness.py` — drives the REAL card path (`isolinear/v1/job/start` + snapshot polling over the HA WS API, the same commands the card sends) for a fixed prompt set against live HA + worker + gemma, captures the served PNG (from `chart.image_url`) + structured metadata (render_path, fallback_reason, answer_text, answer_verification, failure codes, phase timings) into gitignored `evals/e2e_runs/<ts>/` with a REPORT.md scaffold; **no programmatic assertions — Claude reads the PNGs + manifest and judges by looking** (Colin's scope). **Its FIRST run (vs live 0.2.20) immediately caught two unknown bugs synthetic checks miss:** (1) a generated non-string `render_metadata.warnings` entry made the worker's OWN response validation raise → HTTP 500 → the integration treated it as an unrepairable transport fault → Pillow fallback with ZERO repairs (same trap for model-stringified claim values, measured in the 8th-session benchmark). Fixed WORKER-side: `_normalize_render_metadata` coerces every model field to its contract type + `_coerce_claims` sanitizes/drops malformed claims (a dropped claim → unverified caveat, never a fabricated value) + a residual leak degrades to a structured repairable `invalid_render_metadata` instead of a 500. Also allowlisted `matplotlib.patches`/`lines`/`ticker`/`colors` (the ADR-0033 "e.g. a Patch" legend hint burned repair attempts on `import_not_allowlisted`). (2) the >2-day state-overlay tiering wall (see below). **Then Colin asked to expand the prompt set** (humidity/%, state timeline, renderable short-window overlay, transforms, correlation, heatmap, histogram, smoothing → 18 prompts) and authorized deploying the worker fix to the CT103 `:dev` compose service + a full live run. Worker rebuilt + force-recreated (healthy, fix verified in-container). **Second run (18 prompts, worker fix live, HA still 0.2.20): 8 PASS / 2 PARTIAL / 8 FAIL, ZERO Pillow fallbacks (worker fix held; e2e-01 flipped Pillow→codegen).** **HEADLINE FINDING: the model-authored ANALYSIS layer does NOT fire on the live floor model.** Every transform/correlation/question prompt — average (e2e-11), delta "how much warmer" (e2e-12), correlation (e2e-13), deviation-from-mean (e2e-18), rolling average (e2e-17, partial), and the answer_text question (e2e-06) — collapsed to plotting the RAW input series with an analysis-flavored TITLE and an EMPTY `answer_text`/claims; the model computed nothing. Two more (cross-metric temp/humidity correlation e2e-14, heatmap e2e-15) failed at the PLANNER (`model_provider_planner_not_chart_spec_ready`). This is the gap between the stated "data-analysis assistant" identity and live behavior — the ADR-0031 tranche-1 answer/transforms capability was only ever proven by hand-fed eval prompts, and end-to-end through the real planner it doesn't happen. **WIN: ADR-0033 overlay bands proven live end-to-end at short window (e2e-10)** — kitchen °F line + shaded cooling bands via `axvspan`, no state line, on the real card→planner→overlay→codegen path (the exact 0.2.21 fix). **Secondary render bugs:** binary/timeline entity renders EMPTY through codegen (e2e-09 — `binary_sensor.kitchen_door` drawn as an empty numeric line with a degenerate multi-year x-axis; codegen has no timeline handling, invariant-#9 gap); histogram misplaces the unit (e2e-16 — °F on the density y-axis, "Value" x-axis). Cosmetics reconfirmed: axis word still "Value" not the quantity; two-humidity kitchen series mislabeled just "Humidity". **Verify:** suite **437 passed / 4 skipped** (+3 worker coercion tests); worker evals `codegen_sandbox` + `worker_http_server` PASS; integration evals `codegen_generation_path` + `model_authored_analysis` PASS. Specs updated (`worker-http-server` 500-hardening, `answer-grounding-check` claims-coercion deviation, `model-authored-analysis` submodule allowlist). New open-queue (q)/(r)/(s)/(t). Reports: `evals/e2e_runs/20260706T035420Z/REPORT.md` (judged), `evals/prompts/rule_gate_findings.md`. **Deploy state:** `main` 0.2.22 COMMIT-ONLY (not pushed); the CT103 `:dev` worker carries the metadata fix live (worker-side, no version bump); HA still runs 0.2.20. **Next: open-queue (q) — make the analysis layer actually fire live (design first).**

- **2026-07-05 (15th session)** — `Fixed the 0.2.18 empty-chart / wrong-unit regression: bounded real-points preview grounds the floor model + deterministic catalog unit (0.2.18→0.2.19)` — **Colin retested 0.2.18 and got charts that rendered COMPLETE but with NO data plotted and wrong axes** (kitchen+basement weekend chart: empty, y-axis "Temperature (°C)" on °F sensors; kitchen last-3-days: empty, y-axis "Value"). **Reproduced live end to end** (real planner → real HA history via the HA API → live gemma, EXECUTING each generation in a venv to measure ground truth): NOT overflow (real prompts ~1.8–3.2K tok, well under `num_ctx`). **Root cause: 0.2.18's pure per-series SUMMARY removed the concrete data that anchored the floor model's code.** THREE interacting failures: **(1)** the summary renamed the point list to `sample_points`, a key ABSENT at runtime (runtime data uses `points`) — the prompt was self-contradictory (JSON showed `sample_points`, rule text said `points`); caught gemma live writing `history_series_data['sample_points']` → KeyError/empty. **(2)** with only a summary, gemma drove plotting/labeling off the `chart_spec` (5/6 real runs) — which carries a planner-HALLUCINATED unit (the planner emitted `°C` on °F sensors) and series keyed by `source.entity_id` with NO top-level `entity_id` → entity-match fails → EMPTY plot + wrong/generic unit. **(3)** the `PlannerResult` schema REQUIRES a `unit` the planner is never given → it guesses. **Fix (Colin's steer: bounded real points, count chosen by experiment; + fix the planner too).** `_history_series_prompt_view` now carries a bounded, evenly-downsampled PREVIEW of REAL points under the SAME runtime key `points` (+ `points_truncated`; first+last kept) via `_downsample_preview`, `_CODEGEN_PROMPT_PREVIEW_POINTS=12`. **Live grounding experiment (execution-truth, real chart_spec+history): summary=1/3 grounded (2/3 EMPTY); 6 pts=6/6; 10=3/3; 12=6/6; 40=6/6 but 6.2K tok — picked 12 for margin at ~3.2K/2-series.** Prompt rules now make `history_series` the sole data authority (plot by iterating it directly; **chart_spec is intent-only** — never read data/units/series-list from it). Planner unit fixed deterministically: `_apply_catalog_units` (job_orchestration.py, after chart_spec validation) overwrites each series' `unit` from the authoritative catalog `unit_of_measurement` keyed by `source.entity_id` (°C→°F confirmed live). **Verify: on the ACTUAL fixed code, 5/5 live runs plot the full data (was 2/3 empty), 4/5 clean °F; the 1/5 was an unrelated gemma runtime bug (`set.pop` on empty) that STILL plotted the data → routes through the repair loop / surfaced Pillow fallback, NOT the empty-chart symptom (reinforces open-queue (m), now more urgent).** Suite **427 passed / 4 skipped** (+6: preview shape under the runtime key, short-series-not-truncated, `_downsample_preview` span/bound, chart_spec-intent prompt rule, `_apply_catalog_units` overwrite/unknown/aggregate); evals `codegen_generation_path` + `model_authored_analysis` PASS; spec `model-authored-analysis` updated (prompt view = grounded preview; authoritative series unit). Inline invariant review OK (prompt-only projection + a deterministic post-plan step; no schema/sandbox/service/boundary change — the preview is bounded and strictly less than 0.2.17's full-points prompt, raw ISO `ts` still stripped per D9; the unit comes from the allowlisted catalog); arch subagent not spawned (bounded change on the accepted codegen path), available on request. Integration-only, NO worker/frontend rebuild. **FOLLOW-ON (0.2.20, same session): the first successful 0.2.19 render plotted real data but the y-axis read "Value ()" (empty unit). Reproduced live: the model reads the unit CORRECTLY from `history_series[i]['unit']` (6/6 runs) and renders it verbatim — an empty label means the DATA's unit is empty. Root cause: the catalog snapshots `unit_of_measurement` at build time, but cloud entities (ecobee) are commonly `unavailable` then (no unit attr) → catalog cached `null`; `history_series.unit` and `_apply_catalog_units` both empty. Fix: `_approved_catalog_items` (both copies) backfills a missing unit from the entity's LIVE state via `backfill_catalog_units_from_state` (new, in `history_retrieval`), never overriding a present unit. Verified live: real state None→°F backfill, then 4/4 gens render "(°F)". Suite 430/4 (+3: backfill missing/present/no-state). Cosmetic residue: the axis WORD is still sometimes generic "Value" — optional follow-up to surface device_class for "Temperature". **FOLLOW-ON (0.2.21, ADR-0033): overlay renders wrong on 0.2.20 — Colin's "temps + when the AC was running" plotted the climate state ("cool", the constant mode) as a LINE on the temperature axis instead of shaded bands.** (Note: 0.2.20 DID fix the earlier overlay `unsafe_code` fallback — the code is now safe but renders wrong = accept≠quality, invisible to the static check; validates open-queue (p).) The data was all there (points carry `attrs.hvac_action`; chart_spec.overlays has color_map + `render_as: shaded_intervals`), but my 0.2.19 "plot every series as a line" rule pushed the model to draw the state series. **Colin's steer: integration precomputes the bands (Option B), leave room to back out.** `_compute_overlay_bands` (job_orchestration) reuses the Pillow renderer's attribute-aware `_binary_on_regions`/`_categorical_overlay_states` to compute shaded bands `{start_ms,end_ms,color,label}` from `hvac_action` (cooling→blue/heating→orange), populated into the existing `derived_intervals` (schema already open — no change). Prompt rules revised: plot ONLY `kind=='numeric'` series as lines (never state series); draw each `derived_intervals` band as `ax.axvspan`. **Live-verified 5/5: 2 numeric lines + real cooling bands via axvspan, NO state line, no error.** ADR-0033 accepted (isolated + revertible). Suite 434/4 (+4); evals PASS. Version 0.2.21. Next: Colin HACS-redownloads 0.2.21.**


_(older sessions — 14th session fixed the codegen context-window overflow (per-series summary prompt, 0.2.18); 13th session landed the FIRST live codegen chart end-to-end + polish (0.2.14→0.2.17); 11th session fixed open-queue (n): prose-before-fence codegen replies became `syntax_error@L1` → Pillow fallback; new `_extract_python_code` pulls the fenced block regardless of surrounding prose (0.2.11→0.2.12); 10th session shipped to `main` + live bring-up: merged the branch (caught a stale PR #3 half-ship), then fixed three live bugs — editable endpoints (0.2.9), repair blind to `unsafe_code` (0.2.10), failure logging (0.2.11); grounding-check proof req #4 floor-model claim-emission rate (8th session, 0.2.5→0.2.6, `079431d`/`e1c6ef7`); ADR-0031 D8a packet 4 answer-grounding check + 4d event anchors (6th/7th sessions, 0.2.3→0.2.5); ADR-0031 drafted + hardened by a real-data benchmark (`c9d6ad3`→`ac71de8`, 4th session, 0.2.1); ADR-0030 implemented in code: pandas/1024MB/repair-everything/codegen-primary + Pillow fallback (`4532ba5`/`a038b9b`/`940887b`, 3rd session, 0.2.1), ADR-0029 KEEP decision + ADR-0030 + the great scaffold purge (`f8f7760`/`255b0c3`, 2nd session), ADR-0029 packet 5 codegen reliability eval (`9320cf0`), packet 3 worker PROVEN LIVE on CT103 + OpenBLAS `RLIMIT_AS` fix (`2bb2747`), packet 4/0.1.49 (`b22992b`), packet 3 Dockerfile (`6321215`) + packets 1–2, ADR-0028/0.1.48, ADR-0027/0.1.47, ADR-0023/0.1.44, ADR-0026/0.1.43 and earlier — live in git history)_
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Open-queue (u) — bounded re-plan on validation failure` — ANCHOR LANDED (2026-07-06, 18th session, 0.2.25)

- [x] Spec `docs/specs/planner-replan-on-validation-failure.md` + BDD `bdd/integration/planner-replan-on-validation-failure-bdd.md` + evidence (draft; ADR-vs-spec flagged for Colin)
- [x] `_configured_max_planner_replan_attempts` reader (default 0, opt-in) + `_PLANNER_REPLAN_TRIGGER_CODES` = {`invalid_model_provider_chart_spec`, `invalid_planner_result`}
- [x] `_record_model_provider_plan` wraps `_plan_once` in the bounded loop; result carries `planner_replan_attempts`; excludes `model_provider_planner_not_chart_spec_ready` (legitimate clarify/cannot_resolve — validated by e2e-14)
- [x] `tests/test_planner_replan_on_validation_failure.py` — 5/5 (recover, exhaustion-unchanged, clarify-never-replanned, zero-attempts-revert, default-off); suite 451/4
- [ ] Config surface: `config_schema.py` field + default + `config_flow.py` integer field + coercion
- [ ] Flip reader default 0→1 (bundle with (m); update the failure-path call-count assertions to the exhaustion count)
- [ ] Scenario-E test (mixed-routing pre-planner rejection not re-planned)
- [ ] Live proof: e2e-18 duplicate-source variance tail recovers via re-plan against live gemma (spec Proof req #4)

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
- [x] **Colin: enter `worker_endpoint_url`=http://10.0.1.39:8080 + paste the SOPS token** in HA options — DONE (13th session): the endpoint + token are configured and a real chart rendered end to end through the live worker

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
  **MORE URGENT after the 15th session:** 0.2.19 restores grounding, but the live
  verify still showed ~1/5 generations hitting a repairable RUNTIME code bug
  (e.g. `set.pop` on empty) — with `attempts=1` that one-shots straight to the
  Pillow fallback instead of getting a repair pass. Raising to 2 would recover
  most of these. (Colin was offered this in the 15th session; not taken in that
  packet — do as a bounded follow-up.)
- (n) ~~**NEW BUG (Colin, 2026-07-04 live testing).**~~ **RESOLVED (0.2.12,
  11th session).** Two symptoms: (1) *"Custom element doesn't exist:
  isolinear-card"* — a **stale browser cache**, not a code bug (backend verified
  healthy live: resource registered, JS serves 200 byte-identical, element
  registers); a hard reload fixed it. (2) *codegen always fell back to Pillow
  with `unsafe_code`* — the real bug: model replies with prose before the
  ` ``` ` fence were mangled by `_strip_markdown_json` into `syntax_error@L1`.
  Fixed with `_extract_python_code` (pulls the fenced block regardless of
  surrounding prose). Pending only Colin's 0.2.12 redownload + retest.
  **Follow-on (12th session): the redownloaded 0.2.12 surfaced a SECOND syntax
  fallback — `syntax_error@L19` from a bare `°` token** — fixed in 0.2.13/0.2.14
  (generation rule + generic `source_line` on violations). **Worker rebuilt +
  force-recreated on CT103 (source_line now live).** **FULLY CLOSED (13th session):
  three more live-found bugs fixed (0.2.15 fence instruction, homelab tmpfs uid/gid,
  0.2.16 image_bytes_base64) and the full chain rendered a real chart end to end.**
- (o) **Eval-gate the generation-side bare-non-ASCII rule for retirement.** The
  `_CODEGEN_PROMPT_RULES` "labels must be string literals; no bare `°`/`%`" rule
  (0.2.13) is failure-driven; the 0.2.14 `source_line`-assisted repair is the
  generic mechanism. Once the worker carries `source_line` live, run the
  reliability corpus (`evals/codegen_reliability.py`) with and without the rule:
  if repair recovers the class on its own, drop the rule to keep the prompt lean
  (small floor models degrade on long rule lists). Proposed division: contract
  rules stay in the prompt; failure-driven style hints must earn accept-rate.
  **Update (13th session): the rule is now DOUBLY redundant — the 0.2.17
  unit-from-data grounding rule tells the model to read `°` from
  `history_series[i]['unit']` (a str variable), so the degree symbol never lands
  as a bare literal in the first place. Strong candidate to drop; eval-gate first.**
- (p) **End-to-end pipeline harness with Claude-in-the-loop as the oracle (Colin,
  15th session).** **Motivation:** recent sessions hit render regressions that
  synthetic backend simulations MISS — 0.2.18 empty charts, 0.2.19/0.2.20
  wrong/missing units, the overlay `unsafe_code` fallback (14th–15th). Diagnosing
  by hand-building a codegen request diverges from the real `card → job/start →
  planner → _compose_state_overlays → history retrieval → codegen → worker sandbox
  → served artifact → card` path, so failures get mis-attributed to "gemma
  variance" and real regressions ship. **Colin's scope (2026-07-05): NOT a fully
  assertable CI suite — just close the loop back to Claude, who judges pass/fail by
  looking.** Build a harness that, for a fixed prompt set, drives the REAL pipeline
  (the WS API is the lightest faithful entry — `job/start` + snapshot polling, the
  same commands the card sends — no synthetic request) against the live HA + worker
  + pinned Ollama (gemma4:e4b), then captures the REAL output per prompt: the
  served **PNG** (already available as `image_bytes_base64` / the artifact endpoint,
  saved to disk) plus the structured metadata (`render_path`,
  `render_fallback_reason`, `answer_text`, `answer_verification`, and on a fallback
  the generated code + sandbox violations). **Claude then READS the PNGs + metadata
  and judges each pass/fail** (empty plot? wrong/missing unit? Pillow fallback?
  right shape?) — no programmatic pixel/OCR assertions needed for v1; Claude's
  vision is the oracle. Prompt set must include the cases that regressed:
  single-series, two-series numeric, numeric+state OVERLAY, long-window (statistics
  tier). **Readily buildable now** (WS-API driver + PNG capture); could later
  harden the recurring judgments into hard assertions, and/or add richer
  `render_chart` metadata (`series_plotted` count, `unit_used`) — overlaps packet 6
  visual validator. Env: run against Colin's live instance with the fixed prompt
  set, or a dedicated test HA. **BUILT + PROVEN (16th session):**
  `evals/e2e_pipeline_harness.py` (18-prompt set in `evals/prompts/e2e_prompts.json`);
  two live runs judged, found the worker-500 + analysis-layer-silent + timeline
  bugs below. This item is DONE; the harness is now a standing tool. Future
  hardening (hard assertions, `series_plotted`/`unit_used` metadata) stays open.

- (q) ~~**HEADLINE (16th session): the model-authored ANALYSIS layer does not fire
  on the live floor model.**~~ **RESOLVED (17th session, ADR-0034, 0.2.23→0.2.24).**
  Root cause was STRUCTURAL, not model capability: the codegen payload never
  carried the user's request (its task was "render the ChartSpec"; the answer rule
  keyed on a prompt the model never saw), the 0.2.19 grounding rule hard-instructed
  raw-line plotting, and the planner was told analysis is unsatisfiable. ADR-0034
  (accepted): `user_request` reaches the codegen model (generation-time only, never
  crosses to the worker); task reframed; plot rule = default-with-compute-exception;
  answer rule keys on `user_request`; planner rule declares analysis satisfiable.
  Probe `evals/analysis_intent_probe.py` proved it (baseline 0/12 vs intent 12/12);
  the live e2e re-run (0.2.23) showed the layer FIRE (answers compute, transforms
  plot). Firing exposed two follow-up bugs, both fixed 0.2.24: irregular-series
  alignment (`evals/alignment_rule_gate.py`, 9/9 vs 0/6) and the e2e-18 planner
  duplicate-source tail. **Remaining: deploy 0.2.24 + a confirming e2e re-run
  (packet A); the planner variance tails → open-queue (u); a code-specialized
  codegen model is no longer needed (gemma4:e4b computes fine with the conduit).**

- (u) **ANCHOR LANDED (18th session): bounded re-plan-on-validation-failure.**
  Spec + BDD + evidence + implementation shipped (0.2.25): `_record_model_provider_plan`
  wraps `_plan_once` in a bounded re-plan loop over `_PLANNER_REPLAN_TRIGGER_CODES`
  = {`invalid_model_provider_chart_spec` (e2e-18's class), `invalid_planner_result`},
  reusing the existing gates + planner client; carries `planner_replan_attempts`.
  **Opt-in, reader default 0** (`max_planner_replan_attempts`) — purely additive.
  Slice-1 is a plain re-sample (no corrective prompt). **Scope corrected this session:**
  it deliberately does NOT re-plan `model_provider_planner_not_chart_spec_ready`
  (post-schema-validation that always means a legitimate `clarification_needed`/
  `cannot_resolve`) — so it does NOT close e2e-14, which the repro proved is an
  entity-resolution gap, not a planner variance tail (see (v)). **Remaining to
  finish (u):** config surface (config_schema + config_flow field + coercion),
  flip default 0→1 (bundle with (m); update failure-path call-count tests),
  Scenario-E (mixed-routing) test, and the live e2e-18 duplicate-source recovery
  proof. Spec: `docs/specs/planner-replan-on-validation-failure.md` (ADR-vs-spec
  decision flagged for Colin). Corrective re-plan (feed the error back) = tranche 2.

- (v) **NEW (18th): e2e-14 entity-resolution gap — "kitchen humidity" not disclosed.**
  Root-caused via `scripts/repro_e2e14.py`: the cross-metric correlation fails at
  the planner ONLY because entity resolution discloses the temp sensor alone; the
  planner correctly clarifies that `sensor.kitchen_ecobee_humidity` is required
  (friendly name "Kitchen ecobee Humidity" — the prompt's "kitchen humidity" misses
  the "ecobee" token; "kitchen" also noise-matches 3 temp sensors). Disclose both →
  the planner plans + renders the °F-vs-% correlation fine. Fix is in the
  entity-resolution/composition layer (multi-numeric cross-metric disclosure), not
  the planner. Opus-executable (root cause known). Check the D1/D2 + composition
  path for why the second numeric metric isn't added.

- (w) ~~**NEW (18th): e2e-15 heatmap emits GARBAGE codegen.**~~ **DONE (19th
  session, 0.2.26) — "ship simple".** Root cause (repros `scripts/repro_e2e15*`):
  the single-numeric envelope has no heatmap family, the planner routes the ask
  to `histogram` (6/6), then the ADR-0034 conduit's "heatmap" `user_request`
  collides with the histogram spec inside codegen → the garbage. Colin chose the
  histogram-degrade over a real temporal heatmap (keeps "heatmap" reserved for
  the future spatial/floorplan renderer, open-queue (c)). Fixed with ONE
  `_CODEGEN_PROMPT_RULES` family-degrade sentence (render only line/histogram/bar;
  never a 2-D grid; a single-sensor heatmap ask → histogram of its values;
  `user_request` changes the COMPUTATION, never the family — reinforces invariant
  #9). Gated 3/3 vs 0/3 (`evals/heatmap_rule_gate.py`); regression test
  `FamilyDegradePromptRuleTests`; spec `model-authored-analysis` §2. Findings:
  `evals/prompts/heatmap_diagnosis_findings.md`.

- (aa) **NEW (19th): latent codegen stray-quote guard-branch emission.** While
  diagnosing (w), 2/3 counterfactual runs emitted a dead-code "data not found"
  guard containing `transform=ax.transAxes')` (stray quote → `syntax_error`),
  re-emitted every repair attempt (temp-0 regenerates its own bug — more repair
  budget won't help). Not heatmap-specific; could surface on other prompts. Worth
  a prompt nudge against the guard-branch preamble, or a targeted repair hint.

- (bb) **NEW (19th): multi-sensor "heatmap of correlations" degrades to lines.**
  A multi-entity heatmap ask routes through the `time_series` envelope, so the (w)
  family-degrade rule sends it to multi-line series, not a histogram — coherent
  but a weak substitute. Acceptable by the coherent-degrade bar; revisit only if
  correlation-matrix asks become common (then a named family, per the (w)
  decision).

- (x) **NEW (18th): e2e-09 door answer_text has zero-duration intervals.** The
  door step track now renders (good), but the generated answer lists malformed
  open periods ("14:17 to 14:17", "20:05 to 20:05") — a duration-computation bug
  in the codegen answer path (and no legend maps the red/blue bands to open/closed).

- (y) **NEW (18th): e2e-03 two-line chart missing legend.** "Kitchen and basement
  temperatures over the weekend" drew two °F lines with no legend to distinguish
  them (e2e-08's two-humidity chart DOES emit one — inconsistent). A codegen prompt
  nudge to always legend multi-series charts.

- (z) **NEW (18th): e2e-11 "average of X and Y" plots a scalar line, not a mean
  series.** The 0.2.24 alignment artifact is gone, but the model draws a horizontal
  scalar-average reference line + the two raw lines instead of a computed
  time-varying cross-sensor mean series (and no answer_text). Transform-intent gap.
  **FABLE-shaped diagnosis** (why the model reaches for a reference line).

- (r) **Binary/timeline entity renders EMPTY through codegen (16th session,
  e2e-09).** "When was the kitchen door open today?" routed `binary_sensor.
  kitchen_door` down the codegen path and drew an empty numeric line with a
  degenerate multi-year x-axis (2024→2028) and a 0.96–1.04 "State" y-axis — no
  step track, no events. Invariant #9 says binary/categorical entities render as
  raw-states step tracks (timeline family); codegen has no timeline handling, so
  a state entity that reaches it produces nothing usable. Fix options: route the
  timeline family to the Pillow step renderer (bypass codegen for pure-state
  charts), OR teach the codegen prompt to draw a step track from string states +
  fix the degenerate axis when a series has ~no points in-window. Check how the
  render-family route (which is supposed to pick timeline before planning) let a
  binary entity reach the numeric codegen path.

- (s) **Histogram unit — LIKELY FIXED (confirm before closing).** The 16th-session
  bug put °F on the density y-axis and "Value" on the x. The 18th-session live run
  (e2e-16) rendered a CORRECT histogram: x-axis "Temperature (°F)", y-axis
  "Frequency (Count)". Re-confirm across a couple of runs (it may be model variance)
  before closing. Residual: the axis WORD cosmetic (device_class → "Temperature")
  still applies where the model picks "Value".

- (t) **The >2-day state-overlay tiering wall (16th session, e2e-04).** A
  numeric+state OVERLAY prompt spanning more than 2 days fails at
  `approved_history_retrieval` with `no_long_term_statistics` before any render:
  `RAW_TIER_MAX_SPAN=2d` (history_retrieval) + ADR-0021 single-source-per-window
  routes EVERY series (including the state entity) to the long-term-statistics
  tier, which a state entity lacks. So the ADR-0033 overlay only works inside the
  2-day raw tier (proven: e2e-10 short-window PASSED, e2e-04 five-day FAILED).
  Design fix: per-KIND tiering (numeric series from statistics, state overlays
  from recorder raw states inside retention within the same window), or cap the
  overlay to the raw-retention sub-window. Needs a small ADR (touches the
  single-source-per-window invariant from ADR-0021).

## Blockers

- None.
