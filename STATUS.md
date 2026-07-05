# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-07-05, fifteenth session (**Fixed the 0.2.18 empty-chart / wrong-unit regression Colin hit on `main` (basement-only + kitchen/basement weekend charts rendered COMPLETE but with NO data plotted and °C/"Value" axes on °F sensors). Reproduced live end to end (real planner → real HA history → live gemma, executing each generation) — NOT overflow (real prompts ~1.8–3.2K tok). Root cause: 0.2.18's pure per-series SUMMARY removed the concrete data that anchored the floor model's code. THREE interacting failures: (1) the summary renamed the point list to `sample_points` (absent at runtime — runtime uses `points`); caught gemma writing `series['sample_points']` → KeyError/empty. (2) With only a summary, gemma drove plotting/labels off the `chart_spec` (5/6 real runs) — which carries a planner-HALLUCINATED unit (`°C` on °F sensors) and `source.entity_id` (no top-level `entity_id`) → empty plots + wrong units. (3) The `PlannerResult` schema REQUIRES a `unit` the planner is never given → it guesses. **The fix (Colin's steer — bounded real points, count chosen by experiment; + fix the planner too):** `_history_series_prompt_view` now carries a bounded, evenly-downsampled PREVIEW of REAL points under the SAME runtime key `points` (+`points_truncated`), first+last kept (`_downsample_preview`, `_CODEGEN_PROMPT_PREVIEW_POINTS=12`). Live grounding experiment (execution-truth): summary=1/3 grounded (2/3 EMPTY); ≥6 pts = solid; picked 12 for margin (~+950 tok, 2 series → 3.2K). Prompt rules now make `history_series` the sole data authority (plot by iterating it directly; **chart_spec is intent-only** — never read data/units/series-list from it). Planner unit fixed deterministically: `_apply_catalog_units` overwrites each series' `unit` from the catalog `unit_of_measurement` after planning (°C→°F confirmed live). **Verified live on the fixed code: 5/5 runs plot the full data (was 2/3 empty), 4/5 clean °F; the 1/5 was an unrelated gemma runtime bug that STILL plotted the data → repair loop / surfaced Pillow fallback (reinforces open-queue (m)).** Suite 427 passed / 4 skipped (+6); evals `codegen_generation_path` + `model_authored_analysis` PASS; spec `model-authored-analysis` updated. Integration-only, NO worker/frontend rebuild. Version 0.2.19.**) **FOLLOW-ON 0.2.20 (same session): fixed the "Value ()" empty-axis Colin saw on the FIRST successful 0.2.19 render** — 0.2.19 restored data plotting (real kitchen+basement lines) but the y-axis read "Value ()" (empty unit). Reproduced live: the model reads the unit CORRECTLY from `history_series[i]['unit']` (6/6 runs) and renders it verbatim, so an empty label means the DATA's unit is empty. Root cause: the catalog snapshots `unit_of_measurement` at BUILD time, but cloud entities (ecobee) are often `unavailable` then (no unit attr) → the catalog cached `null` even though the live sensor now reports °F; `history_series.unit` (= catalog unit) and `_apply_catalog_units` both came up empty. Fix: `_approved_catalog_items` now backfills a missing unit from the entity's LIVE state (`backfill_catalog_units_from_state`, in `history_retrieval`, applied in BOTH `_approved_catalog_items` copies), never overriding a present catalog unit. Verified live end to end (real live state None→°F backfill, then 4/4 generations render "(°F)"). Suite 430 passed / 4 skipped (+3). NOTE: the axis WORD is still sometimes generic "Value" (vs "Temperature") — cosmetic, "Value (°F)" is informative; optional follow-up to surface device_class.**)

_(prior)_ 2026-07-05, fourteenth session (**Fixed the live `unsafe_code`/`syntax_error` fallbacks on 0.2.17: the codegen PROMPT carried the FULL recorder points → tens of thousands of tokens overflowed Ollama's ~4K default `num_ctx` → system prompt/rules evicted → gemma replied with prose → `syntax_error@L1`. `_history_series_prompt_view` switched to a per-series SUMMARY (metadata + point_count + range + stats + 3 sample_points), the dispatched render request still carries every point; `num_ctx=8192`; runtime overflow safety net (`prompt_eval_count >= num_ctx` → `codegen_context_overflow` fallback + card guidance). Suite 420/4; version 0.2.18. NOTE: the pure summary is what the 15th session had to correct — it removed the model's data grounding.**)

_(prior)_ 2026-07-05, thirteenth session (**🎉 FIRST LIVE CODEGEN CHART RENDERED END TO END — HA → gemma4:e4b → fenced matplotlib → CT103 sandbox → PNG bytes → served card. Three bugs fixed to get there, then polish. (1) `0.2.15` (`ec57839`) fence instruction: the initial gen hit `syntax_error@L11` but every repair degraded to `syntax_error@L1` — gemma replied with prose + UNFENCED code, so `_extract_python_code`'s no-fence fallback returned the raw text (prose = line 1). `_CODEGEN_SYSTEM_PROMPT` said "no markdown OUTSIDE a fence" but never to USE one; now it mandates a python code fence. (2) homelab tmpfs perms (`4e80bbc` on homelab `main`): code then ran but hit `PermissionError` on savefig — the compose tmpfs `/var/lib/isolinear-worker/work` was `root:root` but the worker runs uid 10001; added `uid=10001,gid=10001` (live-fixed on CT103 + committed to the IaC template). (3) `0.2.16` (`9e14b9e`) image bytes: worker reported `status=success` but the integration failed `missing_worker_image_bytes` — the result carried only `image_path` (unreachable from the HA box); the HTTP server now inlines `image_bytes_base64` on success (field already in schema; base64 is stdlib). Worker rebuilt on CT103. THEN it rendered live. (4) `0.2.17` (`0a02b51`) polish, all HACS-only: wrong unit (°C for an °F sensor — model guessed; the real unit was already in the prompt data `history_series[i]['unit']` but no rule used it → grounding rule reads it from data, which also keeps `°` out of a bare literal); tiny fonts (matplotlib defaults scaled down on a phone → legibility rule: figsize ~8×4.5 @ dpi 110, explicit font sizes, `bbox_inches='tight'`); card letterbox (`.result img` `object-fit:contain` in a forced 260px row → `height:auto`, fills width). Suite 415 passed / 4 skipped; frontend 35 passed; evals `codegen_sandbox`/`worker_http_server`/`codegen_generation_path`/`model_authored_analysis` PASS; spec `worker-http-server` corrected (base64 inlining now IMPLEMENTED, was marked deferred). Next: Colin HACS-redownloads 0.2.17 + retests — confirm unit/fonts/fit on the phone.**)

_(prior)_ 2026-07-04, twelfth session (**Second live codegen fallback fixed: `syntax_error@L19` from a bare `°` token. Diagnosed from live logs — worker `docker logs` showed `error=unsafe_code violations=[syntax_error@L19]`, and the HA system-log WARNING carried `invalid character '°' (U+00B0)`. The fence-extraction fix (0.2.12) worked (L1→L19), but the model wrote the degree symbol as a BARE Python token (e.g. `ax.set_ylabel(Temperature °F)` — no quotes), which `ast.parse` rejects; repair re-emitted it because the repair task only described disallowed imports/attrs/calls, not syntax errors. **0.2.13 (`345be4a`):** generation-side `_CODEGEN_PROMPT_RULES` rule (labels must be Python string literals; no bare non-ASCII tokens) + repair-task clarification. **0.2.14 (`458a8b7`) — the generic fix (Colin steered away from per-error prompt instructions):** worker `static_safety_check` now attaches `source_line` — the exact offending text — to EVERY line-numbered violation via `_attach_source_lines` (syntax_error + all unsafe_code); the repair task points at `source_line` generically and the hardcoded `°` example was removed. No schema change (`error.details` is `additionalProperties:true`); `_sandbox_error_view` already deep-copies violations so it flows to the repair prompt unchanged. Insight: the info was never missing (syntax errors have no traceback; the full diagnostic + prior code were already in the prompt) — small models just can't COUNT to line 19 in their own output; handing them the line text is the lever. Suite 414 passed / 4 skipped (+2), evals `codegen_sandbox` + `codegen_generation_path` PASS; spec `codegen-generation-path` updated. **DEPLOY SPLIT:** the generation-side prevention ships via HACS (integration-only); the `source_line` robustness is WORKER-side and needs an image rebuild + `docker compose up -d --force-recreate isolinear-worker` on CT103 to go live. Next: Colin HACS-redownloads 0.2.14 (+ optional worker rebuild) and retests "kitchen temperature".**
**Phase:** `LIVE END TO END — the full codegen chart chain works. 0.2.19 fixed the 0.2.18 empty-chart regression (bounded real-points preview grounds the floor model; chart_spec intent-only; deterministic catalog unit). 0.2.20 fixed the "Value ()" empty-axis Colin saw on the first successful 0.2.19 render (catalog unit was stale/null from an unavailable-at-build cloud entity → backfill the unit from live state). Awaiting Colin's 0.2.20 HACS-redownload + retest.`
**Next bounded packet:** `(A) CONFIRM 0.2.20: Colin HACS-redownloads + retests "kitchen and basement temps over the weekend" etc. — expect REAL data with a correct °F axis (no "()"). THEN: (B) raise the default max_codegen_repair_attempts above 1 (open-queue (m)) — MORE urgent: ~1/5 gens hit a repairable runtime code bug, one-shots to fallback at attempts=1 (Colin's live instance already set to 3); (C) OPTIONAL cosmetic: nudge the axis WORD to the measured quantity (surface device_class → "Temperature (°F)" not "Value (°F)"); (D) EVAL-GATE the generation-side ° rule (open-queue (o)); (E) registry follow-ups (pearson_r alignment; corpus-requested metrics). PARKED: packet 5 (output-modality) + packet 6 (visual validator + progressive UX); anchored-window tranche-2; open-queue (l) refinement + saved cards; split job_orchestration.py.\`
**Current readiness:** `Version 0.2.20 on \`main\` (HACS-tracked), pushed. Codegen render chain LIVE-PROVEN (13th) + grounding restored (15th, 0.2.19) + unit backfill (15th follow-on, 0.2.20). 0.2.19 = bounded real-points preview (\`_CODEGEN_PROMPT_PREVIEW_POINTS=12\`) + chart_spec-intent-only rules + deterministic catalog unit (\`_apply_catalog_units\`); 0.2.20 = \`backfill_catalog_units_from_state\` (live-state unit when the catalog snapshot is null). Integration-only — NO worker/frontend rebuild. Worker on CT103 carries image_bytes_base64 + source_line; tmpfs worker-owned (uid 10001). Homelab \`main\`: tmpfs-perms fix (\`4e80bbc\`) + worker compose service (\`311eac9\`). Endpoints editable in Configure; token via ADR-0032.\`

> **⚠️ Direction (2026-07-02, supersedes the 2026-06-12 banner):** ADR-0030 —
> matplotlib codegen via the sandboxed worker is the PRIMARY render path;
> Pillow is the fallback; the model is empowered to transform data in generated
> code. The 2026-06-12 reality pivot completed: the simulated scaffold is
> deleted (commit `f8f7760`), pytest is the single source of behavioral truth
> (`docs/reality-pivot-review.md` is historical context).

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-07-05 (15th session)** — `Fixed the 0.2.18 empty-chart / wrong-unit regression: bounded real-points preview grounds the floor model + deterministic catalog unit (0.2.18→0.2.19)` — **Colin retested 0.2.18 and got charts that rendered COMPLETE but with NO data plotted and wrong axes** (kitchen+basement weekend chart: empty, y-axis "Temperature (°C)" on °F sensors; kitchen last-3-days: empty, y-axis "Value"). **Reproduced live end to end** (real planner → real HA history via the HA API → live gemma, EXECUTING each generation in a venv to measure ground truth): NOT overflow (real prompts ~1.8–3.2K tok, well under `num_ctx`). **Root cause: 0.2.18's pure per-series SUMMARY removed the concrete data that anchored the floor model's code.** THREE interacting failures: **(1)** the summary renamed the point list to `sample_points`, a key ABSENT at runtime (runtime data uses `points`) — the prompt was self-contradictory (JSON showed `sample_points`, rule text said `points`); caught gemma live writing `history_series_data['sample_points']` → KeyError/empty. **(2)** with only a summary, gemma drove plotting/labeling off the `chart_spec` (5/6 real runs) — which carries a planner-HALLUCINATED unit (the planner emitted `°C` on °F sensors) and series keyed by `source.entity_id` with NO top-level `entity_id` → entity-match fails → EMPTY plot + wrong/generic unit. **(3)** the `PlannerResult` schema REQUIRES a `unit` the planner is never given → it guesses. **Fix (Colin's steer: bounded real points, count chosen by experiment; + fix the planner too).** `_history_series_prompt_view` now carries a bounded, evenly-downsampled PREVIEW of REAL points under the SAME runtime key `points` (+ `points_truncated`; first+last kept) via `_downsample_preview`, `_CODEGEN_PROMPT_PREVIEW_POINTS=12`. **Live grounding experiment (execution-truth, real chart_spec+history): summary=1/3 grounded (2/3 EMPTY); 6 pts=6/6; 10=3/3; 12=6/6; 40=6/6 but 6.2K tok — picked 12 for margin at ~3.2K/2-series.** Prompt rules now make `history_series` the sole data authority (plot by iterating it directly; **chart_spec is intent-only** — never read data/units/series-list from it). Planner unit fixed deterministically: `_apply_catalog_units` (job_orchestration.py, after chart_spec validation) overwrites each series' `unit` from the authoritative catalog `unit_of_measurement` keyed by `source.entity_id` (°C→°F confirmed live). **Verify: on the ACTUAL fixed code, 5/5 live runs plot the full data (was 2/3 empty), 4/5 clean °F; the 1/5 was an unrelated gemma runtime bug (`set.pop` on empty) that STILL plotted the data → routes through the repair loop / surfaced Pillow fallback, NOT the empty-chart symptom (reinforces open-queue (m), now more urgent).** Suite **427 passed / 4 skipped** (+6: preview shape under the runtime key, short-series-not-truncated, `_downsample_preview` span/bound, chart_spec-intent prompt rule, `_apply_catalog_units` overwrite/unknown/aggregate); evals `codegen_generation_path` + `model_authored_analysis` PASS; spec `model-authored-analysis` updated (prompt view = grounded preview; authoritative series unit). Inline invariant review OK (prompt-only projection + a deterministic post-plan step; no schema/sandbox/service/boundary change — the preview is bounded and strictly less than 0.2.17's full-points prompt, raw ISO `ts` still stripped per D9; the unit comes from the allowlisted catalog); arch subagent not spawned (bounded change on the accepted codegen path), available on request. Integration-only, NO worker/frontend rebuild. **FOLLOW-ON (0.2.20, same session): the first successful 0.2.19 render plotted real data but the y-axis read "Value ()" (empty unit). Reproduced live: the model reads the unit CORRECTLY from `history_series[i]['unit']` (6/6 runs) and renders it verbatim — an empty label means the DATA's unit is empty. Root cause: the catalog snapshots `unit_of_measurement` at build time, but cloud entities (ecobee) are commonly `unavailable` then (no unit attr) → catalog cached `null`; `history_series.unit` and `_apply_catalog_units` both empty. Fix: `_approved_catalog_items` (both copies) backfills a missing unit from the entity's LIVE state via `backfill_catalog_units_from_state` (new, in `history_retrieval`), never overriding a present unit. Verified live: real state None→°F backfill, then 4/4 gens render "(°F)". Suite 430/4 (+3: backfill missing/present/no-state). Cosmetic residue: the axis WORD is still sometimes generic "Value" — optional follow-up to surface device_class for "Temperature". Next: Colin HACS-redownloads 0.2.20.**

- **2026-07-05 (14th session)** — `Fixed the live codegen context-window overflow: prompt now carries a per-series summary, not the recorder points (0.2.17→0.2.18)` — **Colin retested 0.2.17 and still got `unsafe_code`/`syntax_error` Pillow fallbacks (basement-only and kitchen+basement charts).** I pulled the live logs myself (root SSH to CT103 `docker logs` + HA `system_log` via `scripts/ha_logs.py`): three failure classes — `syntax_error@L1`, `missing_fixed_entry_point`+`top_level_statement`, and `syntax_error: leading zeros in decimal literal` — with repair failing all 3 attempts each. **Root cause (reproduced EXACTLY offline against live gemma): the codegen PROMPT was carrying the FULL recorder points.** `_history_series_prompt_view` stripped only raw `ts` and kept every point, so a real "last N hours" of two sensors is ~tens of thousands of tokens — far over Ollama's small default `num_ctx` (~4K). Ollama truncates from the FRONT, evicting the system prompt + rules, so gemma (seeing only a tail of numbers) replies with a PROSE analysis of the data → `_extract_python_code` returns prose → `syntax_error@L1`; partial truncation gives the other two variants; repair never recovers because its prompt is even bigger. **The fix (Colin's steer — the model never needs the points in the prompt): the generated `render_chart(data, output_path)` receives the FULL data at RUNTIME in the sandbox (`codegen_sandbox.py:288` `render_chart(_PAYLOAD["data"], …)`), so the prompt only needs the SHAPE.** `_history_series_prompt_view` now emits a per-series SUMMARY — all series metadata + `point_count` + `ts_epoch_ms_range` + `value_stats` (numeric) / `distinct_states` (binary/categorical, capped 50) + 3 `sample_points` showing the point dict keys — and NEVER the full list; the dispatched `render_mode: codegen` render request still carries every point (separate path). Prompt dropped ~50K→~1.7K tokens and gemma renders CLEAN where it failed 4×. **Measured via Ollama's own tokenizer (`prompt_eval_count`): fixed rules overhead ~1,418 tokens; ~242 tokens/series CONSTANT regardless of point count; 6 series × 12 MONTHS = ~2,808 tokens (fits 4096).** Also set `num_ctx=8192` on codegen options as defense-in-depth (large num_ctx alone did NOT save the dense-data case — the summary is the real cure). **Runtime overflow SAFETY NET (Colin asked how to catch it): measured that Ollama caps `prompt_eval_count` at exactly `num_ctx` on truncation, so `prompt_eval_count >= num_ctx` is a definitive signal (`_context_overflow`). Codegen generate/repair results carry a `context_overflow` marker; orchestration SHORT-CIRCUITS the doomed repair loop (no wasted worker/repair calls) and falls back to Pillow with the distinct `codegen_context_overflow` reason. Actionable card guidance + WARNING message: raise the codegen model's num_ctx / OLLAMA_CONTEXT_LENGTH, ask for fewer SERIES, or use a bigger-context model/GPU — explicitly NOT a shorter time range (the prompt is a per-series summary, not the points; Colin caught the contradictory wording).** **Verify:** suite **420 passed / 4 skipped** (+5: prompt-summary + state-summary projection, overflow flagged/not-flagged, orchestration short-circuit asserting zero worker/repair calls); frontend **36 passed** (+1: card shows guidance not the raw code); evals `codegen_generation_path` + `model_authored_analysis` PASS; bundle rebuilt + synced (md5 match). Spec `model-authored-analysis` updated (prompt-view-vs-runtime + runtime overflow detection). Inline invariant review OK (data boundary strictly TIGHTENED — the summary shrinks only the prompt; the worker still gets full points + runs the full static check; no schema/service/ADR change; the overflow path is a surfaced ADR-0030 fallback, never silent); arch subagent not spawned (bounded change on the accepted codegen path), available on request. Integration + frontend only, NO worker rebuild. **Next: Colin HACS-redownloads 0.2.18 and retests basement + kitchen/basement — codegen should render first-attempt.**

- **2026-07-05 (13th session)** — `First live codegen chart rendered end to end + polish (0.2.14→0.2.17)` — **THE MILESTONE: the full codegen chart chain works live.** After 0.2.14, Colin retested and the initial gen hit `syntax_error@L11` but all three repairs degraded to `syntax_error@L1`. **(1) `0.2.15` (`ec57839`) fence instruction:** the `@L1`-on-every-repair signature = `_extract_python_code`'s no-fence fallback returning raw text whose line 1 is prose. The repair model (gemma) replied with explanation + UNFENCED code. Root cause: `_CODEGEN_SYSTEM_PROMPT` said "no markdown OUTSIDE a code fence" but never told the model to USE a fence. Fixed: prompt now mandates wrapping output in a python code fence. Regression test pins the fence instruction. **(2) homelab tmpfs perms (`4e80bbc` on homelab `main`):** fence fixed → code ran → `PermissionError` on `fig.savefig`. The compose tmpfs `/var/lib/isolinear-worker/work` mounts `root:root`, but the worker runs uid 10001 (the Dockerfile chown is overridden by the tmpfs mount). Added `uid=10001,gid=10001` to the tmpfs options — live-fixed on CT103 AND committed to the homelab IaC template (the sandbox correctly blocked my direct prod `sed`/push until Colin authorized both). **(3) `0.2.16` (`9e14b9e`) image bytes:** worker then logged `status=success` but the integration failed `missing_worker_image_bytes` at the serve stage. `invoke_codegen_sandbox` returns `image_path` (a path inside the container) but not the bytes — and the integration on the HA box has NO filesystem access to the worker container. Fixed: the HTTP server reads the PNG and inlines `image_bytes_base64` on success (field already in `render-result.schema.json`; base64 is stdlib — no new dep, no schema change). Worker rebuilt + force-recreated on CT103. **THEN it rendered live** — a real gemma-authored matplotlib "kitchen temperature" chart end to end, displayed in the card. **(4) `0.2.17` (`0a02b51`) polish** — three issues Colin flagged on the first real chart, all HACS-only (prompt rules are integration-side; CSS is in the bundle — no worker rebuild): **wrong unit** (°C on an °F sensor — the model guessed; the real unit was already in the prompt data `history_series[i]['unit']='°F'` but no rule used it → grounding rule reads it from the data and f-strings it in, which also keeps `°` out of a bare code literal, so it can't retrigger the syntax-error class); **tiny fonts** (matplotlib 640×480 defaults scaled down on a phone → legibility rule: figsize ~8×4.5 @ dpi 110, explicit title/label/tick sizes, `bbox_inches='tight'`); **card letterbox** (`.result img` used `object-fit:contain` in a forced 260px-tall row → gray bars around the landscape chart; now `height:auto`, natural aspect ratio, fills width). **Verify:** suite **415 passed / 4 skipped** (+1 fence test, image_bytes assertion added to the worker-http test), frontend **35 passed**, evals `codegen_sandbox`/`worker_http_server`/`codegen_generation_path`/`model_authored_analysis` PASS; bundle rebuilt + synced (md5 match). Spec drift fixed: `worker-http-server` marked base64 inlining "deferred" — corrected to IMPLEMENTED with the live rationale. Inline invariant review OK (no sandbox/allowlist/schema/service change: `image_bytes_base64` is the PNG that was always meant to be served, base64 runs in the server process not the sandbox subprocess; unit comes from allowlisted catalog data; CSS is display-only); arch subagent not spawned (bounded hotfixes + polish on the accepted path), available on request. **Next: Colin HACS-redownloads 0.2.17 + retests — confirm the unit/font/fit look right (the unit+font fixes depend on gemma following the new prompt rules).**

- **2026-07-04 (12th session)** — `Second live codegen syntax fallback fixed: bare ° token → generic source_line on violations (0.2.12→0.2.14)` — **Colin retested 0.2.12 and still got a fallback; I pulled the live logs.** The worker `docker logs isolinear-worker` showed `status=failed error=unsafe_code violations=[syntax_error@L19]` and the HA system-log WARNING (via `scripts/ha_logs.py`) carried the full message: `invalid character '°' (U+00B0) (<unknown>, line 19)`. So the 0.2.12 fence fix WORKED (the error moved L1→L19, real code now reaching the sandbox), but the model wrote the degree symbol as a **bare Python token** (e.g. `ax.set_ylabel(Temperature °F)` with no quotes), which `ast.parse` rejects — the only position of `°` that fails (in a string/comment/f-string it's fine). Repair re-emitted it every attempt because the repair task only described disallowed imports/attrs/calls. **Two commits.** **(1) `0.2.13` (`345be4a`):** a generation-side `_CODEGEN_PROMPT_RULES` rule (write all labels as Python string literals; never use non-ASCII like `°`/`%` as bare tokens; correct vs wrong example) + a repair-task clarification distinguishing `syntax_error` from `unsafe_code`. **(2) `0.2.14` (`458a8b7`) — the GENERIC fix, after Colin pushed back on "an increasingly long list of one-off instructions":** worker `static_safety_check` attaches `source_line` (the exact offending text, ≤200 chars) to EVERY line-numbered violation via new `_attach_source_lines` — both the `syntax_error` early-return and all `unsafe_code` violations. The repair task now points at `source_line` generically and the hardcoded `°` example was **removed** (walking back the slope). **Key insight:** the info was never missing — a `SyntaxError` fails in `ast.parse` before execution so there is NO richer traceback to give, and the full diagnostic + prior code were already in the prompt; the gap was the model **locating line 19 by counting** in its own output, which small models are bad at. Handing them the line verbatim is the lever, and it's generic across all violation classes. **No schema change** (`error.details` is `additionalProperties:true`; violations are free-form inside it); `_sandbox_error_view` already deep-copies violations so `source_line` reaches the repair prompt unchanged. The generation-side `°` rule stays but is now a **candidate for eval-gated retirement** (open-queue (o)) — if `source_line`-assisted repair handles the class alone, drop it. **Deploy split:** generation-side prevention ships via HACS (integration-only, 0.2.14); `source_line` robustness is **worker-side** and needs an image rebuild + `docker compose up -d --force-recreate isolinear-worker` on CT103 to take live effect. **Verify:** suite **414 passed / 4 skipped** (+2: worker `test_violations_carry_the_offending_source_line`; integration `test_repair_prompt_carries_violation_source_line`); evals `codegen_sandbox` + `codegen_generation_path` PASS; spec `codegen-generation-path` `repair_chart_code` description updated (traceback+violations+source_line, generic task). Inline invariant review OK (source_line is the model's own code already in the prompt; static gate runs in full; no boundary/schema/service change); arch subagent not spawned (bounded hotfix on the accepted codegen path), available on request. **Next: Colin HACS-redownloads 0.2.14 (+ optional worker rebuild) and confirms a first-attempt codegen render + grounded answer.**

- **2026-07-04 (11th session)** — `Fixed open-queue (n): codegen fell back to Pillow with unsafe_code because prose-before-fence replies became syntax_error@L1 (0.2.11→0.2.12)` — **The "new bug" was a codegen render always falling back to Pillow.** The 0.2.11 fallback WARNING gave it away instantly: `final_error_code: unsafe_code, codegen_attempts: 4, repair_attempts: 3, violations: ['syntax_error@L1: invalid syntax (<unknown>, line 1)']` — not a genuine unsafe construct; the worker's `ast.parse` failed on **line 1** of the code it received, every attempt. **Root cause:** the only transform between the model reply and the sandbox is `_strip_markdown_json`, a helper written for **JSON** — it strips a ` ``` ` fence only when the fence is the very FIRST thing in the text. Freeform codegen replies (and **repair** replies especially: "Here is the corrected code:\n```python…") lead with prose, so that prose survived as line 1 → `syntax_error@L1` → Pillow fallback. Reproduced exactly by feeding the helper a prose-prefixed reply. **Fix:** new `_extract_python_code` (`model_provider.py`) for `generate_chart_code`/`repair_chart_code` — pulls the first fenced block regardless of surrounding prose (non-greedy `_CODE_FENCE_RE`; strips lang tag; tolerates truncated/no-close fence; falls back to stripped raw text when unfenced). JSON-only `_strip_markdown_json` untouched. Verified on 8 reply shapes (prose before/after/both, no-lang, truncated, bare) — all extract clean compilable code, no fence leakage. **Integration-only** — no worker/frontend rebuild, no schema/sandbox change; the sandbox still runs the full static check on what it receives (invariant #3 intact). **Also:** diagnosed the "Custom element doesn't exist: isolinear-card" card break as a **stale browser cache**, not a code bug — verified live that the config entry is `loaded`, the Lovelace resource is registered (`?v=0.2.11`, type module), the JS serves 200 with+without auth byte-identical to the repo bundle, and the bundle registers the element in a DOM realm; a hard reload fixed it (confirmed). **Verify:** suite **411 passed / 4 skipped** (+3), evals `codegen_generation_path` + `model_authored_analysis` PASS; spec `codegen-generation-path` updated (the `_strip_markdown_json` lines now describe `_extract_python_code` + why). Inline invariant review OK (bounded parse hotfix; arch subagent not spawned, available on request). Version 0.2.11→0.2.12. **Next: Colin HACS-redownloads 0.2.12 and confirms a first-attempt codegen render + grounded answer.**

_(older sessions — 10th session shipped to `main` + live bring-up: merged the branch (caught a stale PR #3 half-ship), then fixed three live bugs — editable endpoints (0.2.9), repair blind to `unsafe_code` (0.2.10), failure logging (0.2.11); grounding-check proof req #4 floor-model claim-emission rate (8th session, 0.2.5→0.2.6, `079431d`/`e1c6ef7`); ADR-0031 D8a packet 4 answer-grounding check + 4d event anchors (6th/7th sessions, 0.2.3→0.2.5); ADR-0031 drafted + hardened by a real-data benchmark (`c9d6ad3`→`ac71de8`, 4th session, 0.2.1); ADR-0030 implemented in code: pandas/1024MB/repair-everything/codegen-primary + Pillow fallback (`4532ba5`/`a038b9b`/`940887b`, 3rd session, 0.2.1), ADR-0029 KEEP decision + ADR-0030 + the great scaffold purge (`f8f7760`/`255b0c3`, 2nd session), ADR-0029 packet 5 codegen reliability eval (`9320cf0`), packet 3 worker PROVEN LIVE on CT103 + OpenBLAS `RLIMIT_AS` fix (`2bb2747`), packet 4/0.1.49 (`b22992b`), packet 3 Dockerfile (`6321215`) + packets 1–2, ADR-0028/0.1.48, ADR-0027/0.1.47, ADR-0023/0.1.44, ADR-0026/0.1.43 and earlier — live in git history)_
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

## Blockers

- None.
