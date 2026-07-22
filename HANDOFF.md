# HANDOFF.md

## Current project phase

### 2026-07-22 (33rd session) — Claude-layer alignment with the agentic-workflow-kit (no product change)

**Phase.** `A workflow-tooling session, not a product session. isolinear's .claude/ layer was brought up to date with the agentic-workflow-kit; no custom_components/ code changed, version stays 0.2.46, suite 590/4 unchanged. Committed + pushed as 6ed0091.`

**What shipped.** Native slash commands (frontmatter + `$1`), review subagents registered (`code-reviewer`→`arch-reviewer` keeping `model: inherit`; new `bdd-evidence-reviewer`), branch-agnostic drift everywhere, a fail-open SessionStart drift-check + continuity guard with a read-only `permissions.allow` allowlist, and the continuity-budget guard PORTED + ON (`scripts/continuity_budget.py` + `.claude/continuity-budget.json`, calibration 1.7; `continuity_tracking:true` in `claude/workflow-config.json`). Two intentional deviations from the kit: isolinear KEEPS its Codex layer (`codex/`, AGENTS.md) and its `claude/` config path (kit deleted its own); HANDOFF stays a required read (it carries the phase) rather than being demoted, and ROADMAP.md is optional/absent. See [[isolinear-workflow-kit-alignment]].

**Arch review (fresh context, OK).** Run via `general-purpose` because the project's `arch-reviewer` subagent does not register in this hosted runtime (it will in a normal Claude Code session that reads `.claude/agents/`). No invariant surface touched; guard confirmed fail-open (exit 0 even over budget); refs resolve; rename clean.

**Outstanding — the continuity trim.** The guard now flags `STATUS.md` (~63k real-tok vs 9600, 6.6×) and `HANDOFF.md` (~143k vs 19200, 7.5×) every `/startup`. This is the intended nag, NOT a bug. It was deliberately NOT fixed this session: STATUS's top entry packs ~15 sessions in one inline paragraph, so a true rolling-5 restructure + a prune of stale HANDOFF phase entries (like the cosmetic `code-reviewer.md` mention at line ~2810) is a judgment-heavy content decision that needs Colin's steer on what recent detail to keep. **Next:** a dedicated trim pass to bring both files under budget.

### 2026-07-20 (32nd session) — two-sensor comparison answers: emission + multi-input delta grounding (0.2.46)

**Phase.** `The answer channel now covers two-sensor COMPARISON prompts. Both of the 31st session's deploy gates closed live on 0.2.45 first, then this packet shipped — with its premise corrected by a live repro before any code was written.`

**Recovered first.** The 31st session completed packet (r) but ended before committing: 0.2.45 sat staged in the index while STATUS reported it as committed. The staged tree was verified (suite 578/4, matching the closeout's claim) and landed as `8334dfe` + docs `c4400ce`, then pushed. Deploy gates then closed live on the deployed 0.2.45 (`evals/e2e_runs/20260720T165846Z/`): (r) Scenario A confirmed (clean off-track timeline lane + a grounded, verified 8-second duration → spec `timeline-codegen-rendering` promoted DRAFT→accepted, open-queue (x) closed) and the 0.2.44 correlation basis fix confirmed (e2e-13 r=-0.02 and e2e-20 r=0.75, both served + verified).

**The premise was wrong — and that is the main lesson.** The packet was scoped from STATUS as "e2e-08/17 verify as caveats → apply the align-grid extension after mean (0.2.37) and pearson (0.2.41)". A live-first repro (`scripts/repro_delta_rolling_grounding.py`) plus a live harness run on 0.2.45 showed otherwise: across 7 executed production-path runs **zero emitted a claim**, live e2e-17 answered "shows the general trend" with no number, and e2e-08's codegen collapsed to a Pillow fallback. The dominant failure was EMISSION, not the recompute. It is also worse than the assumed caveat: a claimless answer grounds as `outcome: pass` with `answer_verification` **absent** — served with no caveat and never checked, so a wrong number reads as fact (one run stated "4.0 %" against an aligned truth of 4.63). The STATUS line describing a caveat was true of ONE earlier run; emission varies run to run. See [[isolinear-claimless-answer-is-unverified]].

**What shipped (0.2.46, two-part, the (ff) shape).** _Emission (`model_provider.py`):_ a comparison question has the same shape as correlation — the gap is a scalar with nothing new to plot — so a rule makes the average difference the mandatory deliverable, computed off the aligned frame, with `inputs` in the SAME order as the subtraction; a paired sentence requests `params.window_ms` whenever a numeric rolling value is stated while explicitly NOT forcing a summary number. _Grounding (`answer_grounding.py`):_ `_compute_delta` for exactly two inputs recomputes the aligned average difference (was last-minus-first of `inputs[0]`), a pure-Python mirror verified against real pandas `align()` to 4 decimals; 3+ inputs return no reference.

**Proof.** `evals/comparison_delta_gate.py` (production codegen path, REAL recorder humidity, with/without arms, execution-truth judge = the real `run_grounding_check` both SERVES and VERIFIES): **with-rule 3/3 served and 3/3 verified (delta 4.6384, matching the independent reference to 12 decimals) vs without-rule 0/3, all plot-only — e2e-08 reproduced in the control arm.** Suite **590/4** (+12).

**Negative result, recorded rather than forced.** `rolling_mean` needs no algorithm change: raw-point (73.29) and aligned-grid variants (73.28–73.31) agree well inside the 0.05 tolerance, so alignment was never its problem — it only lacks `params.window_ms` to have a reference at all. Half the planned packet was retired by measurement instead of shipped to match its title.

**Arch review (fresh context) CONCERNS→RESOLVED — it caught two false-contradiction paths the fix had opened**, the exact (cc)/(ff) failure mode of withholding a CORRECT answer: (a) the prompt prescribes `align(history_series)`, whose `dropna` spans every numeric column, while the recompute intersected only the two claim inputs — with a third numeric series the grids diverge (measured live 5.40 vs 4.65, 15× tolerance), so both defensible grids are now computed and a value matching either verifies; (b) `delta` is the first ORDER-SENSITIVE multi-input metric (mean/pearson are symmetric), so a sign-only disagreement now caveats (`grounding_delta_sign_ambiguous`) instead of withholding. A wrong magnitude matches neither and still contradicts, keeping step 4 load-bearing. No invariant violations; `params` is already `additionalProperties:true` and `_coerce_claims` preserves it, so **no worker rebuild**. No new ADR (bug-fix class inside accepted ADR-0031 D8a / ADR-0036).

**One semantics call for Colin.** Grounding trusts the PROMPT CONTRACT for subtraction order rather than inferring it defensively, with the magnitude-match caveat as the safety net. The trade: a possibly back-to-front direction served with a caveat, versus a correct answer withheld. Chosen consistently with (cc)/(ff); the reviewer suggested explicit human sign-off rather than an ADR.

**Suspected context-overflow exposure INVESTIGATED and DISPROVED.** The LiteLLM client sends only `messages`, dropping `options` (`num_ctx=8192`, `temperature=0`), and LiteLLM runs `drop_params: true` — but `OLLAMA_CONTEXT_LENGTH=8192` is set server-side (exactly the intended value) and `temperature: 0` rides as a standard OpenAI body param. Residual, real but minor (open-queue (gg)): the overflow SAFETY NET is inert on that path — `_context_overflow()` is only called in the Ollama class (the OpenAI subclass overrides those methods) and `_provider_response_summary` reads Ollama-native `prompt_eval_count`. The replacement signal is measured: Ollama's `/v1` returns HTTP 200 with `usage.prompt_tokens` capped at exactly 8192 on a ~14k-token prompt. POE would instead need its 400 `context_length_exceeded` classified (inferred, not measured). See [[isolinear-openai-client-drops-ollama-options]].

**Next.**
1. **Deploy 0.2.46** — HACS redownload, then a live e2e-08 eyes-on that the comparison answer serves a numeric average difference and verifies on the card.
2. **(gg)** restore the overflow safety net on the LiteLLM path (small, self-contained; note the `_CODEGEN_NUM_CTX` vs `OLLAMA_CONTEXT_LENGTH` coupling should fail loudly, not silently mis-calibrate).
3. **(t)** the >2-day tiering wall (small ADR), **(F)** cosmetics (now including the timeline on-bar contrast and the raw entity-id y-tick label).

### 2026-07-19 — (r) BINARY/TIMELINE routing for the codegen render path (0.2.45)

**Phase.** `The codegen render path now handles a PRIMARY binary/categorical timeline (a door/occupancy entity charted on its own), closing the e2e-09 accept≠quality gap. Integration-only (no worker rebuild); deploy-gated on a HACS redownload + a live eyes-on before the spec promotes.`

**What it was.** Live e2e-09 on the deployed 0.2.42 served a codegen chart of ~4 near-zero axvspan verticals on a fake Open/Closed axis + a degenerate "0.0 minutes" answer (open-queue (x)). Root cause: a primary timeline series carries `overlays: []`, so `_compute_overlay_bands` (which only iterates `chart_spec['overlays']`) handed codegen empty `derived_intervals`, and the model derived on-regions from raw points badly. The codegen path had no timeline handling at all (invariant #9 gap since the 16th session).

**Fix (spec `docs/specs/timeline-codegen-rendering.md`, DRAFT — a bounded extension of ADR-0022/0030/0031/0033, no new ADR).** C1: `_compute_timeline_bands`/`_compute_derived_intervals` (render_dispatch) precompute state intervals for a primary timeline, reusing the trusted Pillow `_binary_on_regions` region logic. C2: a `_CODEGEN_PROMPT_RULES` `broken_barh` idiom — a grey off-baseline track spanning the window + colored on-bars on one fixed entity-labelled lane, window-relative min-width for brief openings; never axvspan/line/raw-point derivation. C3: the duration answer sums the precomputed intervals (deviation from the draft's `timeline_summary` request field, which would have forced a worker schema copy + rebuild). C4: grounding `_compute_state_duration` (independent ms recompute, mirrors `_compute_hours_above` + holds a still-active final segment to the global window end like C1) + a metric-aware relative tolerance + treats `state_duration` as a descriptive value-only metric (nulls spurious model verdict/rule; the (cc) class).

**Proof.** Eval gate `evals/timeline_render_gate.py` (production codegen path, live gemma, with/without the render rule; execution-truth judge on BOTH a clean lane — off-track + on-bars + entity y-ticks — AND a grounding-verified non-degenerate duration): with-rule every executed run draws a clean lane + grounded 540000 ms; without-rule 0/3 (verticals on a numeric axis). Eyes-on `evals/prompts/timeline_eyeson.png`. Suite 578/4. Arch-review subagent (fresh context) CONCERNS→resolved (window-end asymmetry fixed + tested; descriptive-metric-class policy documented as a candidate future ADR `value-only-metric-classes-in-grounding`).

**Unresolved / next.** ~~Deploy-gated~~ **RESOLVED 2026-07-20 (32nd session):** pushed on Colin's OK, HACS-redownloaded, live e2e-09 Scenario A confirmed on the deployed 0.2.45 (run `evals/e2e_runs/20260720T165846Z/` — clean off-track lane + grounded VERIFIED 8-second duration) → spec promoted DRAFT→accepted; the same run confirmed the 0.2.44 correlation basis fix live (e2e-13 r=-0.02 "Not really" verified, e2e-20 r=0.75 "Yes" verified). Latent: categorical (HVAC-mode) multi-lane polish is in C1 but only binary is anchored/eyes-on'd. New (F) nits: timeline on-bar #ffe0b2 low contrast vs the grey track; verdict-string spliced mid-sentence; e2e-20 generic "Temperature" legend label.

### 2026-07-17 — (ff) part-3: the correlation "no answer" is a verdict-basis contradiction, not an emission miss (0.2.44)

**Phase.** `The last (ff) correlation gap is closed. The live 0.2.42 e2e showed temp-vs-temp correlations (e2e-13/e2e-20) still not serving; a faithful real-data repro proved it was NOT emission — the model emits a correct coefficient but grounding withholds it on a verdict/rule basis mismatch. Prompt-only fix.`

**Why the earlier diagnosis was wrong (the e2e-over-synthetic lesson, again).** The 0.2.41 (ff) fix framed the residual as an EMISSION miss ("the model plots and stops"). Two probes disproved that: (1) the SYNTHETIC `repro_correlation_answer.py` reproduced a *different* failure — the model guessed wrong entity_ids against synthetic data and hit an early-return "could not find sensor data" guard; (2) a new faithful `scripts/repro_correlation_emission_realdata.py` (REAL kitchen/basement recorder history + the exact e2e-13 prompt) reproduced the LIVE behavior **6/6**: the model EMITTED a correct `r ≈ -0.40` (the grounding recompute matched to 13 decimals — the 0.2.41 grounding fix is solid) but the answer was **WITHHELD** as `grounding_verdict_contradicted`. A withheld answer is suppressed on the card, so it looked exactly like a plot-only emission miss in the snapshot.

**Root cause.** The model derives its correlation verdict from **magnitude** (`verdict = 'Yes' if abs(corr) > 0.3 else 'Not really'`) but the prompt's `pearson_r` claim example declared the rule with **`basis: 'value'`**. For a negative correlation strong enough that `|r| > 0.3` but `r < 0.3` (−0.40), grounding's step-6 consistency check re-derives 'Not really' from the declared rule while the model claims 'Yes' → contradiction → withhold. Positive correlations (and e2e-14's −0.31, which the model happened to call 'Not really') stayed internally consistent, which is why e2e-14 served and the same-metric negatives didn't.

**Fix (0.2.44, prompt-only — no code/grounding change; `_apply_rule` already supported `basis: 'abs'`).** The `pearson_r` claim example now declares `basis: 'abs'` (correlation strength is magnitude, matching the `abs(corr)` verdict), plus a CRITICAL `_CODEGEN_PROMPT_RULES` instruction: `basis` MUST match how the verdict was derived (magnitude → 'abs', else 'value'), with the concrete −0.40 failure spelled out.

**Verification.** **Real-data gate flipped: 6/6 WITHHELD → 6/6 SERVED+VERIFIED at MAX_REPAIRS=3 (production repair budget); at MR=1, 3/3 clean-execution runs verified and the other 3 were generic codegen runtime errors (NameError `isolinear` unimported, undefined `series`, brace mismatch — unrelated to the basis fix, repair-recoverable, which the MR=3 run confirmed).** Suite **568 passed** (+3: `TestCrossSensorPearsonR.test_negative_correlation_value_basis_contradicts` [value → contradicted + withheld] and `_abs_basis_verifies` [abs → verified], + a prompt-rule pin). Spec `model-authored-analysis` §2 gained the basis part. No BDD (prompt-rule fix on an accepted contract; the real-data gate + unit tests are the proof). Integration-only, ships via HACS, no worker rebuild. Version **0.2.44**.

**Next.**
1. **(r) binary/timeline routing** — codegen renders binary/categorical entities empty (invariant #9 gap, e2e-09).
2. Cross-sensor **delta/rolling** grounding = the documented next align-grid extension (e2e-08/17 verify as caveats today).
3. **(t)** the >2-day tiering wall (small ADR), **(F)** cosmetics (legend color-fidelity, mixed-unit axis, x-axis date formatting, door zero-duration).

### 2026-07-17 (30th session) — (y) card-level legend for the codegen render path, + a new `computed` legend kind (0.2.42)

**Phase.** `The ADR-0027 D1 card-level legend now populates on the codegen path (ADR-0030), with a third legend kind — computed — so a model-authored derived series (mean/delta/deviation) reads distinctly from a raw sensor (solid) and a state-overlay band (shaded). Landed integration+frontend+worker; goes live after a worker rebuild.`

**The gap (traced end-to-end).** The card-level legend — a rich disclosure OUTSIDE the plot, one row per series/overlay with swatch/entity/alias/state breakdown — was wired for the Pillow renderer but never fed by codegen since ADR-0030 made it primary. Three links were dead: (1) the codegen return-contract (`_CODEGEN_PROMPT_RULES`) only asked for `{title, series_plotted, warnings}` — no legend; (2) the WORKER `_normalize_render_metadata` rebuilt the metadata from a fixed key set and silently DROPPED any returned `legend`/`summary`; (3) `render_dispatch._build_worker_artifact_metadata` copied only `answer_text` while its Pillow twin copies legend+summary. The frontend disclosure UI and `snapshot_assembly` copy were already renderer-agnostic and intact — just never fed.

**The decision (confirmed with Colin via AskUserQuestion).** Colin's liked convention: real sensors solid, a computed series dashed. Because the frontend keys `kind === "overlay"` to a state-band tag + a per-state `states` breakdown, a computed *line* cannot reuse `overlay` without inheriting band UI. Decision: **a third `kind: "computed"`** (real=`series`/solid, computed=`computed`/dashed, state band=`overlay`/shaded), and **drop the in-image `ax.legend()`** — the card-level legend supersedes it; line style carries the in-plot distinction. Both product calls, so both were confirmed before writing the contract.

**What shipped (0.2.42).** Spec `docs/specs/card-level-legend-codegen.md` (DRAFT, extends the accepted `card-legend-and-summary.md`) + BDD `bdd/dashboard-card/card-level-legend-codegen-bdd.md` + evidence file.
- **Schema** — `computed` added to the legend `kind` enum in every copy: `render-result` (×3: docs, custom_components, worker), `integration-artifact-metadata` (×2), `integration-job-snapshot` (×2). Byte-identical per group; purely additive (existing `series`/`overlay` validate unchanged). The `legend` and `summary` fields were ALREADY in the render-result `render_metadata` schema — only the enum needed extending.
- **Worker** (`codegen_sandbox.py`) — `_normalize_render_metadata` now preserves a sanitized legend via new `_coerce_legend` (drops non-dict rows, rows with an unknown kind, and rows without a `#rrggbb` hex color — a swatch can't be recovered otherwise; keeps `states` only for `overlay`) + a `summary` passthrough. Cosmetic (spec C6): a malformed/missing legend is dropped, never fails the worker response (which would 500 → unrepairable Pillow fallback).
- **`render_dispatch.py`** — `_build_worker_artifact_metadata` copies `legend`+`summary` onto the artifact, matching the Pillow builder (parity gap closed).
- **Prompt** (`model_provider.py`) — the return-contract dict names `legend`; a new rule requires `legend[]` (self-reported lower-case hex colors + `kind`), solid raw sensors / dashed computed (`linestyle='--'`), and NO `ax.legend()`.
- **Frontend** (`isolinear-card.ts`, `types.ts`) — a `computed` tag (distinct from `overlay`) + a hollow dashed-outline swatch; `kind` type widened. Bundle rebuilt (`npm run build`, type-check clean) and synced to `custom_components/isolinear/frontend/dist/`.

**Verification.** Suite **565 passed** (+6: `CodegenLegendSandboxTests` — passthrough, malformed-color drop, chart-only-no-legend; `CodegenLegendEndToEndTests` — legend+summary thread to `snapshot.chart` + artifact on the real codegen path; `CodegenLegendPromptRuleTests`; `CodegenLegendSchemaTests`). Frontend **37 passed** + build type-checks. BDD evidence captured for Scenarios B/C/D on the real pipeline; **Scenario A (live card eyes-on — the dashed computed line + `computed` row on the actual card) is deploy-time-pending.** **Arch-review subagent (fresh context): OK** — no invariant violations; `_coerce_legend` runs in the TRUSTED worker parent AFTER the subprocess returns (no sandbox capability/import/IO — invariant #3 intact); legend is display-only (grep-confirmed it never enters grounding/repair/plan validation); schema change additive (#4); `summary` parity justified (same pre-existing drop), not scope creep; no new ADR (an enum extension of the accepted ADR-0027 D1 `kind` field, which D2 already framed as follow-up work).

**⚠️ NOT integration-only — worker rebuild required.** The `_normalize_render_metadata` change is worker-side. Deploy order: rebuild the worker image + `docker compose up -d --force-recreate isolinear-worker` on CT103, THEN HACS-redownload 0.2.42, THEN eyes-on the card. Until the worker rebuilds, the legend stays dropped even on 0.2.42. Prior worker rebuild was 0.2.34.

**Next.**
1. **(y) deploy + eyes-on** — worker rebuild, then confirm a computed-average chart shows the 3-row legend with a dashed `computed` row and no in-image legend (Scenario A). Then promote the spec draft→accepted.
2. **(r) binary/timeline routing** — codegen renders binary/categorical entities empty (invariant #9 gap, e2e-09).
3. **(t)** the >2-day tiering wall (small ADR), **(F)** cosmetics.

### 2026-07-16 (29th session) — (ff) correlation-answer gap closed, a two-part fix reproduced live before designing (0.2.41)

**Phase.** `The analysis-answer layer now fires for correlation too. Correlation prompts used to render the two input series but never serve a computed Pearson r + verdict; a live production-path probe split that into a grounding bug (the coefficient could never be independently verified) and an emission bug (the model plots and stops). Both fixed and eval-gated. The answer channel now covers mean / delta / deviation / distribution / rolling / correlation.`

**How the probe drove the design ([[feedback-e2e-over-synthetic]]).** Before touching code I ran `scripts/repro_correlation_answer.py` — the production codegen path (real `generate_chart_code` + `_CODEGEN_PROMPT_RULES`) against live gemma4:e4b, executing the returned code and running the REAL `run_grounding_check`, bucketing each run. First read (3 runs): 2 `EMITTED_UNVERIFIED` (the model computed corr=0.997 correctly but grounding could not verify it) + 1 `NOT_EMITTED` (plot only). That split the symptom cleanly into the two causes below — neither guessed.

**Part 1 — GROUNDING (`answer_grounding.py::_compute_pearson_r`).** The recompute paired the two sensors on their EXACT-timestamp intersection (`set(map_a) & set(map_b)`). Two sensors read by separate integrations share NO raw timestamps, so on real recorder data that intersection is empty → `None` → no reference → a correct correlation could only ever be served as an `unverified_caveat`, never verified. This is the exact analog of the 0.2.37 multi-input `_compute_mean` bug (which averaged only `inputs[0]`), never applied to pearson. Fixed to resample each input onto the shared 5-min `align()` grid (reusing the existing `_resample_interpolate` helper) and correlate the paired buckets — mirroring the model's `align().corr().iloc[0, 1]`, verified to ~12 decimals against the model's own value. Grounding stays pure-Python and independent (no pandas). It is a strict TIGHTENING: wrong coefficients are now caught that previously rode as caveats; `<3` shared buckets or `den_sq <= 0` still return `None` → caveat, never a false contradiction.

**Part 2 — EMISSION (`model_provider.py` `_CODEGEN_PROMPT_RULES`).** Re-probing against the fixed grounding (5 runs) confirmed Part 1 (emitted runs flipped `EMITTED_UNVERIFIED` → `SERVED_VERIFIED`) but exposed that emission is the dominant remaining half: 3/5 runs plotted the two raw sensors and returned with no `answer_text`. Unlike a mean/delta/deviation — which produce a derived SERIES the model plots (and plotting it reinforces that it did the analysis) — a correlation is a single SCALAR with nothing new to plot, so the floor model treats the chart as the deliverable and stops. A new prompt sentence ("IMPORTANT for correlation questions…") makes the coefficient the mandatory `answer_text` deliverable: plotting the raw sensors is explicitly not enough; the model MUST compute `frame.corr().iloc[0, 1]` and report it. Also harmonized a stale `df['a'].corr(df['b'])` example (the last non-aligned correlation idiom in the rules) to `align()` (arch-review nit).

**The eval as the proof.** `evals/correlation_answer_gate.py` drives the production codegen path over two genuinely-correlated sensors, two arms (production rules with/without the emission sentence), execution-truth judge = the real `run_grounding_check` SERVES the answer (`withheld=False`). **Result: with-rule 4/4 served and ALL 4 verified (corr=0.997, `outcome=verified` — Part 1 confirmed end-to-end) vs without-rule 0/4** (2 withheld `grounding_verdict_absent`, 2 runtime-exhausted).

**Verification.** Suite **559 passed** (+10: `TestCrossSensorPearsonR` — 5 grounding tests incl. `test_wrong_correlation_value_now_contradicts` pinning the recompute stays load-bearing after it starts producing references; `CorrelationEmissionPromptRuleTests` — 1 rule-text pin). **Arch-review subagent run (fresh context): OK** — grounding independence preserved, faithful to `align()` (interior-only interpolation → the bucket-set intersection mirrors pandas `dropna`, no extrapolation on either side), no new unverified/wrong path opened, invariant #1 (allowlist on `claim.inputs`) unaffected; bug-fix within accepted ADR-0031 D8a / ADR-0034 / ADR-0036, no new ADR. Spec `answer-grounding-check` §5 (pearson on the shared grid) + `model-authored-analysis` §2 (the two-part (ff) fix) updated. No BDD (a prompt-rule + grounding bug-fix on existing contracts; the gate + unit tests are the proof — same treatment as the (cc) fix). Integration-only, no worker rebuild. Version **0.2.41**.

**Not yet done / for the deploy step.** The fix is proven on the production codegen path via the gate, but NOT yet re-run through the full live e2e harness. When Colin redownloads 0.2.41, re-run e2e-13/14/20 to confirm the correlation answer serves + verifies live (and check the e2e-14 mixed °F/% axis cosmetic (F) while there).

**Next.**
1. **(y) card-level legend for codegen** — needs a `kind:computed` design decision before a spec (`docs/research/codegen-card-level-legend.md`).
2. Then **(r)** binary/timeline routing, **(t)** the >2-day tiering wall (small ADR), **(F)** cosmetics (e2e-14 mixed-unit axis, door zero-duration intervals, raw-epoch axis, generic axis word).

### 2026-07-16 (28th session) — ADR-0036 + ADR-0037 promoted to accepted; the (cc) grounding_verdict_ambiguous fix, which the live gate proved is two-part (0.2.40)

**Phase.** `The LiteLLM provider is live-confirmed end-to-end through the card; two long-carried ADRs are now accepted; and the (cc) descriptive-verdict bug — a correct mean answer being withheld by a spurious verdict — is fixed with a two-part prompt + grounding change the eval gate forced into the open.`

**Context.** Colin confirmed a query now works end-to-end on the LiteLLM provider. The residual failure from the 27th session was a **configuration error** — the worker and model endpoints were split across `10.0.1.39` and `10.0.1.46`; both belong on `.46`. That was not a code bug (and the 0.2.39 `provider.type` schema fix was still genuinely necessary — it was producing a *different* failure through the same retry-policy path). With the provider live-exercised through the card, the two draft ADRs are ripe to accept.

**What shipped.**
- **ADR-0036 draft → accepted.** The in-sandbox `isolinear_analysis.align()` helper; proof gate (e2e-18 clean PASS + e2e-11 grounds) met since the 24th–25th sessions.
- **ADR-0037 draft → accepted.** The OpenAI-compatible / LiteLLM provider; now live-exercised through the card (the acceptance gate the arch review flagged in the 26th–27th sessions). `docs/decisions/README.md` index synced for both.
- **(cc) grounding_verdict_ambiguous fix (0.2.40) — TWO-PART, surfaced by the eval gate.** The 25th session flagged that the codegen model decorates a plain descriptive mean ("the average was 72.9 °F") with a spurious `verdict`+`rule`; the grounding step-5 verdict-containment then rejects it (`grounding_verdict_absent`), and because every re-generation recomputes the same correct number, all repair attempts hit the identical wall → the correct answer is withheld.
  - **Part 1 (prompt, `model_provider.py`).** A `_CODEGEN_PROMPT_RULES` sentence: attach `verdict`+`rule` to a claim ONLY for a Yes/No or categorical judgment; a plain descriptive value answer emits a value-only claim (`metric`+`inputs`+`value`) and omits them.
  - **Part 2 (grounding, `answer_grounding.py`) — which the gate proved necessary.** Under Part 1, gemma nulls the verdict but frequently leaves a vestigial empty `rule: {"bands": []}` stub, which step-1 structure validation rejected as `grounding_claim_malformed`. A rule is inert without a verdict (steps 5 and 6 both gate on `verdict is not None and rule is not None`), so `_check_claim` now skips rule-structure validation when `verdict is None`, treating a verdict-less claim as value-only. The mean is still value-verified at step 4.

**The eval as the proof (and the honest path to it).** `evals/verdict_omission_gate.py` drives the production codegen path against live gemma with an e2e-11-shaped descriptive two-sensor mean prompt, two arms (production rules with/without the new sentence), and an execution-truth judge = the REAL `run_grounding_check` SERVES the answer (`withheld=False`). **Result: with-rule 3/3 served vs without-rule 0/3** (all three without-arm runs reproduced the live withhold via `grounding_verdict_absent`). Two earlier gate runs were invalid and discarded honestly: the first because `isolinear_analysis` wasn't on the exec-harness `sys.path` (the ADR-0036 helper the production align() rule reaches for) so every run failed on a `ModuleNotFoundError` unrelated to the rule; the second because the judge miscounted `verdict: null` (key present, value null) as "decorated". Both fixed — worker/ added to the harness path (mirroring `analysis_helper_gate.py`), and the judge rewritten to key on the grounding *outcome* (served vs withheld) rather than the presence of an inert rule stub.

**Verification.** Suite **549 passed / 4 skipped** (+4: the rule-text pin `VerdictOmissionPromptRuleTests` + three grounding-contract tests — value-only claim served, null-verdict-with-empty-rule-stub tolerated, and a **wrong-value-still-caught** guard that pins step-4 stays load-bearing after the relaxation, per the arch-review recommendation). **Arch-review subagent run (fresh context): OK** — traced `_check_claim` and confirmed the tolerance does NOT let an unverified/mismatched value ride through (step-4 recompute + tolerance runs regardless of verdict/rule; steps 5/6 were already unreachable when `verdict is None`, so only the inert rule-STRUCTURE check is skipped); invariant #1 (allowlist on `claim.inputs`) unaffected; no new ADR (a bug-fix within the accepted ADR-0031 D8a grounding contract). Spec `model-authored-analysis` §2 (the rule + the two-part rationale + gate result) and §5 (the inert-rule tolerance) updated. No BDD (a prompt-rule + grounding-tolerance bug-fix on an existing contract; the eval gate + unit tests are the proof). Integration-only, no worker rebuild. Version **0.2.40**.

**Live e2e validation (same session, deployed 0.2.40 through LiteLLM).** Colin redownloaded 0.2.40 (WS manifest/get → 0.2.40) and I ran the full 20-prompt e2e suite through the LiteLLM proxy: **16 PASS / 2 PARTIAL / 2 not-clean** (vs the 22nd-session 0.2.27 baseline of 11 / 4 / 3). **The (cc) fix is confirmed live** — e2e-11 renders a clean computed mean series and serves *"The average temperature across the kitchen and basement over the last day was 73.02 °F"* with `answer_verification: verified` (that prompt had failed in some form for ~10 sessions). ADR-0036 deviation (e2e-18), the (w) heatmap→histogram degrade (e2e-15), the (v) cross-metric resolution (e2e-14, temp+humidity both plotted), and the 0.2.30 door-guard (e2e-20, two temps not a door) all hold live. **No provider-caused regressions** — codegen, the answer channel, grounding, and the reasoning-driven planner all work through the proxy. The two not-clean: e2e-04 (the known >2-day AC-overlay tiering wall, open-queue (t)) and e2e-13 (the long-flaky correlation codegen → Pillow `unsafe_code`). **e2e-08** (2-sensor humidity compare) failed twice *under load* (connection_error, then a 544s timeout) but rendered clean via codegen in **63s when re-run in isolation** — transient GPU contention, not a defect (reinforces the `OLLAMA_MAX_LOADED_MODELS=1` recommendation). **NEW open-queue (ff): correlation prompts (e2e-13/14/20) render the two input series but never COMPUTE/SERVE a Pearson r + yes/no verdict** — the analysis-answer layer fires for mean/delta/deviation/distribution/rolling but not correlation (the registry already has `pearson_r`, and the 22nd session once saw a grounded r=0.08, so this is a codegen-emission gap, likely a `_CODEGEN_PROMPT_RULES` nudge + eval gate). Cosmetic nits logged: e2e-09 door zero-duration intervals ("16:45 to 16:45", open-queue (x)), raw-epoch x-axis on one generation (variance), e2e-14 mixed °F/% axis. **Harness fix:** a long provider stall dropped the HA WebSocket mid-run (killed the first run at e2e-09); `HaWs.call` now reconnects+retries once on `ConnectionClosed` (`evals/e2e_pipeline_harness.py`, commit `971e573`, eval-only/commit-only) — it held through the whole retry batch. Run dirs: `evals/e2e_runs/{20260716T203832Z,210149Z,214021Z}/` (gitignored — private HA data).

**Next.**
1. **(ff) correlation-answer gap** — correlation prompts render the series but don't emit a computed correlation coefficient + verdict. Candidate fix: a `_CODEGEN_PROMPT_RULES` nudge (compute `corr()` and answer it) + an eval gate on the production codegen path (judge = `answer_text` carries a corr value the grounding check verifies). Pairs with the e2e-14 mixed-unit-axis nit.
2. **(y) card-level legend for codegen** — needs a `kind:computed` design decision before a spec (see `docs/research/codegen-card-level-legend.md`).
3. Then **(r)** binary/timeline routing, **(t)** the >2-day tiering wall (small ADR), **(F)** cosmetics (door zero-duration intervals, raw-epoch axis, generic axis word).

_Infra note (this session): on the LLM host (RTX 3060 12 GB), gemma4:e4b @ num_ctx=8192 = 10.69 GB VRAM (weights ~9.6 GB fixed + KV ~1.1 GB, scales with num_ctx); Frigate baseline ~1.6 GB → both fit at ~11.4 GB with only ~500 MB headroom. Recommended `OLLAMA_MAX_LOADED_MODELS=1` (Colin to set). Cloud-E4B research: only Fireworks hosts Gemma 4 E4B (~$0.20/M, LiteLLM-reachable); Poe has 31B only; Groq has no Gemma; free tiers serve bigger Gemma 4, not E4B._

### 2026-07-16 (27th session) — Write-only LiteLLM key field (ADR-0037 §4, deferred item now landed) + a live-discovered schema bug fix (0.2.39)

**Phase.** `The (ee) deferred item from the 26th session — the write-only provider-key field — is landed. While closing it, Colin re-enabled proxy auth and hit a live failure that traced to a real bug in the 26th session's ADR-0037 landing: three JSON Schemas still hardcoded provider.type to the pre-ADR-0037 Ollama-only const, rejecting every schema-validated record the new default provider produces the moment a call fails. Fixed alongside the key field.`

**What shipped.**
- **`ModelProviderKeyStorageHelper`** (new `model_provider_key_storage.py`) — an integration-owned HA Store, structurally identical to the ADR-0032 `WorkerTokenStorageHelper` (per-entry keys, presence-only `summary()`, no key value ever surfaced). No minimum length (API keys vary, unlike the 24-char worker-token floor).
- **Write-only `model_provider_api_key` options-flow field** (`config_flow.py`): `extract_provider_key_action()` splits keep/save/clear out of the form input *before* options validation — same ordering as `extract_worker_token_action`. `_apply_provider_key_action()` saves/clears and rebuilds both the planner and codegen clients immediately (a key-only re-paste leaves options unchanged, so the options-update listener never fires — same reasoning as the ADR-0032 token rebuild).
- **`config_schema.py`** — `model_provider_api_key` added to `FORBIDDEN_CONFIG_KEYS` as defense-in-depth (it must never land in config data/options even by accident).
- **`_build_planner_client`** now accepts `api_key`; `setup_model_provider_planner`/`setup_model_provider_codegen` read the stored key via `stored_model_provider_key(hass, entry_id)` and thread it into `OpenAICompatiblePlannerClient`, which sends `Authorization: Bearer <key>`.
- **Live bug found + fixed:** Colin re-enabled LiteLLM proxy auth (no key configured yet) and got a card failure — `SNAPSHOT_POLL_FAILED` / `invalid_integration_model_provider_retry_policy`. Root cause: `integration-model-provider-plan`, `integration-model-provider-health`, and `integration-model-provider-retry-policy` schemas all hardcoded `provider.type` to `"const": "ollama_compatible"`, a leftover from before ADR-0037 added the second provider. The 26th session's "live-proven" verification called the client directly and never routed a *failure* through the full orchestration + schema-validation path, so this never surfaced until a real 401 hit it live. Fixed: `provider.type` → `"enum": ["ollama_compatible", "openai_compatible"]` in all three schemas, both the `docs/schemas/` source copies and the bundled `custom_components/isolinear/schemas/` runtime copies (kept byte-identical, verified). Also fixed a paired correctness bug: the health record's `provider.health_path` was hardcoded to Ollama's `/api/tags` regardless of provider; `_provider_health_metadata()` now picks `/api/tags` or the new `MODEL_PROVIDER_OPENAI_HEALTH_PATH = "/models"` based on the actual provider type.

**Verification.** Suite **545 passed / 4 skipped** (+34: 28 key-storage tests + 6 schema-regression tests). 4 of the 6 new schema-regression tests were confirmed to genuinely fail against the pre-fix schemas (git-stashed the schema files, re-ran, saw the exact live error message `"$.provider.type must equal 'ollama_compatible'."`, restored) — not vacuous. **Architecture-review subagent run (general-purpose, fresh context) — OK**: no invariant violations; secret handling verified clean (key never reaches config data/options/logs/card, extraction ordering matches ADR-0032); grepped the whole repo for the stale const pattern — no other schema missed; both schema copies confirmed byte-identical. No new ADR needed — the key field is ADR-0037 §4 landed verbatim, and the schema fix is a pure bug fix on an already-decided default. No BDD (mirrors how the 26th session treated the provider transport itself — additive/bug-fix on an existing contract, not a new user-facing surface).

**Deploy state.** Commit-only as of this write-up; **PUSHED per Colin's explicit request this session**. Integration-only, no worker rebuild. Version **0.2.39**.

**Still open / not yet verified live.** Colin has not yet generated a LiteLLM virtual/master key or pasted it into Isolinear's Configure form — the proxy's auth is on but Isolinear is still sending unauthenticated requests until he does. Once he does: (1) confirm the query now succeeds end-to-end (the schema fix should mean any transient failure now surfaces cleanly instead of `invalid_integration_model_provider_retry_policy`); (2) confirm the health entity reports `ready` (exercises the `health_path` fix live). ADR-0037 stays `draft` — the architecture review noted its full decision surface is now landed and suggested flipping it to `accepted`, but that's pending Colin's OK per this repo's ADR-immutability convention, and ideally after the live key-based retest above.

**Next.**
1. **Colin: generate a LiteLLM virtual key, paste it into Configure, redownload/restart, and confirm the query + health entity work end to end.**
2. **(I) Promote ADR-0037 draft → accepted** once the above live retest is clean (per the architecture review's recommendation).
3. **(cc) grounding_verdict_ambiguous** prompt rule (carried over from the 25th session).
4. **(y) card-level legend for codegen** (needs a `kind:computed` decision).
5. **(I) promote ADR-0036** draft→accepted (carried over).
6. Then (r) binary/timeline routing, (t) the >2-day tiering wall, (F) cosmetics.

### 2026-07-16 (26th session) — Second model provider: OpenAI-compatible / LiteLLM proxy, now the default; the ADR-0025 thinking stream survives + simplifies (0.2.38, ADR-0037)

**Phase.** `Model access can now route through a LiteLLM proxy (OpenAI-compatible), which is the default for local dev/testing — model A/B (local vs POE cloud) is a config change, not a code change.` Colin is moving the homelab behind a LiteLLM proxy. The open question — does the ADR-0025 live "thinking" stream survive the move off Ollama's native `/api/chat`? — was answered by probing the REAL proxy before designing ([[feedback-e2e-over-synthetic]]).

**Probe findings (live, `http://10.0.1.39:4000/v1`, `ollama/gemma`).** (1) `/v1/models` exposes `ollama/gemma` + `ollama/qwen-coder`; (2) `response_format` json_schema returns clean schema-valid JSON through the `ollama_chat` route — the planner's structured-output contract holds; (3) reasoning streams as `choices[0].delta.reasoning_content` via `reasoning_effort`; (4) **the decisive one — reasoning + structured JSON coexist in ONE streaming call**, so Ollama's two-pass think-then-format workaround (needed because Ollama suppresses thinking under `format`) is unnecessary here.

**What shipped (0.2.38, ADR-0037 draft).**
- **`OpenAICompatiblePlannerClient`** (`model_provider.py`) — a subclass of the Ollama client that REUSES every payload builder's `messages` array (all the prompt/rules/schema construction, provider-agnostic) and overrides only transport: POST `{base}/chat/completions`, `response_format` json_schema (where Ollama used `format`), an SSE consumer mapping `delta.reasoning_content` → the existing `on_reasoning` callback (sanitized, unchanged) and `delta.content` → the message, optional `Authorization: Bearer`, and a `/models` health check. Single streaming call replaces the two-pass; a model with no reasoning degrades to the ADR-0025 D6 "nothing shown" fallback.
- **Default flipped to LiteLLM** — `default_config_data()` → `openai_compatible`, `http://10.0.1.39:4000/v1`, planner `ollama/gemma`; codegen defaults to the planner (gemma), preserving prior codegen behavior. Ollama retained as a selectable type.
- **In-place provider switch** — `model_provider_type`/`planner_model`/`codegen_model` are now editable in the OPTIONS form (routed into config-entry data like the endpoints), so an existing install switches Ollama→LiteLLM without deleting the integration and re-entering its allowlist. The client rebuilds live on submit.
- `_build_planner_client` factory selects the client by provider type; the config gate `_has_planner_config` (renamed from `_has_ollama_planner_config`) accepts both types.

**Verification.** Full suite **511 passed / 4 skipped** (+23: 22 client transport/factory/health + 1 in-place-switch-keeps-allowlist). **Live-proven against the real proxy:** health `ready`; `plan_chart` returned `chart_spec_ready` (structured) with **674 streamed reasoning callbacks**; `generate_chart_code` returned a valid `render_chart`. **Arch-review subagent RUN — OK** (no invariant violation; #1 allowlist preserved through the switch; #3 sandbox untouched; #4 strengthened — `response_format` `strict:true`; secret handling clean — `api_key` is always None today, never in data/options, no key in debug logs; subclass reuse sound, drift bounded by the shared `messages` contract; ADR-0037 the sufficient record). No BDD (additive transport, not a new user-facing surface; unit tests + live probe are the proof).

**Deploy / usage.** `main` will be **0.2.38, PUSHED**, integration-only (no worker rebuild). Auth is currently DISABLED on the proxy (Colin's temporary dev setting), so no key is sent. To switch his existing install: Configure → set provider `openai_compatible`, model endpoint `http://10.0.1.39:4000/v1`, planner `ollama/gemma` → submit (allowlist kept). **Caveat:** if proxy auth is re-enabled before the key field lands, `/v1/models` health returns 401 → provider shows unhealthy; keep auth off until then.

**Deferred (ADR-0037 §4).** The write-only bearer-key config-flow field + key Store (mirroring the ADR-0032 worker token) — not needed while auth is off. When it lands, add a `config_schema` regression asserting no provider key ever appears in data/options (arch-review rec).

**Next.**
1. **Write-only LiteLLM key field** when Colin enables proxy auth (deferred here).
2. **(cc) grounding_verdict_ambiguous** prompt rule (from the 25th session — the model attaches a spurious verdict+rule to a plain descriptive mean).
3. **(y) card-level legend for codegen** (needs a `kind:computed` decision; `docs/research/codegen-card-level-legend.md`).
4. **(I) promote ADR-0036** draft→accepted; **ADR-0037** draft→accepted once live-exercised through the card.
5. Then (r) binary/timeline routing, (t) the >2-day tiering wall, (F) cosmetics.

### 2026-07-14 (25th session) — Packet (H) closed: e2e-11's empty answer root-caused live to a grounding-reference bug and fixed (0.2.37); Ollama timeout made configurable (0.2.36); card-level legend re-scoped

**Phase.** `e2e-11's persistent empty-answer symptom is ROOT-CAUSED and FIXED — live-confirmed on Colin's own card.` The [[isolinear-e2e11-sandbox-cascade]] theory (a sandbox-execution repair cascade) was **superseded**: ADR-0036's `align()` (0.2.34) had already resolved the sandbox `KeyError`/`PermissionError` class, and the current dominant failure is a grounding-reference bug. Diagnosis was done against the REAL deployed pipeline + system_log ([[feedback-e2e-over-synthetic]]), not offline sims.

**What shipped.**
- **0.2.35 (pre-session, already committed) — per-attempt WARNING escalation.** The (H) logging lever was already landed after the 24th-session closeout (`470201c`); it's what made this diagnosis possible.
- **0.2.36 — configurable Ollama timeout.** The hard-coded 90s per-call Ollama timeout became an options-flow field `ollama_timeout_seconds` (positive-int validated, string-digit coerced, default **180s** — codegen for complex charts regularly runs 60-90s so 90 sat near the fallback ceiling), threaded into both the planner and codegen client constructors. Existing installs without the field fall back to 180s via the options-normalization merge. `DEFAULT_OLLAMA_TIMEOUT_SECONDS` 90→180 as the coupled fallback.
- **0.2.37 — cross-sensor mean grounding fix (the packet-(H) headline).** `answer_grounding.py::_compute_mean` averaged only `inputs[0]`, so a two-sensor "average of the kitchen AND basement temperatures" claim was checked against a **single-sensor** reference → 4/4 `grounding_value_mismatch` → answer withheld (chart served correct, `answer_text` empty). Fix: for `len(inputs) > 1`, average ACROSS inputs on a shared 5-minute grid (resample + collapse-dupes + interpolate + dropna), faithfully mirroring ADR-0036 `align().mean(axis=1).mean()` reproduced in pure Python (grounding stays an independent drift-detector — no pandas on the HA side). Single-input unchanged; disjoint coverage → no reference → caveat, never a false contradiction. +5 tests; spec §5 updated.

**Diagnosis method (the interesting part).** Ran the e2e harness against the **deployed** 0.2.35 for e2e-11 only, then pulled `scripts/ha_logs.py` — the WARNING cascade showed all 4 attempts failing `grounding_value_mismatch` with a **byte-identical** stated value (the repair loop was powerless because the model kept re-computing the same *correct* value). Confirmed against live HA history: no single-sensor mean can land within the 0.05 tolerance of a correct two-sensor mean (basement-only 72.31 vs 72.78 = 0.47 off; kitchen-only 73.86 = 1.08 off). Installed pandas locally to compute the real `align()` truth and proved the pure-Python `_compute_mean` matches it to **6 decimals** on live + synthetic (full/partial/sparse/three-sensor/duplicate-timestamp) data.

**Verification.** Suite **488 passed / 4 skipped** (54 grounding tests incl. the 5 new; the isolinear_analysis helper tests un-skipped once pandas was installed locally). **Live proof:** Colin redownloaded 0.2.37 and re-ran e2e-11 on his card — it grounded: *"The average temperature of the kitchen and basement over the last day was 72.89 °F"*, matching the chart. **Arch-review subagent run: OK** (clean) — no invariant violations; #1 allowlist intact (recompute only reads delivered series); the pure-Python align mirror preserves grounding independence rather than coupling it; ADR-relevance judged defensibly spec-only (the change makes grounding *conform* to the already-decided ADR-0036 contract it was silently diverging from, not a new decision). No BDD (no user-facing contract shape change; the live card + unit tests are the proof).

**Deploy state.** `main` is **0.2.37, PUSHED** (`92a7429` timeout, `d162f7f` grounding). Integration-only — ships via HACS, **no worker rebuild**. Colin already redownloaded and confirmed live.

**Newly-visible finding (masked until now).** With `grounding_value_mismatch` gone, the same live run's repairs 2-3 surfaced `grounding_verdict_ambiguous`: *"longest matching label 'Average' differs from claimed verdict 'The average temperature was calculated.'"* The model attaches a spurious `verdict`+`rule` (band-label structure) to a plain descriptive mean that has no natural Yes/No or High/Low framing — a CODEGEN-PROMPTING gap, not a grounding bug (the check at `answer_grounding.py:615` is doing its job). Never seen before because every attempt used to die on value_mismatch at step 4, before reaching step 5's verdict containment. Recorded in [[isolinear-e2e11-sandbox-cascade]].

**Card-level legend re-scoped (open-queue (y)).** Colin asked whether the Pillow-era card-level legend (ADR-0027 D1 — a disclosure list *outside* the plot) still exists for the codegen path. Investigation: the whole spine (schema `legendItem`, `snapshot_assembly.py:632` which is renderer-agnostic, and the frontend `isolinear-card.ts:390+` disclosure UI) is fully intact and just never fed — `_build_worker_artifact_metadata` (codegen path) never copies `legend`/`summary` from `render_metadata`, unlike its Pillow sibling, and the codegen return-contract + render-result schema have no `legend` field yet. Three additive pieces sketched in the new research note `docs/research/codegen-card-level-legend.md`; open-queue (y) re-scoped from "prompt nudge for an in-image legend" to this richer already-built path.

**Next.**
1. **(cc) grounding_verdict_ambiguous on plain descriptive means** — a `_CODEGEN_PROMPT_RULES` rule that value/descriptive claims (mean/delta with no natural threshold) omit `verdict`/`rule` entirely, attaching them only when the question implies a band judgment. Concrete repro is in the 25th-session live log. Would stop e2e-11 burning 2 repairs on a non-bug.
2. **(y) card-level legend for codegen** — needs a decision on `kind:overlay`-vs-a-new-`computed` value (to match Colin's liked solid-line/dashed-computed convention) before a spec's contract can be written; see the research note's open sub-questions.
3. **(I) Promote ADR-0036 draft → accepted** — proof-gate met (e2e-18 PASS, and now e2e-11 grounds); held pending Colin's explicit OK.
4. Then (r) binary/timeline routing, (t) the >2-day tiering wall (small ADR), (F) cosmetics.

### 2026-07-12 (24th session) — Five reactive fixes 0.2.30→0.2.34, capped by ADR-0036 (draft): the in-sandbox analysis helper `isolinear_analysis.align()`

**Phase.** `HELPER SHIPPED + LIVE; the align/combine transcription-variance class is structurally fixed.` A reactive session driven by Colin's live card testing. Five fixes shipped and pushed (0.2.30→0.2.34), the last introducing ADR-0036 — the third rung of the idiom-over-prose ladder (prose → literal idiom → a callable inside the sandbox).

**What shipped.**
- **0.2.30 — D6 prune safety guard.** "are the kitchen and family room temperatures correlated?" rendered a DOOR timeline: the ADR-0028 D6 model prune, handed a `numeric_with_overlay` composition where `binary_sensor.kitchen_door`/`kitchen_ecobee_occupancy` noise-matched "kitchen", picked the door. Guard (`entity_resolution.py::_prune_composition_with_model`): when a numeric type-hint fired but the prune returns ONLY binary/state entities, reject it and fall back to the numeric subset. +2 tests.
- **0.2.31 — cross-math variance basin, ROOT-CAUSED.** The intermittent `runtime_error` that rotated across mean/delta/deviation is an entity-id `KeyError`: gemma builds a bare-list `pd.concat([...],axis=1)` (positional columns) then indexes it by entity_id. Pulled the CT103 worker logs (Colin-authorized) to establish the pattern, reproduced the actual traceback via the production codegen path. Shipped the entity-id-keyed-frame rule; deterministic mechanism proof + `evals/crossmath_frame_keying_gate.py` **2/40 → 0/40** KeyErrors. The packet's ORIGINAL framing — repair-intent-retention (open-queue (B)) — was investigated and **dropped**: its gate showed no separation (3/3 both arms), so per the 0.2.22 "hints must earn their keep" principle it isn't shipped; the eval stays as a documented negative result.
- **0.2.32 — render/repair phase labels.** The codegen generate/repair loop is non-streaming, so after "Planning chart…" the card's live slot held stale text and looked frozen through the longest phase. Added `RENDER_CHART_PHASE_LABEL` / `repair_chart_phase_label(n)` / `CHECK_ANSWER_PHASE_LABEL` pushed via the existing ADR-0025 sibling-poll `apply_live_reasoning` machinery (`set_render_phase` in `orchestration_store.py`, wired into `render_dispatch.py`). Colin confirmed the live updates animate. +2 tests.
- **0.2.33 — degenerate-answer guard.** "the average … was nan °F" reached the user: `run_grounding_check`'s degeneracy check only guarded a *claim's* value, but a plain aggregate emits an `answer_text` with no verdict claim → reached the "no claims → pass" branch unscanned. Added an answer_text tripwire (nan/inf/-inf/infinity whole-word + unfilled `{…}` template braces; `0.00` deliberately excluded — a genuine zero is valid) → repair, withheld on exhaustion. +5 tests. Spec §5(a) corrected (it had over-claimed this scan existed).
- **0.2.34 (ADR-0036, DRAFT) — in-sandbox analysis helper.** `worker/isolinear_analysis/__init__.py` (v1.0.0): `align(history_series, freq='5min')` → a DataFrame whose columns ARE the entity_id strings on a shared interpolated grid, raising a specific ValueError on degenerate inputs (never an empty/all-NaN frame). COPY'd into the image's system site-packages (the `-I` sandbox sees only system site); allowlisted as one curated module. The alignment/keying idiom retires from `_CODEGEN_PROMPT_RULES` in favor of an `align()` prescription + per-member one-liners (`mean(axis=1)`, column difference, `corr().iloc[0,1]`, `sub(mean(axis=1),axis=0)`); the rule text shrinks ~415 chars.

**Verification.** Suite **465 passed / 5 skipped** (the +1 skip is the pandas-gated helper test file in the pandas-less integration env; it's 17/17 under the eval env). ADR-0036 proof gate: unit tests 17/17 (incl. parity with the SEPARATE `answer_grounding` registry — grounding independence preserved); in-image `-I` import proven on the rebuilt CT103 image; `evals/analysis_helper_gate.py` (4 cross-math members × 6 runs × 2 arms) — **deviation 6/6 fired with the helper vs 4/6 with 2 repair-exhaustions on the idiom arm** (the live e2e-18 failure reproduced offline), adoption 24/24, no regression on mean/delta/correlation. **Arch-review subagent run: OK** — the helper adds no capability (pandas already allowlisted; no I/O), grounding independence is intact (the `answer_grounding` registry recomputes with pure-Python raw-timestamp logic, a genuinely different algorithm; the parity test is a drift-detector, not a shared code path), scope is minimal (one function), ADR-0036 is the correct record. No BDD (the eval gate is the proof artifact; no user-facing contract changed).

**Deploy state.** `main` is **0.2.34, PUSHED**, and BOTH halves are deployed: HA `installed_version = 1eafbfe` (confirmed via the update entity after Colin's redownload + restart), and the CT103 worker force-recreated to the ADR-0036 image (healthy; `docker exec isolinear-worker python -I -c "import isolinear_analysis"` → 1.0.0). This is the first worker-image rebuild since the split — done by scp'ing the `worker/` context to `/tmp` on CT103 and building there (no repo clone on the host; the compose stack is `/srv/compose`, and the `ollama` container also runs on 10.0.1.39).

**Live e2e verdict (deployed 0.2.34, `evals/e2e_runs/20260712T063227Z/`).** **e2e-18 (deviation — the ADR-0036 acceptance headline) flipped to a clean PASS** — a real per-sensor deviation series, no fallback. e2e-13/19/20 clean; the random regression sample (04/05/10/15/17) all clean with grounded answers. The first full-20 run (`…043352Z/`) had 6 fallbacks but 3 were transient `model_provider_connection_error` (Ollama contention — likely competing `ollama.ai_task` vision on the same GPU + my own eval load); those did not recur on the clean re-run.

**RESIDUAL — e2e-11 (mean) fails reproducibly (2/2), but as a SEPARATE class.** It is a sandbox-execution repair cascade: the served error `KeyError('history')` is the exhaustion *tail* of a 4-attempt chain (`repair_attempts: 3`), not the trigger. Extensive digging ruled out every input difference — the real planner chart_spec (captured live; 2 plain line series, identical structure), the "History"-in-title priming theory (18/18 clean with it), the history_series field shapes (10/10 clean faithful), and the model (the Ollama *container* logs show only `architecture=gemma4` loaded — codegen model = gemma4:e4b, what I reproduced against). The only un-replicated difference is the **worker sandbox's write/import/resource enforcement** — the same system_log batch carried `PermissionError: sandbox allows writes only to the fixed output path`, an error the permissive local `execute()` harness can never produce. ADR-0036 does not touch this (the helper's `align()` works fine for e2e-11 every offline run; it's a different failure class than the alignment transcription variance the helper fixes). Recorded in `[[isolinear-e2e11-sandbox-cascade]]`.

**Next.**
1. **(H) e2e-11 diagnosis — the concrete lever:** add per-attempt WARNING logging of each codegen error (code + `source_line`/traceback tail) inside the `render_dispatch` repair loop. The full cascade including attempt-0's trigger is currently DEBUG-only, and DEBUG is unreachable via `scripts/ha_logs.py` (system_log is WARNING+ only). With the escalation, re-run e2e-11 and read the trigger straight from system_log. Alternatively, route a repro through the REAL worker `/v1/render` (needs the SOPS worker token — Colin to supply/run).
2. **(I) Promote ADR-0036 draft → accepted.** The proof-gate headline (e2e-18 → PASS) is met and no verdict regressed; held at draft pending Colin's explicit OK (ADRs are immutable once accepted).
3. Then (r) binary/timeline routing, (t) the >2-day tiering wall (small ADR), (F) cosmetics (door-duration (x), the generic axis word/label, the awkward "Yes correlate" verdict phrasing), and the deviation-prompt claims-literal SyntaxError both helper-gate arms share (likely a series-valued claims attempt — a "claims are scalar-valued only" rule candidate).

### 2026-07-08 (23rd session) — Split deployed + spot-gated (0.2.28 live, behavior-preserving); open-queue (v) e2e-14 fixed; (cc) re-framed as a variance basin (0.2.29)

**Phase.** `SPLIT DEPLOYED, SPOT-GATED, AND EXTENDED.` The ADR-0035 step-1
split is live on HA (0.2.28) and gated behavior-preserving; the one hard
resolution failure (e2e-14, open-queue (v)) is fixed; and the cross-math e2e
"regression" is now understood as a variance basin rather than a fixed bug.

**Part 1 — the split is deployed and behavior-preserving.** Colin
HACS-redownloaded 0.2.28. Ran an 8-prompt e2e spot set (one per family plus the
cross-math trio) against the live instance → all 8 `complete`, captured to
`evals/e2e_runs/20260708T002741Z/` and judged by looking. **No non-cross-math
verdict degraded vs the 0.2.27 baseline** (`…20260707T171258Z/REPORT.md`):
e2e-01/06/09/10 unchanged, and **e2e-03 improved** — it now renders a legend, so
open-queue (y) is effectively closed. The accept gate ("no verdict may degrade")
is met. The split is confirmed a pure refactor at runtime, not just by
construction.

**Part 2 — the cross-math family is a variance basin, not a fixed regression.**
Last session's (cc) FAILs **e2e-12 (delta) and e2e-18 (deviation) both now PASS**
(grounded "1.31 °F" delta answer; a clean per-sensor deviation series), while
last session's (z) PASS **e2e-11 (mean) flipped to a Pillow `runtime_error`
fallback**. Pulled the CT103 worker logs (`docker logs isolinear-worker`): the
first codegen attempt throws `runtime_error` intermittently across ALL of
transport-004/006/007, each recovered by a repair on some runs and exhausted on
others. So the multi-sensor cross-math prompts share ONE flaky
codegen-runtime slip that rotates across whichever member draws the unlucky
temp-0 sample — exactly the "repair-chain intent erosion" the 20th session
diagnosed for (z). This is the strongest live motivation yet for the **(B)
repair-intent-retention** packet, which is now the cross-math family's real fix
(not a per-member chase). NOT a split defect.

**Part 3 — open-queue (v) e2e-14 fixed (0.2.29).** The cross-metric
temp-vs-humidity correlation. The 18th-session diagnosis ("kitchen humidity
fails to resolve to `sensor.kitchen_ecobee_humidity`") was WRONG. The REAL
approved allowlist — pulled non-destructively via the options-flow init
(`POST /api/config/config_entries/options/flow`, which returns the
`entity_allowlist` default) — carries `binary_sensor.kitchen_door` and
`binary_sensor.kitchen_ecobee_occupancy`. Both noise-match the bare word
"kitchen", so `select_prompt_entity_ids` always routes this prompt into the
`numeric_with_overlay` composition path. There, `_filter_numerics_by_type_hint`
**returned on the FIRST firing hint category**: the prompt hints both
"temperature" and "humidity", the temperature hint fired first, and every
humidity candidate was dropped from `numeric_matches` — BEFORE the overlay
composition assembled and therefore BEFORE the ADR-0028 D6 model-prune pass ran.
No model call ever saw humidity, so nothing could recover it, and the planner
correctly clarified that the required humidity sensor was missing.

**The fix (one function in `entity_resolution.py`):** union the target
device-classes across ALL firing type hints instead of returning on the first,
so a cross-metric prompt keeps every metric it names. The binary door/occupancy
noise still enters the composition candidate set, but the existing D6 model
prune (which fires because the candidates share the "kitchen" token) drops it —
live-proven 5/5 (D1+D6 against the real catalog → exactly temp+humidity). The
change is bounded to the deterministic pre-filter; invariants #1 (allowlist)
and #9 (kind→family routing) are untouched — the fix only widens which approved
numerics survive to the model, and the D6 prune + allowlist re-validation still
gate the final set.

**Verification.** Suite **456 passed / 4 skipped** (+2:
`CrossMetricTypeHintTests` — cross-metric survives the filter through the prune,
and a regression guard that a single-metric prompt still drops an incompatible
numeric noise match); `evals/composition_membership_prune.py` PASS against live
gemma; the e2e-14 resolution repro 5/5 correct. Inline invariant review OK; arch
subagent not spawned (bounded change on the accepted ADR-0028/0024 path,
available on request). New diagnostic `scripts/repro_e2e14_resolution.py`.
Integration-only, ships via HACS, NO worker rebuild, no new ADR.

**Deploy state.** `main` is **0.2.29, PUSHED**. HA runs 0.2.28 (deployed +
spot-gated this session). A 0.2.29 redownload deploys the e2e-14 cross-metric
fix — verify through the card that "is the kitchen temperature correlated with
the kitchen humidity" resolves both sensors instead of clarifying (live-proven
at the resolution seam; not yet exercised through the deployed pipeline).

**Next.** HACS 0.2.29 redownload + card verify e2e-14. Then the **(B)
repair-intent-retention** packet (the cross-math variance basin's real fix — the
repair task must preserve every computed/derived series + the answer_text
emission from the previous attempt; eval-gate with/without arms like 0.2.26).
Then (r) binary/timeline routing, (t) the >2-day tiering wall (needs a small
ADR), (x) e2e-09 zero-duration door intervals, and the housekeeping flagged for
Colin (mixed_chart dead code; ADR-vs-spec on the re-plan spec; the CLAUDE.md-9
vs ARCHITECTURE.md-12 two-list reconciliation). ADR-0035 step 2 (retire
first_real_vertical_slice) remains a bounded packet on the deployed split.

### 2026-07-07 (22nd session, Fable) — The 0.2.27 e2e verdict recovered + completed ((z) fixed; NEW (cc) regression), and ADR-0035 demolition step 1 executed: the god module is split (0.2.28)

**Phase.** `DEMOLITION STEP 1 DONE.` `job_orchestration.py` (8,335 lines, 44%
of the integration) is split into seven seam modules behind a green suite —
seven behavior-preserving commits, each independently landable, the
2026-07-02 purge playbook applied to the post-purge residue exactly as
ADR-0035 §5.1 prescribed. Same session: the interrupted 21st session's live
e2e run against 0.2.27 was recovered from disk, completed, and judged.

**Part 1 — the 0.2.27 live e2e verdict (`evals/e2e_runs/20260707T171258Z/REPORT.md`).**
The 21st session (whose connection died before reporting) had completed
e2e-01…11; its artifacts were intact in `…061751Z/`. This session ran
e2e-12…18 fresh and judged all 18: **11 PASS / 4 PARTIAL / 3 FAIL** (0.2.24
baseline 12/3/3). **(z) is CONFIRMED FIXED in the mode** — e2e-11 draws a true
computed mean series. ADR-0033 bands, rolling mean, and a grounded Pearson
verdict (r=0.08) are clean; the 0.2.26 family-degrade rule held (no 2-D grid).
**NEW open-queue (cc):** e2e-12 (delta) and e2e-18 (deviation-from-mean) —
the two multi-sensor cross-math transforms — **reproducibly** fail at codegen
runtime (re-run confirmed), exhaust the 3 repairs, and fall back to Pillow raw
lines with empty answers. Both were PASS on 0.2.24 → candidate 0.2.25–0.2.27
regression. The sandbox traceback is only in the CT103 worker logs; the (cc)
debugging packet pulls it and decides idiom-gap vs re-plan side effect. This
is also the strongest live case for the repair-intent-retention packet.

**Part 2 — the split (spec `docs/specs/job-orchestration-split.md`, accepted).**
Measured ground truth first: the production import surface is 8 symbols in 2
modules (untouched); tests/evals reference ~51 symbols (compat re-export block
in the facade); SIX patch sites (two attribute-writes found by grep, four
multi-line `patch.object` found by the suite failing exactly as designed —
the correction is recorded in the spec). Seven commits, dependency-ordered,
suite 454/4 green after each: `orchestration_contracts` (validators + schema
paths, 603) → `orchestration_store` (record plumbing + lookups + locks +
ADR-0025 slots, 678) → `snapshot_assembly` (appenders + sanitizers + artifact
glue, 995) → `history_dispatch` (window math + D9 epoch-ms, 284) →
`entity_resolution` (D1/D2/aliases/composition + family/envelope routing,
900) → `planning_pipeline` (plan/replan loop, 652) → `render_dispatch` (codegen
loop + worker dispatch + Pillow fallback + overlay bands + transport, 2,117).
The facade keeps setup/gates, the five WS handlers, deferral +
pending-selection, the drivers, and response envelopes (2,671 lines).
Downward-only imports, acyclic; def-parity vs base proven (zero defs
dropped/added). Amendments vs the plan (recorded in the spec): the ADR-0025
model-call plumbing landed in orchestration_store (D2 selection is a sibling
consumer); `_artifact_series`/`_artifact_title` landed in snapshot_assembly.

**Verification.** Suite **454 passed / 4 skipped** after every one of the
seven commits; evals `codegen_generation_path` + `model_authored_analysis`
PASS on the split code (live gemma + CT103 worker); import-graph + layer-rule
checks green; def-parity machine-verified. No BDD (no contract change — the
spec records why).

**Architecture review — RUN this time.** Colin noticed the arch-review
subagent had been self-skipped as "bounded" for ~4 sessions and asked for it.
Spawned fresh-context on the split diff: verdict **OK** — it byte-diffed all
204 moved functions (0 body changes — stronger than the AST def-parity),
confirmed the secret sanitizers (`_safe_*` + `FORBIDDEN_*` regexes) moved
together so none is reachable by a path that bypasses sanitization, and found
no data-boundary weakening and no validator-ordering change. Process lesson
saved to [[feedback-isolinear-arch-review]]: don't self-exempt this pass.
Then **audited `docs/ARCHITECTURE.md`** (`df8d6a6`): invariant-#8 clean (every
claim traces to an accepted ADR or code — no map-only decisions), but 4 claims
had drifted (repair-default "still 1"→3; "ADR-0035 forthcoming"→accepted; "16
validators"→13; the "newer wins" tie-break reframed into an explicit
derived-view contract). **Open for Colin:** CLAUDE.md's 9 enforced invariants
and ARCHITECTURE.md's 12 "load-bearing decisions" are two separate numbered
lists with no cross-reference — the real duplication to reconcile (lean:
make the 12 an explicit superset citing which rows are the enforced 9).

**Deploy state.** `main` is **0.2.28, PUSHED** (`origin/main` at `df8d6a6`;
the 9 split commits + the ARCHITECTURE.md audit). HA runs 0.2.27 (live-verified
this session). A 0.2.28 HACS redownload ships the split — behavior-identical by
construction; the **e2e spot set** (one per family, judged against the 0.2.27
baseline report, no verdict may degrade) is the final accept gate after deploy.
CT103 `:dev` worker unchanged.

**Next.** Colin: push call → HACS 0.2.28 → e2e spot set. Then (cc) worker-
traceback debugging + the repair-intent-retention rule (eval-gated like
0.2.26); (v) e2e-14 resolution gap (Opus); then (r)/(t)/(y)/(x)/(s)-confirm/
(w)-polish. ADR-0035 step 2 (retire first_real_vertical_slice, ~19 refs) is
now a bounded packet on top of the split.

### 2026-07-07 (20th session, Fable) — Finished open-queue (u)+(m): re-plan default ON with a real fresh-sample guarantee (0.2.27); diagnosed (z) as a variance basin

**Phase.** `STRUCTURAL RETRY ON BY DEFAULT.` The bounded planner re-plan loop
ships enabled (reader default 1) with its full config surface, the codegen
repair cap defaults to the proven live value (3), and — the session's key
finding — the loop now actually works live: re-plan attempts sample at a
nonzero temperature, because at the planner's default temperature 0 a
"re-sample" was a byte-identical repeat of the rejected plan.

**(u) finished (0.2.27).** Config surface: `max_planner_replan_attempts` typed
field + non-negative validation in `config_schema.py`; options-flow integer
field + string-digit coercion in `config_flow.py` beside the codegen tunables.
Defaults: re-plan reader 0→1; bundled (m) `max_codegen_repair_attempts` 1→3
(reader + `default_options_data`). One failure-path call-count assertion
updated to the exhaustion count.

**The fresh-sample fix (the live proof's finding).** The planner's structured
pass runs at `temperature: 0` (near-greedy). Probed live on a frozen request:
3/3 byte-identical planner results — so the 0.2.25 slice-1 loop ("plain
re-sample", same request) was a live no-op; its unit tests passed because stub
planners vary where greedy gemma does not. Fix: re-plan attempts (attempt ≥ 1)
pass `temperature=_PLANNER_REPLAN_TEMPERATURE` (0.7) through `plan_chart`
(additive kwarg; `_call_planner_with_optional_reasoning` degrades unknown
keywords one at a time, keeping `temperature` over the presentational
`on_reasoning`); the same frozen request then yields 3/3 distinct plans.
Constrained decoding still enforces the schema on every attempt; the first
attempt keeps the reproducible temp-0 default.

**Live proof (spec Proof req #4, `evals/planner_replan_live_proof.py`, honest
two-part record).** (1) The fresh-sample property proven live (the PASS gate).
(2) The e2e-18 duplicate-source tail did NOT reproduce in 16 live
production-path runs of `_record_model_provider_plan` (exact live prompt +
entity set, the 0.2.24 hardening clause marker-stripped, reader default
exercised) — 16/16 first samples validated; recorded as tail-not-reproduced
(a rare variance region), not spun as recovery. The eval is resumable and will
headline a live recovery if one ever fires.

**Scenario E deviation (flag for Colin).** `mixed_chart_composition_unsupported`
is dead code: since `372a437` (2026-06-24, multi-numeric overlays) every
numeric+state set routes to `time_series_overlay`, so the "mixed" family is
unreachable through `_resolve_render_family`. The Scenario-E test pins the
loop's non-trigger discipline at the `_plan_once` seam instead. Decide: delete
the defensive gate, or keep it documented-unreachable.

**(z) e2e-11 mean-intent DIAGNOSED — not structural.** Repro
`scripts/repro_e2e11.py` (production codegen path, live gemma, execution-truth):
14 generations across synthetic + REAL HA 24 h history, the live planner's
faithfully-reproduced framing (phase-1 sampled: raw-history title + "trends"
summary), and both the 0.2.24 and current rule sets — ZERO scalar lines. The
mode is a true computed mean series (real data: 72.48 °F, std 0.38, between the
raw bands) + grounded answer_text. The live 18th-session scalar render was one
unlucky temp-0 sample; the plausible mechanism is **repair-chain intent
erosion** — observed once directly (a two-repair chain kept the mean series but
dropped answer_text), and the live run's 191 s is repair-consistent (0.2.24
rules hit repairable first-attempt slips 3/3 on real data). **Recommended next
packet: a repair-intent-retention rule** (the repair task must preserve every
computed/derived series and the answer_text emission), eval-gated like 0.2.26.
Bonus hardening: the alignment-gate `derived_mean` judge now has a std floor (a
flat axhline at the mean previously PASSED as "clean"). Findings:
`evals/prompts/e2e11_mean_intent_findings.md`. (z) is likely-fixed in the mode
on 0.2.26+ — confirm on the next live e2e run.

**Verification.** Suite **454 passed / 4 skipped** (+2); evals
`codegen_generation_path` + `model_authored_analysis` PASS; BDD-evidence review
OK (Scenario A's INFO-log Then-clause is code-pinned + captured by the live
eval's `replan_log` plumbing, not unit-asserted — noted); inline invariant
review OK (no schema/service/sandbox/data-boundary change; the temperature
param is a call option on the existing planner client; re-plan re-sends the
already-projected request; arch subagent not spawned — bounded change on the
accepted planning path, available on request).

**Deploy state.** `main` is **0.2.27** (pushed). HA runs 0.2.24; one HACS
redownload deploys 0.2.25+0.2.26+0.2.27 together (re-plan loop live-enabled +
heatmap family-degrade + promoted defaults). Integration-only; NO worker
rebuild.

**Next.** HACS 0.2.27 redownload + live e2e re-run (watch for INFO "recovered a
valid plan" lines and e2e-11's mode); the repair-intent-retention packet; (v)
e2e-14 resolution gap (Opus); then (r)/(t)/(y)/(x)/(s)-confirm. Whenever
ADR-0035 demolition starts, hand the job_orchestration.py split PLAN to Fable.

### 2026-07-07 (19th session) — Fixed open-queue (w): the e2e-15 heatmap garbage, "ship simple" (0.2.26)

**Phase.** `HEATMAP GARBAGE FIXED (family-degrade rule).` The last hard live
e2e FAIL that wasn't a known wall — e2e-15's nonsense heatmap render — is
closed with a single codegen prompt rule, eval-gated 3/3 vs 0/3 against live
gemma. No new render family, no worker rebuild, no new ADR.

**Root cause (repros `scripts/repro_e2e15{,_planner,_planner_fix}.py`).** The
single-numeric ADR-0023 envelope has NO heatmap family, so the planner
deterministically (6/6) routes "Show a heatmap … by hour of day and day" to
`chart_type: histogram` — emitting the exact title on the live garbage render
("Kitchen Temperature Distribution Over the Last Week"). The ADR-0034 conduit
then hands codegen a `user_request` that says "heatmap", and codegen tries to
honour BOTH the histogram chart_spec AND the heatmap word → the live 1/2-bar,
epoch-ms nonsense (accept≠quality; sandbox accepted it). The counterfactual arm
showed gemma CAN render a real calendar heatmap, but 2/3 runs died on a
repair-proof stray-quote emission (`transform=ax.transAxes')`) that temp-0
regenerates every repair.

**Decision (Colin, 2026-07-07 — "ship simple").** Two options were on the
table: (A) render a real temporal heatmap (planner routes heatmap→`time_series`,
codegen pivots — the routing patch pre-validated 3/3) or (B) degrade the ask to
the histogram the planner already picks. Colin chose **B**: the temporal
heatmap is a niche ask, and B keeps the WORD "heatmap" reserved for the future
spatial/floorplan renderer (open-queue (c)). A temporal calendar heatmap, if
ever built, becomes its own NAMED family — not an overload of "heatmap".

**The frame that made B one rule, not three.** The bug isn't "wrong viz" — it's
codegen overriding the planner's chart FAMILY via the `user_request` conduit,
violating invariant #9 (the model never chooses `chart_type`). Chart family is
the planner's job; `user_request` drives only the COMPUTATION within it. A
heatmap is a family, so codegen must not invent one.

**Shipped (0.2.26).** One `_CODEGEN_PROMPT_RULES` sentence: render only
line/histogram/bar; never draw a 2-D heatmap/matrix/grid (no `seaborn.heatmap`,
`pcolormesh`, `imshow`, `hist2d`); a single-sensor "heatmap by hour and day"
degrades to a histogram of that sensor's values; `user_request` may change WHAT
is computed, never the family. Spec `model-authored-analysis` §2 updated;
regression test `FamilyDegradePromptRuleTests`.

**Verification.** New gate `evals/heatmap_rule_gate.py` (production codegen
path, the live histogram chart_spec + heatmap `user_request`, marker-gated
with/without arms, execution-truth judge = a clean 1-D histogram not a 2-D
QuadMesh/image): **with-rule 3/3 clean histograms** (8 bins, 67.6–75.4 °F,
first attempt each), **without-rule 0/3** (all drew the 2-D grid — the live
e2e-15 failure reproduced). Suite **452 passed / 4 skipped** (+1). Inline
invariant review OK: prompt text only; reinforces invariant #9; no
schema/service/sandbox/data-boundary change; `user_request` still never crosses
to the worker. Arch-review subagent not spawned (bounded prompt-level change on
the accepted ADR-0034 path), available on request. No BDD scenario added — the
eval gate is the proof artifact for a prompt-rule change (no user-facing
contract surface changed).

**Deploy state.** `main` will be **0.2.26** once committed (this closeout).
Integration-only (prompt text) — ships via HACS, NO worker rebuild (the conduit
never crosses the data boundary; CT103 `:dev` worker unchanged). HA runs 0.2.24;
a 0.2.26 HACS redownload deploys this fix (and the dormant 0.2.25 re-plan code).

**Next.** Finish open-queue (u) (config surface + default flip with (m) +
Scenario-E + live proof); (v) the e2e-14 entity-resolution gap (Opus); (z)
e2e-11 mean-intent (Fable-shaped); (x) e2e-09 door-answer duration; (y) e2e-03
legend; confirm (s) histogram-unit before closing. NEW open-queue items from
this session: (aa) the codegen stray-quote `transAxes'` guard-branch emission
(latent, could resurface on other prompts); (bb) multi-sensor
"heatmap-of-correlations" degrades to time-series lines not a histogram
(coherent, weaker — logged). Whenever ADR-0035 demolition starts, hand the
job_orchestration.py split PLAN to Fable.

### 2026-07-06 (18th session) — Verified 0.2.24 live (e2e targets flipped), landed the open-queue (u) re-plan anchor, root-caused e2e-14, fixed the harness diagnostic gap (0.2.25)

**Phase.** `0.2.24 VERIFIED LIVE; PLANNER RE-PLAN ANCHOR LANDED (opt-in).` The
17th session's alignment + planner-satisfiability fixes are confirmed on real HA
data, the biggest remaining planner-variance tail has a bounded structural fix
in place (dormant, opt-in), and the one hard live failure (e2e-14) is
root-caused to entity resolution, not the planner.

**Live e2e verification (0.2.24, 18 prompts, gitignored `evals/e2e_runs/20260706T205049Z/`).**
Judged **12 PASS / 3 PARTIAL / 3 FAIL** (prior run 8/5/5). The three testable
0.2.24 targets all flipped: **e2e-12** (Kitchen−Basement delta series + computed
"1.25 °F"), **e2e-13** (real Pearson 0.13 — on an isolated re-run
`…220549Z`; the batch run hit a `model_provider_connection_error` transport blip
→ Pillow), **e2e-18** (per-sensor deviation series; was the duplicate-source
planner rejection the satisfiability rule fixed). **e2e-11** improved (the
union-index alignment artifact is gone) but the model draws a horizontal scalar
average line, not a computed mean series (transform intent unmet → open-queue (z)).
Other findings: **e2e-15 heatmap emits garbage codegen** (epoch-ns x-axis, 1/2
y-values — open-queue (w)); **e2e-16 histogram unit is now correct** (open-queue
(s) likely fixed); **e2e-09 door** renders a real step track but the answer_text
has zero-duration intervals (open-queue (x)); **e2e-03** lacks a legend
(open-queue (y)).

**e2e-14 root cause (new `scripts/repro_e2e14.py`).** The cross-metric
temp-vs-humidity correlation fails at `model_provider_planner_not_chart_spec_ready`
because entity resolution discloses ONLY the temperature sensor; the planner then
CORRECTLY returns `clarification_needed` ("sensor.kitchen_ecobee_humidity … is
required"). Disclosing both sensors makes the planner plan the °F-vs-% correlation
fine. So this is an **entity-resolution** gap (the prompt's "kitchen humidity" fails
to resolve to `sensor.kitchen_ecobee_humidity`, friendly name "Kitchen ecobee
Humidity"; "kitchen" also noise-matches three temp sensors), NOT a planner or
re-plan bug — recorded as open-queue (v). This directly validated the (u) design
boundary below.

**Open-queue (u) — bounded re-plan on validation failure (anchor, 0.2.25).**
Spec + BDD + evidence + implementation. `_record_model_provider_plan` now wraps a
renamed `_plan_once` in a bounded re-plan loop over `_PLANNER_REPLAN_TRIGGER_CODES`
= {`invalid_model_provider_chart_spec` (e2e-18's class), `invalid_planner_result`},
re-invoking the planner with the same request + re-running the existing gates,
keeping the first plan that validates; the result carries `planner_replan_attempts`.
**Reader default is 0 (opt-in)** — the landing is purely additive, so the full
suite stays green and no default behavior ships. It deliberately **excludes**
`model_provider_planner_not_chart_spec_ready`: after `validate_planner_result_contract`,
that code always means a legitimate `clarification_needed`/`cannot_resolve`, so
re-planning it would override the model's correct choice (exactly the e2e-14 case).
Slice-1 is a plain re-sample; corrective re-plan (feed the error back) is tranche 2.
**Remaining:** config surface, flip default 0→1 (with (m)), Scenario-E test, live
e2e-18 recovery proof. ADR-vs-spec is flagged for Colin (treated as spec-level,
mirroring ADR-0030's repair loop; no new service/store/schema).

**Harness diagnostic fix.** `evals/e2e_pipeline_harness.py` overwrote `snapshot`
each poll, discarding the streamed selection/planning reasoning (ADR-0025) — the
only reachable "why" for a planner-stage failure. It now accumulates distinct
reasoning across polls → `<id>_reasoning.txt` + manifest `reasoning_tail`/
`reasoning_stages`. (The definitive planner clarification text still lives behind
the deliberate card-suppression; surfacing it is a small integration-side
follow-up.)

**Verification.** Suite **451 passed / 4 skipped** (+5 re-plan tests). BDD-evidence
review (inline) OK — Scenarios A–D carry raw pytest output; Scenario E + the live
proof are honestly flagged pending in the evidence file. Inline invariant review
OK: the re-plan loop reuses the existing validation gates and re-sends the
already-projected planner request (no new data crosses any boundary), touches no
schema/sandbox/service, and is default-off; a fresh-context architecture-review
subagent was not spawned (a bounded change on the accepted planning path),
available on request. **Accepted ADR-0035** (README + `docs/ARCHITECTURE.md`
synced).

**Deploy state.** `main` will be **0.2.25** once pushed (this closeout). 0.2.25
ships **no default behavior change** (re-plan default-off; the harness/scripts/docs
are non-integration), so no HACS redownload is required to stay current — HA is on
0.2.24 (confirmed in the run manifest). The CT103 `:dev` worker is unchanged.

**Next.** Finish (u) (config surface + default flip with (m) + Scenario-E + live
proof); (v) the e2e-14 resolution gap (Opus-executable); (w) heatmap and (z)
e2e-11 mean-intent (both Fable-shaped — see [[isolinear-model-choice-by-packet]]);
(x) door-answer duration bug; (y) e2e-03 legend; and whenever the ADR-0035
demolition starts, hand the job_orchestration.py split PLAN to Fable.

### 2026-07-06 (17th session) — Closed open-queue (q): the analysis layer fires live (ADR-0034 conduit) + fixed the quality bugs it exposed + reset architecture tracking

**Phase.** `THE ANALYSIS LAYER FIRES LIVE.` The 16th session's headline gap —
the model-authored analysis layer collapsing to raw plots with empty answers on
every transform/correlation/question prompt — is closed. ADR-0034 (accepted,
pushed) routes the user's request to the codegen model; the live e2e re-run
(0.2.23) shows answers computing and transforms plotting. Firing then exposed a
second tier of codegen-quality bugs that the silence had masked (accept≠quality),
two of which were fixed the same session (0.2.24). The chart-rendering and
analysis paths are now both live-proven; the remaining work is deployment
confirmation, planner-variance robustness, and the v0.3 direction (ADR-0035).

**ADR-0034 — the analysis-intent conduit (0.2.23, accepted + pushed).** Diagnosis
(design-first, Fable) established the gap was STRUCTURAL, not model capability:
the codegen payload never carried the user's prompt (its task was "render the
supplied ChartSpec"), the answer rule keyed on "if the prompt asks a question" — a
prompt the codegen model was never shown (dead code), the 0.2.19 grounding rule
hard-instructed raw-line plotting, and the planner was told analysis is
unsatisfiable (reproduced live: gemma refused the heatmap as *"I cannot generate a
true heatmap … using the available chart types"*). A production-path probe
(`evals/analysis_intent_probe.py`, execution-truth judging on data with known
analytics) measured the fix: **baseline 0/12 fired vs the intent arm 12/12.**
Implementation: `generate_chart_code`/`repair_chart_code` take a bounded
`user_request` (a generation-time argument that NEVER enters the render request
crossing to the worker — test-asserted); the codegen task is reframed to "fulfill
user_request"; the plot rule becomes default-with-a-compute-exception (raw-line
plotting stays the default, the exception computes a derived series when the
request asks for analysis); the answer rule keys on `user_request`; a planner rule
declares analysis prompts satisfiable (plan one series per input entity, generated
code does the math). Integration-only, no worker/frontend rebuild.

**Live e2e re-run (0.2.23, 18 prompts, `evals/e2e_runs/20260706T172905Z/`): the
analysis layer FIRES.** Judged 8 PASS / 5 PARTIAL / 5 FAIL (2 FAILs are the
unchanged known walls e2e-04 tiering, e2e-14 planner). Answers compute: e2e-06
"The average kitchen temperature over the last week was 70.84°F", e2e-09 door-open
duration, e2e-08 humidity delta. Transforms plot: e2e-11 a derived cross-sensor
mean line, e2e-17 a genuinely smooth rolling mean (was imperceptible). e2e-09
(binary door) went from an empty degenerate-axis line to a correct step track +
duration answer — the conduit told codegen it was a binary-state duration
question. e2e-15 heatmap no longer hard-refuses at the planner (satisfiability
rule) though it degrades to a Pillow histogram.

**Two Fable-shaped follow-ups the run exposed (0.2.24, pushed).**
1. **Irregular-series alignment (e2e-11/12/13 root).** Cross-series math on
   disjoint per-entity timestamps produced a union-index mean spiking ABOVE both
   inputs (impossible for a true mean), an empty "nan °F" delta, and a "no common
   timestamps" correlation (the 8th-session `pearson_r` exact-intersection gap,
   live). Root cause: the production rules carried the benchmark's D9 epoch-ms
   lesson but never its *other* data-loading lesson — "sampling is IRREGULAR per
   entity; resample/align before combining" — which had only lived in the
   benchmark's own system prompt. New `evals/alignment_rule_gate.py` (genuinely
   irregular data, execution-truth judges) reproduced all three offline (0/6). A
   prose-ordered rule only reached 2/6 — gemma scrambled the order and `.dropna()`'d
   the raw union frame (disjoint indexes → every row deleted → all-NaN). The shipped
   rule bakes the order into one literal per-entity idiom
   (`Series(...).resample('5min').mean().interpolate()`, combine only after): **9/9
   clean vs 0/6.** This is the ADR-0033 axvspan lesson generalized — a floor model
   follows a copyable code idiom where it scrambles an equivalent prose ordering.
2. **e2e-18 `invalid_model_provider_chart_spec`.** A planner variance tail: a
   sample plans the computed result ("Deviation") as its own series, and constrained
   decoding — whose `source.entity_id` enum holds only approved ids — forces it onto
   an already-used entity → the duplicate-series-source contract check rejects it
   (the 0.1.37 relabel-reuse class through a new door). The satisfiability rule now
   prohibits planning the computed result as a series; re-check (deviation ×3,
   heatmap ×2, cross-metric ×2) → 7/7 chart_spec_ready + contract-valid.

**Architecture-tracking reset (Colin: "I can't track 34 ADRs").** Wrote
`docs/ARCHITECTURE.md` — the current-state map (the spine as one annotated request
path with module + ADR pointers per stage, the 12 load-bearing decisions, a
weight-honest component table naming `job_orchestration.py` the 8.2K god module, a
"not current architecture / demolition targets" section). `CLAUDE.md`'s doc map
points at it; it syncs at `/closeout`. Archived superseded ADR-0004 (numbers never
renumber). Drafted **ADR-0035** (v0.3 north star: the product is saved,
re-runnable analysis code refreshed model-free, plus the sequenced demolition plan
— split `job_orchestration.py`, retire the `first_real_vertical_slice` gate, shrink
ChartSpec to the intent contract ADR-0034 already declares, retire the Pillow
histogram/aggregate families once the harness proves codegen coverage). ADR-0035 is
DRAFT awaiting Colin — it's the direction decision, his call.

**Verification.** Suite **446 passed / 4 skipped**; evals `codegen_generation_path`
+ `model_authored_analysis` PASS; intent probe 12/12, alignment gate 9/9 vs 0/6,
planner re-check 7/7. Inline invariant review OK (all changes are prompt text +
one generation-time argument; `user_request` never crosses to the worker
[test-asserted]; no schema/service/sandbox/data-boundary change; the
duplicate-source contract check still gates every spec). Arch subagent not spawned
(bounded prompt-level changes on the accepted codegen path), available on request.

**Deploy state.** `main` is **0.2.24, PUSHED** (0.2.23 conduit + 0.2.24
alignment/planner fixes). HA was HACS-updated to **0.2.23** for this session's live
e2e run; **it needs a 0.2.24 redownload to deploy the alignment + planner-hardening
fixes.** No worker rebuild (the conduit never crosses the data boundary; the CT103
`:dev` worker is unchanged from the 16th session). Next: deploy 0.2.24 + a
confirming harness re-run (expect e2e-11/12/13/18 to flip), then open-queue (u)
re-plan-on-validation-failure, (m) repair-attempts, (r) timeline routing, (t) the
tiering wall — and Colin's decision on ADR-0035.

### 2026-07-06 (16th session) — Open-queue D + E: retired the bare-° rule (eval-gated, 0.2.22) and built the Claude-judged live e2e harness — which proved the model-authored analysis layer doesn't fire live

Colin picked open-queue **(o)** and **(p)**. Both shipped; the harness (E) then
did exactly what it was designed to do — caught accept≠quality failures that
synthetic backend checks miss. `main` is **0.2.22**, **commit-only** (not
pushed). HA still runs 0.2.20; the CT103 `:dev` worker was rebuilt this session
and carries a worker-side fix live.

**(D) Retired the bare-non-ASCII codegen prompt rule (0.2.22).** The 0.2.13 rule
("never use `°`/`%` as a bare Python token") was failure-driven; the 0.2.17
unit-grounding rule (model reads the unit from `history_series[i]['unit']`, a str
variable) keeps `°` out of bare literals structurally, and 0.2.14 `source_line`
recovers the class if it recurs. The existing `evals/codegen_reliability.py`
can't test this — it mirrors stale packet-5 rules and ASCII `degF` units, so the
`°` class can't even trigger. New `evals/codegen_rule_gate.py` drives the
**production** codegen path (real `generate_chart_code`/`repair_chart_code`, the
real `_CODEGEN_PROMPT_RULES` and `_codegen_request_view` projection) with
production-shaped `°F`/`%`-unit `ts_epoch_ms` data + ADR-0033 `derived_intervals`,
6 cases × with/without the rule × 3 runs, against live gemma4:e4b + a live worker.
**36 runs, ZERO bare-non-ASCII incidents in either arm (both 18/18 accepted).**
The rule gated nothing, so it's dropped; findings + results committed as
evidence. Integration-only, ships via HACS.

**(E) Built the Claude-in-the-loop live e2e harness `evals/e2e_pipeline_harness.py`.**
It drives the REAL card path — `isolinear/v1/job/start` + `job/snapshot` polling
over the HA WebSocket API, the same commands the card sends — for a fixed prompt
set against live HA + worker + gemma, captures the served PNG (from
`chart.image_url`) plus structured metadata (`render_path`,
`render_fallback_reason`, `answer_text`, `answer_verification`, failure codes,
phase timeline) into gitignored `evals/e2e_runs/<ts>/` with a `REPORT.md`
scaffold. **No programmatic assertions** (Colin's scope): Claude reads the PNGs +
manifest and judges each case by looking.

**Two bugs the harness found on its first run (vs live 0.2.20):**
1. **Worker HTTP 500 on off-contract model metadata (fixed, worker-side).** A
   generated non-string `render_metadata.warnings` entry made the worker's OWN
   `validate_contract("render-result", …)` raise, which propagated as an HTTP
   500 — the integration treats that as an unrepairable transport fault and falls
   back to Pillow with ZERO repair attempts. The same trap applies to
   model-stringified claim `value`s (`'3.0°F'`, measured in the 8th-session
   benchmark). Fix in `worker/isolinear_worker/codegen_sandbox.py`:
   `_normalize_render_metadata` coerces every model-supplied field to its contract
   type (`_coerce_string_list`; off-type `title`/`x_min`/`x_max` fall back);
   `_coerce_claims` sanitizes each claim (plainly-numeric string `value`
   converted, otherwise the claim is dropped → the answer surfaces with the
   unverified caveat downstream, never a fabricated value); and a residual leak
   degrades to a structured, repairable `invalid_render_metadata` failure inside
   the normal `200` flow instead of raising. Also allowlisted
   `matplotlib.patches`/`lines`/`ticker`/`colors` (exact-match, same pure-plotting
   trust tier as `matplotlib.dates`): the ADR-0033 legend hint "e.g. a Patch"
   steered every gemma generation to `import matplotlib.patches`, burning 1–2
   repair attempts on `import_not_allowlisted`. This is worker-side — I rebuilt
   `isolinear-worker:dev` on CT103 and force-recreated the compose service
   (healthy; `_coerce_claims` + `matplotlib.patches` verified in-container).
2. **The >2-day state-overlay tiering wall** (open-queue (t), see below).

**Then Colin asked to expand the prompt set** — humidity/`%`, a state timeline, a
renderable short-window overlay, transforms, correlation, heatmap, histogram,
smoothing → **18 prompts** — and authorized deploying the worker fix + a full
live run. **Second run (18 prompts, worker fix live, HA 0.2.20): 8 PASS / 2
PARTIAL / 8 FAIL, zero Pillow fallbacks** (the worker fix held; e2e-01 flipped
Pillow→codegen).

**HEADLINE FINDING — the model-authored ANALYSIS layer does not fire on the live
floor model (open-queue (q)).** Every transform / correlation / question prompt
collapsed to plotting the RAW input series with an analysis-flavored title and an
EMPTY `answer_text`/claims: the average of two temps (e2e-11) plotted both raw
lines; "how much warmer is the kitchen" (e2e-12) plotted two raw lines with no
delta and no answer; "are they correlated?" (e2e-13) plotted two raw lines titled
"…Correlation" with no coefficient or scatter; deviation-from-average (e2e-18)
plotted raw lines, not deviations; rolling average (e2e-17) showed imperceptible
smoothing; the plain answer question (e2e-06) returned an empty `answer_text`.
Cross-metric temp/humidity correlation (e2e-14) and the heatmap (e2e-15) failed
even earlier, at the planner (`model_provider_planner_not_chart_spec_ready`). So
the ADR-0031 tranche-1 answer + transforms capability — marked "shipped" but
proven only by hand-fed eval prompts — does NOT happen end-to-end through the
real planner + gemma4:e4b. This is the gap between Isolinear's "data-analysis
assistant" identity and its live behavior, and the biggest follow-up.

**WIN — ADR-0033 overlay bands proven live end-to-end at short window (e2e-10).**
"Show the kitchen temperature and when the AC was running today" rendered a
kitchen `°F` line + shaded cooling bands drawn as `axvspan`, no state series
drawn as a line — the exact 0.2.21 fix, on the real card→planner→overlay→codegen
path. e2e-04 (the same overlay over five days) failed only on the tiering wall,
not on ADR-0033.

**Secondary render bugs.** Binary/timeline entity renders EMPTY through codegen
(e2e-09, open-queue (r)): `binary_sensor.kitchen_door` was drawn as an empty
numeric line with a degenerate multi-year x-axis (2024→2028) — codegen has no
timeline handling, so a state entity that reaches it produces nothing (invariant
#9 says these route to a raw-states step track). Histogram misplaces the unit
(e2e-16, open-queue (s)): "Density (°F)" on the y, "Value" on the x — the `°F`
belongs on the x-axis.

**Verification.** Suite **437 passed / 4 skipped** (+3 worker coercion tests);
worker evals `codegen_sandbox` + `worker_http_server` PASS; integration evals
`codegen_generation_path` + `model_authored_analysis` PASS. Specs updated:
`worker-http-server` (the 500-hardening — model metadata coerced + degraded, not
raised), `answer-grounding-check` (the claims-coercion deviation to the "passed
through unchanged" language), `model-authored-analysis` (the matplotlib-submodule
allowlist addendum). Reports: `evals/e2e_runs/20260706T035420Z/REPORT.md`
(judged, 18 cases), `evals/prompts/rule_gate_findings.md`.

**Deploy state.** `main` is 0.2.22 (rule retirement), **commit-only — not
pushed**. The CT103 `:dev` worker carries the metadata-500 + allowlist fix live
(worker-side, no version bump — a future HACS integration ship is independent).
HA still runs 0.2.20 (Colin hasn't redownloaded since 0.2.20). The live e2e
harness + the rule-gate eval are new standing tools.

**Next session.** open-queue **(q)** is the headline — design how an analysis
intent flows prompt → planner → codegen so transforms/answers actually fire live
(then eval against the harness's analysis prompts). Then **(r)** timeline routing,
**(m)** raise `max_codegen_repair_attempts`, **(t)** the >2-day overlay tiering
wall, and the deploy of 0.2.22 via HACS. Consider whether the worker metadata fix
warrants its own version bump + a note that HA and the worker image are now
slightly out of lockstep.

### 2026-07-05 (15th session) — Fixed the 0.2.18 empty-chart / wrong-unit regression: a bounded real-points preview grounds the floor model, and the series unit is set deterministically from the catalog (0.2.18→0.2.19)

Colin retested **0.2.18** and got charts that rendered **COMPLETE but empty** —
no data plotted, default 0–1 axes — with wrong axis labels: the kitchen+basement
weekend chart read **"Temperature (°C)"** on °F sensors, and the kitchen
last-3-days chart read a generic **"Value"**. `main` is now **0.2.19**; all pushed.
Integration only — **no worker or frontend rebuild**.

**Diagnosis (reproduced live, end to end, myself).** This was NOT the 14th
session's overflow (the real prompts measured ~1.8–3.2K tokens, far under
`num_ctx`). I reproduced the whole pipeline offline against the live systems:
pulled real kitchen/basement history via the HA API, ran the **real planner** for
the exact prompts, and generated with **live gemma**, then **executed** each
generation in a venv (matplotlib/pandas) to measure ground truth — did it plot
data, and what unit did it label. The 0.2.18 prompt-view produced empty plots
~2/3 of the time; a clean synthetic case worked, which is what pointed at the
real chart_spec/data as the trigger.

**Root cause: 0.2.18's pure per-series SUMMARY removed the concrete data that
anchored the floor model's code.** Three interacting failures, all confirmed on
real generations:
1. The summary renamed the point list to **`sample_points`** — a key that does
   **not exist at runtime** (the runtime data uses `points`). The prompt was
   literally self-contradictory: the JSON showed `sample_points`, the rule text
   said iterate `points`. Caught gemma live writing
   `history_series_data['sample_points']` → `KeyError` / empty.
2. With only a summary, gemma drove plotting **and** labeling off the
   **`chart_spec`** (5/6 real runs) rather than `history_series`. The chart_spec
   is a trap: the **planner hallucinates the unit** (it emitted `°C` on °F
   sensors), and its series are keyed by `series_id` / `source.entity_id` with
   **no top-level `entity_id`**, so entity-matching fails → empty plot + wrong
   unit. This is exactly the two symptoms.
3. The `PlannerResult` schema **requires** a `unit` per series, but the planner
   prompt never carries the real unit — so it can only guess.

**The fix (Colin's steer: bounded real points, count chosen by experiment; and
fix the planner too).**
- **Grounded preview.** `_history_series_prompt_view` now carries a bounded,
  evenly-downsampled **preview of the real points** under the **same runtime key
  `points`** (plus `points_truncated`; first and last point always kept), via
  `_downsample_preview` and `_CODEGEN_PROMPT_PREVIEW_POINTS = 12`. A live
  grounding experiment (execution-truth, real chart_spec + real history) set the
  count: **summary = 1/3 grounded (2/3 empty); 6 pts = 6/6; 10 = 3/3; 12 = 6/6;
  40 = 6/6 but ~6.2K tok.** 12 sits comfortably above the ~6-point floor at
  ~3.2K tokens for two series. The dispatched render request still carries every
  point (the runtime `data`).
- **Prompt rules.** `history_series` is now the sole data authority: plot every
  series by iterating it directly; the **chart_spec is intent-only** — never read
  the data, the unit, or the list of series to plot from it.
- **Deterministic unit.** `_apply_catalog_units` (job_orchestration.py, right
  after chart_spec validation, `catalog_items` already in scope) overwrites each
  series' `unit` from the authoritative catalog `unit_of_measurement`, keyed by
  `source.entity_id` — so no model-guessed unit reaches either render path.
  Confirmed live: `['°C','°C'] → ['°F','°F']`.

**Verification.** On the actual fixed code, five live generations against the
real weekend chart_spec + history: **5/5 plotted the full data** (was 2/3 empty),
**4/5 clean °F**. The one miss was an unrelated gemma runtime bug (`set.pop` on an
empty set) that **still plotted the data** and would route through the repair loop
/ surfaced Pillow fallback in production — not the empty-chart symptom. This
reinforces open-queue (m): raise `max_codegen_repair_attempts` above 1 (a runtime
slip currently one-shots to fallback). Suite **427 passed / 4 skipped** (+6);
evals `codegen_generation_path` and `model_authored_analysis` PASS; spec
`model-authored-analysis` updated (prompt view = grounded preview, not a bare
summary; authoritative catalog unit). Inline invariant review OK — a prompt-only
projection plus a deterministic post-plan step; no schema, sandbox, service, or
data-boundary change (the preview is bounded and strictly less than 0.2.17's
full-points prompt; raw ISO `ts` is still stripped per D9; the unit comes from the
allowlisted catalog). A fresh-context architecture-review subagent was not spawned
(a bounded change on the accepted codegen path); available on request.

**Note on the 14th-session fix.** The pure summary shipped in 0.2.18 solved the
overflow but is precisely what this session had to correct — for the floor model,
removing all concrete data traded overflow-prose for empty-plot drift. The
bounded preview keeps the prompt small (constant, ~250 tok/series) while giving
the model enough real data to stay grounded. The `num_ctx=8192` and the runtime
`codegen_context_overflow` safety net from the 14th session remain in place.

**Follow-on the same session (0.2.20) — the "Value ()" empty axis on the first
successful 0.2.19 render.** Colin's first 0.2.19 render plotted real data (both
kitchen + basement temperature lines, proper axes) — grounding fixed — but the
y-axis read **"Value ()"**: an empty unit. Reproduced live: across six real
generations the model reads the unit **correctly** from
`history_series[i]['unit']` (`unit = series_data.get('unit')`) and labels the axis
with it verbatim — so an empty `()` means the unit in the **data** is empty, not a
model error. Root cause: `history_series.unit` comes from the catalog's
`unit_of_measurement`, which is snapshotted at catalog **build** time; the ecobee
sensors (a cloud integration) are frequently `unavailable` right after a restart —
their state carries no `unit_of_measurement` attribute then — so the catalog cached
`null` even though the live sensors now report `°F`. Both the codegen unit and the
0.2.19 `_apply_catalog_units` overwrite read that same null. Fix:
`backfill_catalog_units_from_state` (new, `history_retrieval.py`) backfills a
missing unit from the entity's **live state**, applied inside **both**
`_approved_catalog_items` copies (history_retrieval and job_orchestration) so every
consumer — the codegen `history_series.unit` and the chart_spec unit — gets it;
a unit the catalog already carries is never overridden. Verified live end to end:
against the real live state, a stale `[None, None]` backfills to `['°F', '°F']`,
and 4/4 generations then render the unit (`"Temperature (°F)"` / `"Value (°F)"`).
Suite **430 passed / 4 skipped** (+3 backfill tests: missing→backfilled,
present→kept, no-live-unit→unchanged). Version **0.2.20**; integration-only.
**Residual cosmetic:** the axis *word* is still sometimes the generic "Value"
rather than "Temperature" (the model's choice; `"Value (°F)"` is informative but
`"Temperature (°F)"` is nicer). Optional follow-up: surface `device_class` in the
prompt so the model names the measured quantity.

**Follow-on the same session (0.2.21, ADR-0033) — codegen overlays render as a
line, not shaded bands.** On 0.2.20, Colin's "kitchen and basement temps over the
last five days and when the AC was running" rendered COMPLETE but wrong: the
`climate.kitchen_ecobee` state series was drawn as a **line on the temperature
axis** at the constant `"cool"` mode value, instead of shading the intermittent
cooling/heating spans as background bands (as the Pillow renderer does). Note this
also confirms 0.2.20 **fixed** the earlier overlay `unsafe_code` fallback — the
generated code is now *safe*, just *wrong*: an accept-≠-quality failure the static
safety check can't see (exactly the case open-queue (p)'s Claude-in-the-loop
harness would catch; my 18-run static-check repro was clean and I could only see
the problem by looking at the render). The data was already complete — categorical
points carry `attrs.hvac_action`, and `chart_spec.overlays` carries `color_map`
(cooling→blue, heating→orange), `source.attribute: hvac_action`, and
`render_as: shaded_intervals` — but my 0.2.19 rule ("plot every series in
`history_series` as a line") pushed the model to draw the state series, and turning
states into correct shaded intervals is beyond the floor model.

**Colin's steer: integration precomputes the bands (Option B), keep room to back
out.** `_compute_overlay_bands(chart_spec, history_series)` (job_orchestration)
computes, per `shaded_intervals` overlay, bands `{start_ms, end_ms, color, label,
entity_id}` — **reusing the trusted Pillow renderer's** attribute-aware
`_binary_on_regions` / `_categorical_overlay_states` / `_rgb_to_hex` /
`_OVERLAY_COLORS`, so codegen matches Pillow exactly (correct `hvac_action` spans,
correct colors). They populate the existing `derived_intervals` field
(`render-request` schema already an open-object array — no schema change; the
prompt projection already forwards it). Prompt rules revised: plot **only**
`kind == "numeric"` series as lines (never `binary_state`/`categorical_state`), and
draw each `derived_intervals` band as `ax.axvspan(start→dt, end→dt,
color=band['color'], alpha=0.3, zorder=0)` behind the lines. The overlay series
stays in `history_series` (grounding/answer may use it) but is not plotted as a
line. ADR-0033 accepted; deliberately isolated + revertible (remove the population
+ revert the two rules; Pillow fallback unaffected).

**Verification.** Live end to end (real planner-shaped overlay chart_spec + real
HA history with `attrs.hvac_action`): `_compute_overlay_bands` found the real
cooling spans, and **5/5 generations executed to 2 numeric lines + the cooling
bands drawn via `axvspan`, no state line, no error** (instrumented `Axes.plot` /
`Axes.axvspan`). Suite **434 passed / 4 skipped** (+4: bands use `hvac_action` not
the mode, binary `active_values`, no-overlays→[], the axvspan/numeric-only prompt
rule); evals `codegen_generation_path` + `model_authored_analysis` PASS; spec +
decisions README updated. Version **0.2.21**; integration-only. **Residual
cosmetic (unchanged):** the axis *word* is still sometimes "Value" not
"Temperature".

**Next session.** Colin HACS-redownloads **0.2.21** and retests the overlay
("…and when the AC was running") — expect numeric lines + shaded cooling/heating
bands (matching Pillow), no state line. Then: raise the default
`max_codegen_repair_attempts` (open-queue (m); his live instance already at 3);
the optional axis-word cosmetic; **open-queue (p)** the Claude-in-the-loop e2e
harness (this session showed twice why it's needed — accept≠quality slips the
static check); eval-gate the `°` rule (open-queue (o)); registry follow-ups.

### 2026-07-05 (14th session) — Fixed the live codegen context-window overflow: the prompt carries a per-series summary, not the recorder points (0.2.17→0.2.18)

Colin retested **0.2.17** and still got `unsafe_code` / `syntax_error` Pillow
fallbacks — the basement-only chart and the kitchen+basement chart both fell
back. This session root-caused and fixed the underlying problem, which had been
masked as a string of different downstream syntax errors across the last few
sessions. `main` is **0.2.18**; all pushed. Integration + frontend only — **no
worker rebuild**.

**Diagnosis (done live, myself).** Pulled the worker's own logs over root SSH to
CT103 (`docker logs isolinear-worker`) and the HA `system_log` WARNINGs (via
`scripts/ha_logs.py`). Three distinct failure classes across retries —
`syntax_error@L1`, `missing_fixed_entry_point`+`top_level_statement@L…`, and
`syntax_error: leading zeros in decimal integer literals` — with repair failing
all three attempts each time. A clean synthetic reproduction rendered fine, so
the trigger wasn't the prompt *shape* — it was the prompt *size*.

**Root cause (reproduced exactly offline against live gemma).** The codegen
**prompt** was carrying the **full recorder point list**. `_history_series_prompt_view`
stripped only the raw ISO `ts` and kept every point, so a real "last N hours" of
two sensors is on the order of **tens of thousands of tokens** — far past
Ollama's small default `num_ctx` (~4K), and `_codegen_payload` set no `num_ctx`.
Ollama truncates a too-large prompt **from the front**, evicting the system
prompt and rules; gemma, left with only a tail of raw numbers, replies with a
**prose analysis of the data** instead of code. `_extract_python_code` finds no
fence and returns the prose → `syntax_error@L1`. Partial truncation yields the
`missing_fixed_entry_point` / leading-zero variants. Repair never recovers
because the repair prompt (previous code + rules + data) is larger still.

**The fix (Colin's steer — the model never needs the points in its prompt).** The
generated `render_chart(data, output_path)` receives the **complete** data at
runtime in the sandbox (`codegen_sandbox.py:288` calls
`render_chart(_PAYLOAD["data"], …)`; `_sandbox_data` hands it the full
`history_series`), so its code iterates every point when it executes. The prompt
only needs the **shape** to write correct accessors. `_history_series_prompt_view`
now emits a per-series **summary** — all series-level metadata (`entity_id` /
`kind` / `unit` / `label` / overlay fields) plus `point_count`,
`ts_epoch_ms_range`, `value_stats` (numeric) or `distinct_states`
(binary/categorical, capped at 50), and 3 `sample_points` that show the point
dict keys — and **never the full list**. The dispatched `render_mode: "codegen"`
render request is a separate path and still carries every point (the runtime
`data`). Prompt dropped from ~50K to ~1.7K tokens and gemma renders clean where
it failed four times.

**Scaling (measured with Ollama's own tokenizer, `prompt_eval_count`).** The
per-series summary is **constant regardless of point count** — a year and a day
produce the same prompt. Fixed rules overhead ≈ **1,418 tokens**; ≈ **242
tokens/series**; **6 series × 12 months ≈ 2,808 tokens (fits 4096)**. So the
prompt size is now fully decoupled from data volume. `num_ctx=8192` is set on the
codegen options as defense-in-depth (a large `num_ctx` alone did **not** save the
dense-data case in testing — the summary is the real cure).

**Runtime overflow safety net (Colin asked how to catch it).** Even with the
summary, a pathological request (very many series) or a shrunk `num_ctx` / smaller
model could still overflow. Measured: Ollama caps `prompt_eval_count` at **exactly
`num_ctx`** when it truncates, so `prompt_eval_count >= num_ctx` is a definitive
signal (`_context_overflow`). Codegen generate/repair results carry a
`context_overflow` marker; the orchestration **short-circuits the doomed repair
loop** (no wasted worker/repair dispatches) and falls back to Pillow with the
distinct `codegen_context_overflow` reason instead of a misleading downstream
`syntax_error`. The card renders **actionable guidance** for that reason — raise
the codegen model's `num_ctx` / `OLLAMA_CONTEXT_LENGTH`, request **fewer series**,
or use a larger-context model/GPU — and the WARNING log carries the
`prompt_eval_count` / `num_ctx` numbers. The guidance explicitly notes the time
range is irrelevant (the prompt is a per-series summary, not the points) — Colin
caught that the first draft's "shorter time range" advice contradicted the fix.

**Verification.** Suite **420 passed / 4 skipped** (+5: the prompt-summary and
state-summary projections, overflow flagged / not-flagged at the provider
boundary, and the orchestration short-circuit asserting zero worker/repair calls
with the `codegen_context_overflow` reason); frontend **36 passed** (+1: the card
shows guidance, not the raw code); evals `codegen_generation_path` and
`model_authored_analysis` PASS; bundle rebuilt + synced (md5 identical). Spec
`model-authored-analysis.md` updated (prompt-view-vs-runtime discipline + runtime
overflow detection). Inline invariant review OK — the data boundary is strictly
**tightened** (the summary shrinks only the prompt; the worker still receives full
points and runs the full static check; the runtime `data` is unchanged); no
schema, service, or ADR change; the overflow path is a surfaced ADR-0030 fallback,
never silent. A fresh-context architecture-review subagent was not spawned
(bounded change on the accepted codegen path); available on request.

**Next session.** Colin HACS-redownloads **0.2.18** and retests "basement
temperature" and "kitchen and basement temperature" — codegen should render on
the first attempt now (no prose/overflow fallback). Then the standing follow-ups:
raise the default `max_codegen_repair_attempts` (open-queue (m)) — now
higher-value, because the small prompt lets `source_line`-assisted repair actually
converge on a genuine one-line slip; eval-gate the generation-side `°` rule
(open-queue (o)); registry recompute fidelity (`pearson_r` alignment;
corpus-requested metrics).

### 2026-07-05 (13th session) — 🎉 First live codegen chart rendered end to end; three bugs fixed to get there, then polish (0.2.14→0.2.17)

**This is the milestone the whole worker/codegen arc was building toward: a real
model-authored matplotlib chart rendered end to end and displayed in the card.**
Colin asked "show me the kitchen temperature," gemma4:e4b wrote the matplotlib,
the CT103 sandbox ran it, and the PNG came back and displayed. `main` is
`0a02b51` = **0.2.17**; homelab `main` carries the tmpfs fix (`4e80bbc`). All
pushed.

**The three bugs, each surfaced only because the previous fix let the pipeline
get one step further.** This is the signature of bringing up a real integration:
each fix reveals the next latent problem.

1. **`0.2.15` (`ec57839`) — the fence instruction.** After 0.2.14, Colin
   retested: the initial generation failed `syntax_error@L11`, but all three
   repair attempts degraded to `syntax_error@L1`. The `@L1`-on-every-repair
   signature is diagnostic — it means `_extract_python_code`'s no-fence fallback
   returned the raw reply text whose line 1 is prose. The repair model (gemma)
   was replying with an explanation followed by **unfenced** code. Root cause:
   `_CODEGEN_SYSTEM_PROMPT` said "no markdown *outside* a code fence" but never
   told the model *to use* a fence. Fixed by mandating a ```` ```python ````
   wrapper in the system prompt. A regression test pins the fence instruction.

2. **homelab tmpfs perms (`4e80bbc` on homelab `main`).** With the fence fixed,
   the generated code actually executed — and hit `PermissionError` on
   `fig.savefig`. The compose `tmpfs` for `/var/lib/isolinear-worker/work` mounts
   `root:root`, but the worker container runs as uid 10001; the Dockerfile's
   `chown` is overridden by the runtime tmpfs mount. Fixed by adding
   `uid=10001,gid=10001` to the tmpfs options — **both** live on CT103 **and** in
   the homelab IaC template so the next `ansible` apply stays converged. (The
   sandbox correctly blocked my direct production `sed` and my push to homelab
   `main` until Colin explicitly authorized both — the right default.)

3. **`0.2.16` (`9e14b9e`) — the image bytes.** The worker then logged
   `status=success`, but the integration failed with `missing_worker_image_bytes`
   at the serve stage. `invoke_codegen_sandbox` returns `image_path` (a path
   *inside the worker container*) but not the bytes — and the integration runs on
   the HA box with no filesystem access to that container. The worker-http-server
   spec had explicitly marked base64 inlining "deferred to packet 5"; the first
   live render is what forced it. Fixed: on a successful render the HTTP server
   reads the PNG and inlines `image_bytes_base64` (the field already existed in
   `render-result.schema.json`; `base64` is stdlib — no new dependency, no schema
   change). Worker rebuilt + force-recreated on CT103. **Then it rendered.**

**`0.2.17` (`0a02b51`) — polish on the first real chart.** Three issues Colin
flagged, all shipping via HACS with **no worker rebuild** (the prompt rules are
integration-side, the CSS is in the frontend bundle):

- **Wrong unit** — the axis read °C on an °F sensor. The model was guessing: the
  real HA unit is already in the prompt data (`history_series[i]['unit']='°F'`,
  from the allowlisted catalog), but no prompt rule told the model to use it. New
  grounding rule reads the unit from the data and f-strings it into the label —
  which, as a bonus, keeps the `°` symbol out of a *bare literal* (a variable
  reference, not a token), so it structurally can't retrigger the earlier
  bare-`°` syntax-error class. This is why open-queue (o) — retiring the
  generation-side `°` rule — is now *doubly* redundant.
- **Fonts too small** — matplotlib's 640×480 default scaled down on a
  phone-width card. New legibility rule: figsize ~8×4.5 at dpi 110 with explicit
  title/label/tick sizes, plus `bbox_inches='tight'`.
- **Card letterbox** — `.result img` used `object-fit: contain` inside a forced
  `min-height: 260px` row, so a landscape chart floated in gray bars. Now
  `height: auto` at the image's natural aspect ratio, filling the card width.

**Verification.** Suite **415 passed / 4 skipped** (+1 fence-instruction test, and
the worker-http success test now also asserts `image_bytes_base64` decodes to a
PNG); frontend **35 passed**; evals `codegen_sandbox`, `worker_http_server`,
`codegen_generation_path`, `model_authored_analysis` PASS; bundle rebuilt +
synced (md5 identical). **Spec drift fixed:** `worker-http-server.md` marked
base64 inlining deferred — corrected to IMPLEMENTED, with the live rationale
(the integration host can't read `image_path`). Inline invariant review OK: no
sandbox/allowlist/schema/service change — `image_bytes_base64` is the exact PNG
that was always meant to be served (base64 runs in the server process, not the
sandbox subprocess); the unit comes from allowlisted catalog data; the CSS is
display-only. A fresh-context architecture-review subagent was not spawned
(bounded live hotfixes + polish on the accepted codegen path); available on
request.

**Next session.** Colin HACS-redownloads **0.2.17** and retests — confirm the
unit reads correctly (°F), fonts are legible, and the card fits the chart. The
unit/font fixes depend on gemma *following* the new prompt rules; if the unit
still comes out wrong, tighten the wording. Then the standing follow-ups: raise
the default `max_codegen_repair_attempts` (open-queue (m); less urgent now that
first-attempt renders work); eval-gate and likely drop the generation-side `°`
rule (open-queue (o)); registry recompute fidelity (`pearson_r` alignment;
corpus-requested metrics).

### 2026-07-04 (12th session) — Second live codegen syntax fallback fixed: a bare `°` token; the generic fix is offending-line text on every violation (0.2.12→0.2.14)

Colin redownloaded 0.2.12, retested "kitchen temperature," and still got a
Pillow fallback — but a *different* one, and the logging made it fast. `main`
will be `0.2.14` once pushed. Two commits (`345be4a`, `458a8b7`).

**Diagnosis from live logs.** `docker logs isolinear-worker` on CT103 showed
`status=failed error=unsafe_code violations=[syntax_error@L19]` — the fence fix
(0.2.12) had worked: the error moved from line 1 to line 19, meaning real
extracted code was now reaching the sandbox. The HA system-log WARNING (pulled
via `scripts/ha_logs.py`, WebSocket `system_log/list`) carried the full message:
`invalid character '°' (U+00B0) (<unknown>, line 19)`. Reproduced against the
container's own Python: `°` parses fine inside a string, comment, or f-string —
the *only* position `ast.parse` rejects is as a **bare token**. So the model
wrote something like `ax.set_ylabel(Temperature °F)` with the label unquoted, and
repair re-emitted it every attempt because the repair task text only described
disallowed imports/attributes/calls, never syntax errors.

**0.2.13 (`345be4a`) — the first, narrower pass.** A generation-side
`_CODEGEN_PROMPT_RULES` rule (write all text labels as valid Python string
literals; never use non-ASCII such as `°`/`%` as bare tokens; correct-vs-wrong
example) plus a repair-task clarification distinguishing `syntax_error` from
`unsafe_code`. This included a hardcoded `°` example in the repair task.

**0.2.14 (`458a8b7`) — the generic fix, after Colin pushed back.** Colin's
question: are we overfitting to this error and this model, and wouldn't it be
better to give repair better information than to keep appending one-off
instructions? He was right about the mechanism. The key realization: the
information was never missing — a `SyntaxError` fails in `ast.parse` *before*
execution, so there is no traceback to add, and the full diagnostic plus the
prior code were already in the repair prompt. gemma still failed three times.
The real gap is that small models can't reliably **locate line 19 by counting**
in their own output. So the generic lever is to hand them the line. The worker's
`static_safety_check` now attaches `source_line` — the exact offending text
(≤200 chars) — to *every* line-numbered violation via `_attach_source_lines`,
covering both the `syntax_error` early-return and all `unsafe_code` violations.
The repair task points at `source_line` generically and the hardcoded `°`
example was removed. `error.details` is `additionalProperties:true`, so violations
are free-form inside it — no schema change — and `_sandbox_error_view` already
deep-copies violations, so `source_line` reaches the repair prompt with no
integration wiring. As a bonus this is exactly the field that would have made the
diagnosis instant: we *inferred* the bare-° from the message; we never saw the
rejected line.

**On the generation rule.** It stays for now (it prevents the failure at the
source and is a single general principle, not a per-error instruction), but it's
recorded as a candidate for **eval-gated retirement** (STATUS open-queue (o)):
once the worker carries `source_line` live, run `evals/codegen_reliability.py`
with and without the rule; if `source_line`-assisted repair recovers the class
on its own, drop it to keep the prompt lean. Proposed standing division —
contract rules stay in the prompt; failure-driven style hints must earn their
accept-rate in the eval.

**Deploy split (important).** The generation-side prevention is integration-only
and ships via HACS in 0.2.14 — that alone should stop the live symptom, since it
prevents the bare `°` at generation time. The `source_line` robustness is
**worker-side**: it needed an image rebuild + `docker compose up -d
--force-recreate isolinear-worker` on CT103 (no rsync — ship context via
`tar | ssh`; a rebuilt same-tag `:dev` image needs the manual force-recreate).
**DONE this session:** shipped `worker/` to `/tmp/iw-build` via `tar | ssh`,
`docker build -t isolinear-worker:dev`, force-recreated the `/srv/compose`
service. Verified the live image attaches `source_line` (bare-° snippet →
`syntax_error` violation with `source_line='ax.set_ylabel(Temperature °F)'`),
`/v1/health` `ready` (matplotlib ok), container healthy; build dir cleaned up.
Both halves of the fix are now live.

**Verification.** Suite **414 passed / 4 skipped** (+2: worker
`test_violations_carry_the_offending_source_line`; integration
`test_repair_prompt_carries_violation_source_line`); evals `codegen_sandbox` and
`codegen_generation_path` PASS. Spec `codegen-generation-path` updated (the
`repair_chart_code` description now names traceback + violations + `source_line`
and the generic task). Inline invariant review OK — `source_line` is the model's
own generated code, already fully present in the prompt as `previous_code`, and
the data boundary strips secrets on the way in, so nothing new crosses; the
static gate still runs in full (the field is attached *after* the reject
decision). A fresh-context architecture-review subagent was not spawned (a
bounded hotfix on the accepted codegen path); available on request.

**Next session.** Colin HACS-redownloads **0.2.14** and re-asks "kitchen
temperature" — the generation rule should prevent the bare `°`; if any syntax or
unsafe error still slips through, rebuild the worker on CT103 so `source_line`
reaches repair (and `docker logs isolinear-worker` will show the exact offending
line). Then: raise the default `max_codegen_repair_attempts` (open-queue (m));
eval-gate the `°` rule (open-queue (o)); registry follow-ups (`pearson_r`
alignment; corpus-requested metrics).

### 2026-07-04 (11th session) — Live bug (open-queue (n)) fixed: codegen replies with prose around the fence were mangled into `syntax_error@L1`; robust code extraction shipped (0.2.11→0.2.12)

Two live problems, both resolved. `main` will be `0.2.12` once pushed.

**(1) "Card broke, can't re-add it" — diagnosed as a stale browser cache, NOT a
code bug.** Colin's dashboard showed *"Custom element doesn't exist:
isolinear-card."* Diagnosed against the live instance (`10.0.1.200`, HA core
2026.7.1) end to end: config entry `state: loaded`; the Lovelace resource is
registered (`/api/isolinear/static/isolinear-card.js?v=0.2.11`, type `module`);
the JS serves 200 **with and without** auth (static-path bypass correct), byte-
identical to the repo bundle, `text/javascript`; and the bundle evaluates in a
DOM realm and registers `isolinear-card`. Every backend link is healthy, so the
error was purely client-side — the browser held the failed state from the
`0.1.48 → broken-0.2.1 → 0.2.11` upgrade path (same class as the 0.1.38 Edge
stale-JS issue). **A hard reload fixed it** (confirmed by Colin). No code change.

**(2) The real bug — codegen always fell back to Pillow with `unsafe_code`
(`0.2.12`).** After the reload, "kitchen temperature" still fell back. The
0.2.11 logging paid off immediately: the fallback WARNING carried
`final_error_code: unsafe_code, codegen_attempts: 4, repair_attempts: 3,
violations: ['syntax_error@L1: invalid syntax (<unknown>, line 1)']`. So it was
never a genuinely unsafe construct — the worker's `ast.parse` failed on **line
1** of the code it received, every attempt. Root cause: the only transform
between the model reply and the sandbox is `_strip_markdown_json`, a helper
written for **JSON** planning output — it strips a code fence only when the
fence is the *very first* thing in the text. Freeform codegen replies (and
**repair** replies especially) routinely lead with prose ("Here is the
corrected code:") before the ` ```python ` fence, so that prose survived as line
1 → `syntax_error@L1` → Pillow fallback on every attempt. This exact signature
was reproduced by feeding the helper a prose-prefixed reply. (The 0.2.10/0.2.11
visibility work is what made this findable in one session.)

**The fix.** New `_extract_python_code` (`model_provider.py`) for the two
codegen paths (`generate_chart_code` / `repair_chart_code`): it pulls the body
of the first ` ``` ` fence regardless of surrounding prose (via a non-greedy
`_CODE_FENCE_RE`), strips a language tag, tolerates a truncated (no-close)
fence, and falls back to stripped raw text when unfenced. The JSON-only
`_strip_markdown_json` (planner/selector) is left untouched. Verified on 8 reply
shapes (prose before/after/both, no-lang fence, truncated, bare code) — all
extract clean, compilable code, no fence leakage. This is **integration-only**:
no worker rebuild, no frontend rebuild, no schema/sandbox change — the sandbox
still runs the full static safety check on whatever it receives (invariant #3
intact). Inline invariant review OK; a fresh-context architecture-review
subagent was not spawned (a bounded parse hotfix on the accepted codegen path) —
available on request.

**Verification.** Suite **411 passed / 4 skipped** (+3: the extractor unit test
over the 8 shapes + prose-wrapped generate + prose-wrapped repair, each
`compile()`-checked); evals `codegen_generation_path` and
`model_authored_analysis` PASS. Spec `codegen-generation-path` updated (the
"markdown-stripped with `_strip_markdown_json`" lines now describe
`_extract_python_code` and why). Version bumped 0.2.11→0.2.12.

**Next session.** Confirm live: Colin HACS-redownloads **0.2.12**, re-asks
"kitchen temperature" — it should render via codegen with a grounded answer on
the *first* attempt (no repairs needed now the fence extracts). If it still
falls back, `docker logs isolinear-worker` shows the real reason immediately.
Then: consider raising the default `max_codegen_repair_attempts` (open-queue
(m)); registry follow-ups (`pearson_r` alignment; corpus-requested metrics).

### 2026-07-04 (10th session) — Shipped to `main` and brought up live: the chain reaches the worker, and three bugs found in real use are fixed (0.2.8→0.2.11)

Isolinear ran end-to-end against real Home Assistant for the first time this
session, and the debugging happened live. `main` is now `1d923c6` = **0.2.11**;
everything is pushed. Live HA still needs one more HACS redownload (it was on
0.1.48, briefly 0.2.1 from a stale PR, now 0.2.11) plus Colin's retest to
confirm a clean codegen render — the last unconfirmed step. A **new bug** Colin
found during testing is deferred to next session (STATUS open-queue (n),
details TBD).

**The merge, and a stale-PR catch.** Completing the ship meant merging
`adr-0029-worker-codegen-eval` → `main`. On the way I found that Colin's GitHub
**PR #3 had already merged a stale commit** (`4d0e153`, the 4th-session tip,
version 0.2.1) — so `origin/main` was a half-shipped 0.2.1: missing the entire
5th–9th-session line (answer channel, grounding check, scipy/seaborn, ADR-0032)
and still carrying the deleted ADR-0015/0016 machinery. Had HACS pulled that,
it would have been a broken build. I rebuilt the current tip on top of the PR
merge (kept the PR merge commit in history — no force-push) so `main` is the
complete 0.2.11.

**Three live bugs, each root-caused, fixed, tested, shipped:**

1. **Endpoints not editable post-install (`0.2.9`, `8ea4a7f`).** `model_endpoint_url`
   and `worker_endpoint_url` were config-flow (setup-time) fields only. A fresh
   install's worker endpoint was therefore stuck on the placeholder entered
   before the worker existed, so the integration tried a dead address and fell
   back to Pillow with `worker_connection_error`. Both endpoints are now
   editable in the Configure (options) form, positioned above the entity picker
   (Colin's request). They stay config-entry *data* (the single source
   consumers read): the options flow extracts them before options validation
   (like the ADR-0032 token), validates with the same URL rules (malformed +
   credential-bearing rejected), persists via `async_update_entry`, and rebuilds
   the model-provider + worker-renderer setups so the change is live without a
   restart. +8 tests; config-flow spec updated.

2. **Codegen repair was blind to `unsafe_code` (`0.2.10`, `de7ec4f`) — the big
   one.** With the endpoint fixed, renders reached the worker but fell back with
   `unsafe_code` on *every* attempt regardless of `max_codegen_repair_attempts`.
   Root cause: `_sandbox_error_view` projected only `code`/`message`/`traceback`
   into the repair prompt, but a static-check failure has **no traceback** — its
   specifics live in `details.violations`, which was dropped. So the model
   repaired blind and re-emitted the same disallowed construct until the budget
   exhausted. (This is exactly why the packet-5 reliability eval's ~94%
   with-repair rate never appeared in production: the eval saw the violations,
   production didn't.) The error view now carries `violations` and the repair
   task text tells the model to remove/replace each flagged construct using only
   the allowed libraries. Proven against the live model: deliberately-unsafe
   code (`import os` + dunder + forbidden attribute, 3 violations) → one repair
   pass → statically clean, `os` gone. +4 tests. Note: the default
   `max_codegen_repair_attempts` is 1 (stingy now that repair works — STATUS
   open-queue (m) to raise it).

3. **Thin failure visibility (`0.2.11`, `1d923c6`).** The whole session's
   debugging was slow because a fallback surfaced only the reason code and the
   violations were buried in DEBUG / unlogged. Now: the integration logs a
   WARNING on codegen fallback (stage / final error code / attempts + a compact
   log-safe detail — the `unsafe_code` violations as `code@Lline: message`, or a
   runtime traceback tail — reachable via the HA system-log channel), and the
   worker logs each `/v1/render` outcome (INFO success; WARNING with error code
   + `code@Lline` violation summary), so `docker logs isolinear-worker` shows
   more than the bare HTTP line. No secrets cross either log (violations name
   code constructs; the data boundary already strips tokens). +5 tests; worker
   image rebuilt + recreated on CT103.

**Live proof of the chain.** Two `POST /v1/render` from `10.0.1.200` (the Pi)
are in the worker log — the endpoint fix worked and the full path (HA → model →
CT103 worker → sandbox) connects. The render fell back on the repair-blind bug,
now fixed. **Infra:** Colin now has SSH to CT103 — his Termius ed25519 key
(`colin-termius-phone`) is in root's `authorized_keys`; CT103 root is key-only
(`permitrootlogin without-password`), so he reads the deployment token himself
via `docker exec isolinear-worker env | grep ISOLINEAR_WORKER_TOKEN` rather than
it ever crossing the chat transcript.

**Verification.** Suite **408 passed / 4 skipped** (+17 across the three fixes);
evals `home_assistant_hacs_install_packaging`, `codegen_generation_path`,
`model_authored_analysis` PASS. Inline invariant check OK — no sandbox,
allowlist, schema, or new-service change: the config-flow endpoints route into
existing config data, and the repair-view + logging changes are additive /
diagnostic. A fresh-context architecture-review subagent was not spawned (these
are bounded hotfixes on the accepted codegen path); available on request.

**Next session.** (A) Confirm the first clean codegen render: Colin redownloads
0.2.11, sets `max_codegen_repair_attempts` to 2, re-asks — watch
`docker logs isolinear-worker` for a clean render + a grounded answer (the new
logging will show the exact violation immediately if it still trips). (B) The
new bug (open-queue (n)) once Colin describes it. (C) Registry follow-ups
(`pearson_r` alignment; corpus-requested metrics). PARKED as before.

### 2026-07-04 (9th session) — The live-deploy path is open: scipy+seaborn shipped, the worker runs as a CT103 compose service, and the integration can authenticate to it (0.2.6→0.2.8)

Three landings this session move Isolinear from "proven in evals" to "a real
worker the real integration can reach." Isolinear branch
`adr-0029-worker-codegen-eval` is pushed through `54eaffb`; the homelab side is
on `main` (`311eac9`, pushed). **What remains before a first live render is a
merge + a HACS redownload + Colin pasting two values** — no more code.

**Packet 3 — scipy + seaborn into the worker (`8964bc1`, 0.2.7).** The two
tranche-1 analysis libraries (ADR-0031 D6) land in `worker/requirements.txt`
and the sandbox import allowlist (exact-match entries `scipy`, `scipy.stats`,
`scipy.signal`, `scipy.optimize`, `seaborn` — mirroring the matplotlib
submodule pattern). A stale codegen prompt rule ("Do not import anything
except matplotlib") that contradicted the packet-2 pandas hint now enumerates
the five libraries. **Proven live on CT103 (Scenario H):** the image rebuilt to
**719MB** (was 526MB), the in-container worker suite ran **27 passed / 0
skips**, all five libraries imported together in the `-I` sandbox under the
1024MB `RLIMIT_AS` cap, and a `scipy.stats` correlation + `seaborn.heatmap`
generated a valid PNG through the fixed output path. The static gate
incidentally re-proved itself by rejecting a dunder attribute in the first
driver attempt. Evidence appended to
`bdd/model-authored-analysis/model-authored-analysis-evidence.md`.

**Homelab — the worker as a managed service (`311eac9` on `main`).** The
worker (`isolinear-worker:dev`, a local tag built on CT103 from this repo,
`pull_policy: never`) is now a GPU-less `docker_host` compose service on port
8080, with the bearer token injected from SOPS
(`docker_host.isolinear_worker_token`) and a tmpfs work root (rendered PNGs are
ephemeral). Spec + BDD `isolinear-worker-service` (A–E) passed live: the image's
own authenticated HEALTHCHECK reports healthy under compose; `/v1/health`
returns `ready` with token+version, 401 without a token, 400 on a missing
version; re-apply is `changed=0`; and ollama/frigate/plex/caddy kept their
uptimes (the full-stack handler moved from `state: restarted` to
`state: present`, so an additive service block converges only changed
services — a rebuilt same-tag image still needs a manual force-recreate). No
plaintext token in the repo (gitleaks green). **CT103 gotchas that held:** no
rsync on the host (ship context via `tar | ssh`); the worker's auth→version→
schema ordering means an authenticated but version-less health call is a 400,
not a 200.

**ADR-0032 — the deployment token, and a 3.1K-LOC deletion (`54eaffb`,
0.2.8).** Deploying the worker surfaced a mismatch designed into the scaffold
era: the integration self-provisioned a bearer token (the deprecated ADR-0016
lifecycle) that the real worker — which reads `ISOLINEAR_WORKER_TOKEN` from
SOPS at deploy time — had never heard of, so every live dispatch would have
401'd. The evals never hit it because they controlled both ends of the wire.
ADR-0032 (accepted; direction Colin 2026-07-03) makes the token **deployment
configuration**: a write-only options-flow password field (`worker_api_token`)
persists to an integration-owned HA Store (`worker_token_storage.py`, the
semantic-memory storage shape), extracted **before** options validation so
options/config data never carry it (the `config_schema` secret-vocabulary
fail-closed check is untouched), never pre-filled or echoed. A save/clear
rebuilds the renderer client in the options flow itself — HA fires update
listeners only when options changed, and a token-only re-paste leaves options
identical (an architecture-review catch). `setup_worker_renderer` now builds
the client from `worker_endpoint_url` + the stored token; missing either piece
keeps the existing disabled `worker_renderer_token_missing`, so `render_path:
auto` falls back to Pillow (ADR-0030, surfaced) — no new failure mode. **The
deletion:** eight uncovered ADR-0015/0016 modules (`worker_token_lifecycle`,
`worker_readiness`, `worker_health`, `worker_health_polling` +
`_constants`/`_contract`/`_state`/`_storage`), five schemas from both bundled
copies, and the `__init__` lifecycle-abort/readiness/health/polling chain.
Worker health is now on-demand via the client's existing `check_health()`. The
2026-07-02 purge had already deleted every behavioral test of this machinery —
the deletion broke only the packaging test's schema-path imports, confirming it
ran uncovered. A deletion-guard test pins the modules/schemas gone and no
imports remaining (both `custom_components/` **and** `evals/` — a second
review finding, since pytest never runs evals). **Live-proven**
(`evals/deployment_worker_token.py`): the real `HttpJsonWorkerRenderClient`
authenticated to the compose-managed CT103 worker with the SOPS deployment
token and got `status: ready`; a wrong token surfaced a 401 fault as a dict
(no exception, no token material). This is the first time the real integration
client spoke to the real deployed worker.

**Verification.** Suite **391 passed / 4 skipped** (+18 across the two
packets); five worker-path evals PASS (`codegen_sandbox`,
`codegen_generation_path`, `worker_http_server`, `model_authored_analysis`,
`home_assistant_hacs_install_packaging`). Architecture review (fresh-context
subagent) on ADR-0032 returned CONCERNS→resolved: a broken packaging eval
(fixed), the token-only re-paste rebuild (added + test), and spec/ADR drift
(aligned, deviations recorded in the spec). BDD-evidence review OK — stale
counts in the token evidence file were corrected at this closeout.

**What remains (none blocking).** (a) **Ship + first live render:** merge
`adr-0029-worker-codegen-eval` → `main` (30+ commits ahead: the scaffold purge,
the 0.2.x pivot, ADR-0030/0031/0032 — HACS tracks the default branch, and live
HA still runs 0.1.48), HACS Redownload 0.2.8, restart, then Colin sets
`worker_endpoint_url` = `http://10.0.1.39:8080` and pastes the SOPS token into
the new options field → ask a question → the first end-to-end
model→matplotlib→sandboxed-PNG + grounded answer through the live worker. Colin
chose merge-after-smoke-test; the pre-merge smoke test (real client, real
worker, real token) has passed. (b) **Registry recompute fidelity** (from the
8th session, still open): `pearson_r` prescribed alignment; corpus-requested
metric additions. (c) A rebuilt same-tag worker image needs a manual
`docker compose up -d --force-recreate isolinear-worker` on CT103 (the compose
handler won't re-pull/re-read a `:dev` tag) — worth a real image version/registry
when distribution matters. PARKED: packet 5 (output-modality signal), packet 6
(visual validator + progressive-verification UX), open-queue (l), split
`job_orchestration.py`.

### 2026-07-03 (8th session) — Grounding-check proof req #4 answered: floor-model claim-emission rate measured with production scoring, 0.2.5→0.2.6

The grounding-check packet is now closed end to end: implemented (4a–4d, prior
sessions) **and proof-measured at the capability floor** (this session). Branch
`adr-0029-worker-codegen-eval`; **everything is committed and pushed** —
packets 1–4d (`068d7ef`, `c833991`, `4af08f1`, `523cb57`) plus this session's
two commits (`079431d`, `e1c6ef7`) and the closeout commit. The stale
"committed-not-pushed" notes carried by earlier sessions below are corrected.

**What changed (commit 1 — `079431d`, anchored-claim prompt shape).** Packet 4d
shipped anchor re-detection check-side, but `_CODEGEN_PROMPT_RULES`
(`model_provider.py`) only documented the absolute `{start, end}` claim window —
so no model could ever emit the event-anchored form and the 4d path would never
exercise in production. The spec §1/§1a anchored window (anchor
`entity`/`to`/`from`/`occurrence`/`search`/`resolved_at` + `direction` +
`duration_ms`) is now documented with the same compute-not-guess discipline as
`value`/`verdict`: `resolved_at` must be the transition timestamp the code
actually found, so the integration can confirm the SAME event. A prompt-rule
test rides alongside the existing grounding/epoch-ms rule tests.

**What changed (commit 2 — `e1c6ef7`, the proof-req-#4 benchmark, 0.2.6).** The
answer-family benchmark (`evals/analysis_benchmark/`) now scores emitted claims
with the **real production checker**
(`custom_components.isolinear.answer_grounding`) against fresh real HA history
(7-day extract, 16 entities, 16,318 points — gitignored), so "well-formed"
means what production means. Corpus: 18 prompts with `claim`/`claim_window`
expectation flags + `anchor-01` (the registry-verifiable anchored case); the
`answer_question` category was added to `evals/prompts/benchmark_prompts.json`
(proof req #4 names both files); `num_predict` 3000→6000 (the old cap
truncated claim-bearing generations; production doesn't cap). Three live
`gemma4:e4b` runs, one variable at a time; full evidence in
`evals/analysis_benchmark/FINDINGS.md` and mirrored into the BDD evidence file.

**The answer.** **Emission is reliable** — every claim-expected prompt whose
generated code executed emitted a `claims` list (6/6, then 5/5); structure is
mostly right (6/6, 4/5 well-formed). **Registry-verified: 0 in every run**,
with three now-measured causes: (1) run 1's "value formatted into the
sentence" wording made gemma stringify 13/13 values (`'3.0°F'`) — the
production prompt now demands a **raw JSON number**, which fixed the type on
every subsequent claim; (2) free metric naming (`mean_difference`,
`percentage_running`, …) lands honest-but-unregistered metrics in the caveat
box — correct per D3, and renaming them would fabricate `value_mismatch`;
(3) the registry's exact-timestamp `pearson_r` intersection returns no
reference on real irregular data — ADR-0031's "prescribe the alignment" open
item, confirmed live. Anchored windows were never emitted (0/2 every run:
event logic appears in the code, but the record carries absolute bounds) —
acceptable for tranche 1 (value↔data still holds; only event *identity* goes
unconfirmed). Crucially, **no false "verified" was ever produced**, and the
check caught a genuine live `grounding_verdict_contradicted` (pd-05) — the
exact class it exists for. The fail-soft three-state boundary — not the strong
guarantee — is what carries floor-model UX, exactly as spec §3b anticipated.

**Closeout hygiene.** The BDD evidence file was misplaced at
`docs/bdd/answer-grounding-check/answer-grounding-check-bdd.md` — a path the
BDD never named — and is moved to the conventional
`bdd/answer-grounding-check/answer-grounding-check-evidence.md` (the path the
BDD's Evidence section declares), with a proof-req-#4 section appended and the
stale "nothing yet prompts gemma to emit anchors" note corrected. All five
grounding-check spec proof requirements are now met or measured.

**Verification.** Suite **372 passed / 4 skipped** (+1 prompt-rule test); eval
`model_authored_analysis` PASS. Architecture review skipped (benchmark/eval
extension — no new integration surface, no invariant touched); BDD-evidence
review run inline (OK; the path/staleness findings above were fixed in this
closeout).

**What remains (open items, none blocking).** (a) **Registry recompute
fidelity:** integration-prescribed alignment for `pearson_r` (exact-timestamp
intersection finds no common timestamps on real irregular series — correlation
claims can never verify live until this lands); demand-driven registry
additions the corpus actually requested (aligned `mean_difference`-style
delta, time-in-state fraction). (b) **Anchored-window tranche 2:** the floor
model records absolute bounds even with the anchored form documented, so 4d
re-detection won't exercise at the floor until the prompt pushes harder or a
stronger model emits it — recorded as an open item, not a defect.
(c) **Next packet options:** packet 3 (scipy+seaborn into the worker image,
~650MB, in-container import under the 1024MB cap, CT103 rebuild) toward the
live-deploy path (homelab `docker_host` compose service + point the
integration at it + ship via HACS); or the registry follow-ups above. PARKED:
packet 5 (output-modality signal), packet 6 (visual validator +
progressive-verification UX), open-queue (l), worker-durability
simplification, `job_orchestration.py` split.

### 2026-07-03 (7th session) — Sub-packet 4d implemented: event anchors (ADR-0031 D8a §1a), 0.2.4→0.2.5

The last open piece of the answer-grounding check is now built. Packet 4's
sub-packets 4a/4b/4c shipped last session (committed + pushed at session
start, `4af08f1`); this session closes **4d — event anchors**, which the spec
explicitly allowed to ship later since the claim `window` shape was already
fixed. Branch `adr-0029-worker-codegen-eval`; **this session's work is
uncommitted at handoff** *(corrected at the 8th-session closeout: since
committed as `523cb57` and pushed)*.

**The re-detection (`custom_components/isolinear/answer_grounding.py`).**
Anchored windows (`window: {anchor, direction, duration_ms}`) previously
short-circuited to a blanket `grounding_anchor_deferred` caveat. Now, per spec
§1a, `_anchor_criteria_ok` checks all four reproducibility criteria — the
anchor's `entity` is among the delivered series AND its raw-state kind
(ADR-0022 `binary_state`/`categorical_state`, reusing the existing kind
taxonomy); `to`/`from` are non-empty strings (crisp discrete transition, no
fuzzy matching); `occurrence` is a non-zero int (1-based, negative from end);
`search`/`resolved_at` are numeric. Any failure is **irreproducible by
construction** → `grounding_anchor_unreproducible` (caveat, never attempted
further). Criteria-passing anchors are re-detected by `_detect_transitions`
(scans the full ordered raw-state timeline — `raw_state` or
`attrs[attribute]` — for exact `to`/`from` transitions, filtered to those
whose own timestamp falls in `search`) and `_select_occurrence` (the same
1-based/negative-from-end indexing a model would use). No match →
`grounding_anchor_unfound` (contradicted — the fabricated-event case). A match
at a different instant than the claimed `resolved_at` → `grounding_anchor_mismatch`
(contradicted — identity, not just existence). A correctly re-detected anchor
resolves absolute `{start, end}` bounds from `direction`/`duration_ms`, which
then flow through the **same** span-check and registry recompute as an
absolute window — extending the full value↔data guarantee to event-scoped
claims. Window-shape validation (`direction`/`duration_ms`) runs *before* the
re-detection scan (architecture-review nit, applied) so a malformed window
doesn't pay for walking the series.

**No schema change.** The claims-ledger `window` field was already an open
object (`additionalProperties: true`), so the anchored shape fits without
touching any of the three synced schema copies — confirmed byte-identical.

**Tests.** 5 new cases in `TestScenarioD`
(`tests/test_answer_grounding.py`): fabricated anchor → `anchor_unfound` →
contradicted/withheld (spec proof requirement #1's fabricated-anchor case);
mismatched `resolved_at` → `anchor_mismatch`; a correctly re-detected anchor
→ `verified` (reference recompute over the resolved window matches the
claimed value); an anchor on a numeric (non-raw-state) entity → caveat;
an anchor missing `search`/`occurrence` → caveat. The pre-existing stub test
(`test_anchored_window_is_caveat`, asserting the old blanket
`grounding_anchor_deferred` code) is renamed
`test_malformed_anchor_shape_is_caveat` and now asserts
`grounding_anchor_unreproducible` — same observable outcome (caveat), correct
code name.

**Reviews.** BDD-evidence review (inline) OK — Scenario D added to
`docs/bdd/answer-grounding-check/answer-grounding-check-bdd.md` with raw
pytest output and a run timestamp (previously absent from the file).
Architecture review (fresh-context subagent) OK — no invariant violations
(allowlist gate reused for `anchor.entity`; no schema/config/sandbox change;
kind taxonomy reused, not redefined); one non-blocking ordering nit
(validate window shape before the re-detection scan) applied.

**Verification.** Suite **371 passed / 4 skipped** (+5 anchor tests);
frontend unchanged **35 passed** (4d is check-side only, no card change);
eval `model_authored_analysis` PASS; schema byte-parity unchanged (all three
render-result copies still byte-identical — confirmed via md5sum). Version
bumped 0.2.4→0.2.5 in `const.py` + `manifest.json` (completed implementation
packet).

**ADR-0031 D8a is now fully shipped** (4a/4b/4c/4d all landed). **Next
session — choose one:** (A) **floor-model claim-emission rate** (spec proof
requirement #4, still open): extend the answer-family benchmark
(`evals/prompts/benchmark_prompts.json` + `evals/analysis_benchmark/`) to
measure whether `gemma4:e4b` reliably emits well-formed claim recipes —
note the codegen prompt (`_CODEGEN_PROMPT_RULES` in `model_provider.py`)
still only documents the absolute-window claim shape, not the anchored form,
so this benchmark work would also want a prompt extension for anchors to be
exercised by a real model. (B) **Packet 3 — scipy+seaborn** into the worker
image (CT103 rebuild) toward a live deploy. (C) Push this session's commit
plus the still-unpushed packets 1–2 (`068d7ef`/`c833991`) — ask before
pushing. *(Corrected at the 8th-session closeout: (A) is done — proof req #4
answered — and everything is pushed.)*

### 2026-07-03 (6th session) — Packet 4 implemented: the deterministic answer-grounding check (ADR-0031 D8a), 0.2.3→0.2.4

The open half of ADR-0031 D8a is now built. Sub-packets **4a/4b/4c** shipped;
**4d (event anchors) is deferred to tranche 2** — the claim shape and a
`grounding_anchor_deferred` caveat path exist so re-detection slots in later
without schema churn. Branch `adr-0029-worker-codegen-eval`; **the packet-4
work is uncommitted at handoff** (and packets 1–2 remain committed-locally but
not pushed — ask before pushing). *(Corrected at the 8th-session closeout:
packet 4 since committed as `4af08f1` and pushed, as are packets 1–2.)*

**The check (`custom_components/isolinear/answer_grounding.py`, new).** Pure
Python, no numpy/scipy, so it runs integration-side on the Pi. A metric
**registry** maps the seven tranche-1 metrics (`mean`, `delta`, `pearson_r`,
`rolling_mean`, `daily_max`, `daily_min`, `hours_above`) to recompute
implementations over the normalized `ts_epoch_ms` history — `pearson_r` is
hand-rolled over common timestamps. `run_grounding_check(render_metadata,
history_series)` runs the spec's six-step claim check plus the sentence-initial
yes/no **tripwire**, returning a three-state outcome — **verified**
(registry recompute matches within `_TOLERANCE = 0.05` and the verdict follows
the declared rule at the reference), **unverified-caveat** (nothing
contradicted but nobody reproduced the value — unknown metric, window outside
span, anchored window), or **contradicted** (positive evidence: value mismatch,
verdict-vs-rule contradiction, non-finite value). Verdict containment uses a
longest word-boundary match so "not correlated" beats "correlated"; a
band-edge **borderline guard** passes rather than flap-fails. The two-tier
guarantee text is verbatim in the module, the card caveat, and diagnostics.

**Wiring (`job_orchestration.py`).** The check runs in
`_record_codegen_worker_dispatch` after a successful sandbox render, before the
artifact is served. `{pass, verified, unverified_caveat}` serve immediately;
`{repair_contradicted, repair_soft}` feed a `synthetic_error` into the **shared**
codegen repair loop (same `max_codegen_repair_attempts` budget as sandbox
failures). On exhaustion the last successful render is still served — with the
answer **withheld** (contradicted) or shown **with a caveat** (soft), always
`answer_verification="unverified"`. The new `answer_verification` /
`withheld_answer` values thread `_finish_codegen_success` →
`_record_worker_rendered_artifact` → `_build_worker_artifact_metadata` →
snapshot chart → card. The worker `_normalize_render_metadata` passes `claims`
through unchanged (check-only; delete it → output byte-identical, the D3
reconciliation), and `_CODEGEN_PROMPT_RULES` now instructs the model to emit a
well-formed claim.

**Surfacing.** Schemas add `render_metadata.claims` (3 copies) and
`chart.answer_verification` (artifact + snapshot, 2 copies each), all
byte-identical. The Lit card renders three states — verified (no caveat),
unverified (answer + caveat), withheld (a "couldn't produce a verifiable
answer" line + caveat) — with the caveat as a **separate element**, never
spliced into `answer_text` (§4: the verdict prose is never edited).

**Post-review hardening.** A fresh-context architecture-review subagent
returned CONCERNS on one real gap: `_check_claim` received `delivered_entity_ids`
but never read it, so a claim citing a non-delivered/unallowlisted entity
silently became an unverified caveat (spec §1 / invariant #1). Fixed —
step 1 now rejects `claim.inputs ⊄ delivered_entity_ids` as
`grounding_claim_malformed` (repair_soft), with tests. The reviewer's other
note (the single global `_TOLERANCE` applied across correlation / means /
hour-counts) is an accepted tranche-1 coarseness, not a violation.

**Verification.** Suite **366 passed / 4 skipped** (+39 grounding tests, incl.
BDD scenarios A/B/C/E/F/G/H/J, negation safety, the allowlist gap, and edge
cases); frontend **35 passed** (+9 grounding card tests). Eval
`model_authored_analysis` PASS. Schema byte-parity (3× render-result, 2×
artifact, 2× snapshot) + bundle sync verified via md5sum. Version bumped
0.2.3→0.2.4 in `const.py` + `manifest.json`. BDD evidence at
`docs/bdd/answer-grounding-check/answer-grounding-check-bdd.md`.

**Next session — choose one:** (A) **4d event anchors** (tranche 2): anchor
re-detection over delivered raw-state series per spec §1a
(`grounding_anchor_unfound` / `grounding_anchor_mismatch`); the deferred-caveat
path already exists, so this is additive. (B) **Floor-model claim-emission
rate** (spec proof req #4): extend the answer-family benchmark to check that
`gemma4:e4b` reliably emits a well-formed claim recipe (real HA data stays
gitignored). Toward a live test (orthogonal): packet 3 (scipy + seaborn into the
worker image, CT103 rebuild) → deploy the worker as a running homelab
`docker_host` compose service → point the integration at it → ship via HACS.

### 2026-07-03 (5th session) — ADR-0031 ACCEPTED; tranche-1 answer channel + timestamp boundary shipped (0.2.3); the deterministic verdict-grounding check designed & specced

ADR-0031 is accepted and its first tranche is being built. Branch
`adr-0029-worker-codegen-eval`; the spec/ADR/docs work is pushed through
`0436eef`, but the two implementation commits (`068d7ef`, `c833991`) are
**committed locally and NOT pushed** (ask before pushing). *(Corrected at the
8th-session closeout: both since pushed.)*

**Accepted + specced.** ADR-0031 draft→accepted (`7d266cb`): the now-met
proof-gate paragraph was dropped, and the `CLAUDE.md`/`AGENTS.md` identity line
moved from "visualization assistant" to "data-analysis assistant" (D1). The
paired spec `model-authored-analysis` + BDD was written and **accepted**
(`9d52103`→`0436eef`), defining all seven tranche-1 contract surfaces.

**Packet 1 — the answer channel (`068d7ef`, 0.2.1→0.2.2).** Isolinear now ships
a grounded natural-language answer alongside the chart, purely additive on the
codegen render path (the PNG pipeline is untouched). The sandbox
`_normalize_render_metadata` passes a stripped, non-empty `answer_text` through
the existing metadata channel (no security-model change); it is additive/optional
on render-result, artifact-metadata, and job-snapshot (docs + packaged + worker
copies byte-identical); it threads worker-artifact→complete-snapshot
`chart.answer_text`; the Lit card renders it under the caption
(`[data-testid=analysis-answer]`, bundle rebuilt + synced). The codegen prompt
instructs the model to COMPUTE and f-string the answer, deriving verdicts rather
than asserting them. Grounding is proven deterministically: the sample history
71.2/71.8 forces exactly "The average reading is 71.50 degF." at the sandbox
boundary and over the HTTP wire (`evals/model_authored_analysis.py`); the
integration end-to-end test confirms the number reflects the real job history.

**Packet 2 — the epoch-ms timestamp boundary / D9 (`c833991`, 0.2.2→0.2.3).**
The codegen path hands the model epoch-ms integers, never raw HA ISO strings —
killing the benchmark's dominant failure class (`pandas.to_datetime` inferring
one format from HA's mixed-precision first row). Rather than overload the shared
`ts`/`x_min`/`x_max` string contracts, an additive integer `ts_epoch_ms` is added
to history points (history-series schema, all three copies), precomputed by
`_timestamp_to_epoch_ms` (robust to on-the-second + microsecond + `Z` + naive-UTC
+ int passthrough + fail-soft) at both codegen build sites; `_codegen_request_view`
strips raw `ts` from the prompt so the model literally never sees an ISO string.
The safe/Pillow paths are untouched.

**The deterministic verdict-grounding check — designed & specced (packet 4).**
The open half of ADR-0031 D8a — how to deterministically catch a free-text
qualitative verdict that contradicts the data ("Yes … r=0.04") without violating
D3's rejection of integration-side assembly — was handed to a Fable subagent for
design. It produced the **claims ledger**: the generated code emits an optional
`claims` record (the full recompute recipe `{metric, inputs, window?, params?,
value, verdict?, rule?}`) used ONLY for checking — delete it and the user-visible
output is byte-identical, which is the D3 reconciliation (the ledger is to the
answer what the PNG is to the visual validator: reviewed, not composed). A second
Fable pass hardened it against a "does this generalize past correlation?"
critique: the claim now carries the window/params/event-anchor so parametric
metrics reproduce faithfully, event anchors are reproducible under four crisp
criteria (§1a), a three-state **verified / unverified-caveat / contradicted**
boundary is drawn (contradicted requires positive evidence — inability to check
is never contradiction), and the two-tier guarantee (value↔data inside the
metric registry, internal-consistency-only outside) is stated verbatim. The human
ratified; it is distilled into the **accepted** spec `answer-grounding-check` +
BDD, with the research note `answer-verdict-grounding-check` (the design rationale
of record) **promoted-to-spec**.

**Verification.** Suite **327 passed / 4 skipped** (312 baseline → 320 packet 1
→ 327 packet 2); frontend **26 passed** (+3); evals `model_authored_analysis`,
`codegen_generation_path`, `codegen_sandbox` PASS; schema byte-parity + bundle
sync green; `git diff --check` clean. Inline architecture-invariant review OK
(both packets are additive on the accepted codegen path — allowlist #1, sandbox
#3, render-family #9, and the data boundary are all untouched); a fresh-context
architecture-review subagent was not spawned (available on request).

**Next session — implement `answer-grounding-check` (packet 4) in sub-packets:**
4a the metric registry (mean / delta / pearson_r / rolling_mean / daily_max/min /
hours_above, recompute over normalized history) + the number half, wired into
`_record_codegen_worker_dispatch` before serve, repairing via the shared codegen
loop; 4b the `render_metadata.claims` schema + `_normalize_render_metadata`
passthrough + the codegen prompt extension + the deterministic check
(steps 1–6 + the yes/no tripwire); 4c the `chart.answer_verification` schema +
the card caveat/withheld-answer states with the two-tier-guarantee copy; 4d event
anchors as tranche 2 (claim shape fixed now, re-detection deferred). Toward a live
test (orthogonal): packet 3 (scipy + seaborn into the worker image, CT103 rebuild),
then deploy the worker as a running homelab `docker_host` compose service, point
the integration at it, and ship 0.2.3 via HACS.

### 2026-07-02 (4th session) — ADR-0031 DRAFTED + hardened by a real-data benchmark; direction: Isolinear answers questions, not just charts

Exploration + design session (no integration code changed; branch
`adr-0029-worker-codegen-eval`, all pushed through `ac71de8`). **ADR-0031
(`docs/decisions/0031-model-authored-analysis.md`, status: DRAFT) — to be
ACCEPTED next session, then spec + BDD.** The direction: with pandas +
open-ended sandboxed codegen, Isolinear becomes a plain-language data analyst
for the house — a question gets a **grounded natural-language answer + a
supporting chart**, both computed by the worker.

**ADR-0031 decisions (9):** (1) identity expands visualization→analysis;
(2) first slice = always answer + chart (`answer_text` additive, PNG pipeline
untouched); (3) **grounding principle** — generated code computes AND formats
the answer (placeholders filled in-sandbox; the number can't be hallucinated),
extended to qualitative verdicts (compute the "Yes/No", don't assert it);
enforced by prompt + eval backstop, not structural decomposition (capability-
floor rationale: gemma4:e4b is the baseline, everyone runs that or better);
(4) modality model-decided, deterministically validated (invariant #9 intact);
(5) the ADR-0030 transforms scope merges in as tranche 1 (cross-sensor math +
smoothing); (6) library allowlist principle (training-saturation + pure-compute
+ genuinely-new) → **add scipy + seaborn** now, statsmodels/sklearn tier-2,
plotly/prophet/duckdb rejected; (7) TTS deferred; (8) **two-part quality
validation** — deterministic answer-grounding check (broken numbers) + a
**capability-gated visual validator** (broken pictures), with a
**progressive-verification UX** (show first render immediately + "Checking our
work…" indicator, verify in place, REVISE→"found something off, revising now"
+ bounded repair, fail-soft); (9) **normalize timestamps at the data boundary**
(hand the model epoch ints, never raw ISO).

**The benchmark (committed `evals/analysis_benchmark/`; real HA data + generated
code GITIGNORED as private).** 16 prompts × gemma4:e4b + qwen2.5-coder:7b,
generated `render_chart` code **executed against 7 days of real HA history**
(16 entities pulled via the HA REST API, token from the ha-access memory).
Findings that became decisions 6/8/9: **with a clean epoch-ms contract, gemma
12–13/16, qwen 7–11/16** (both ≈2/16 on a raw-ISO-timestamp contract — the
dominant failure was ONE `pandas.to_datetime` format-inference gotcha on HA's
mixed-precision timestamps, NOT model incompetence; only `format='ISO8601'`
fixes it, and epoch-ms erased the whole class). **accept≠quality reconfirmed
hard** (flat-zero seasonal decompose, single-point `r=nan` scatter, `0.00 °F/hr`
cooling all "passed" execution). **Both validators demonstrated live:**
multimodal gemma (has `vision`; qwen-coder does NOT — checked via Ollama
`/api/show`) flagged the flat-zero decompose that execution + answer-text
missed; a structured checklist prompt beat a vague one; the visual-repair loop
fixed the decompose end-to-end. The benchmark is ADR-0031's **acceptance proof
gate**.

**Parked stub (STATUS open-queue (l)):** conversational refinement + saved
live-refresh dashboard cards (integration-scheduled, no model in the refresh
loop; axes-drift open question).

**Next session:** accept ADR-0031 → write `docs/specs/model-authored-analysis.md`
+ paired BDD (contract surfaces: `answer_text` + `verification_status` schema
fields, epoch-timestamp render-data shape, the validator config gate +
checklist prompt, benchmark-gate proof requirements) → implementation packets.

### 2026-07-02 (3rd session) — ADR-0030 IMPLEMENTED in code (pandas, 1024MB cap, repair-everything, codegen-primary render default), version 0.2.1

The ADR-0030 decisions are now real in code (the prior session only recorded the
decisions + purged scaffold). Four bounded changes on branch
`adr-0029-worker-codegen-eval`, all committed (`4532ba5`, `a038b9b`, `940887b`):

1. **pandas + 1024MB cap (`4532ba5`, worker-only).** `pandas>=2,<3` in
   `worker/requirements.txt` + the sandbox import allowlist (exact-match,
   alongside numpy); sandbox `memory_limit_mb` 256→1024 (the schema already
   permitted 1024 — no schema change; the Pi-compat test now pins 1024 and
   asserts pandas is allowlisted). **Proven LIVE on CT103** (root SSH from
   claude-box; `docker build` via `tar | ssh`, rsync absent on the host): image
   rebuilt **526MB** (was 419MB), in-container worker suite **27 passed, zero
   skips**, and a real pandas `resample("1h").mean()` render returned a valid
   PNG over `POST /v1/render` under the new cap (eyes-on verified). CT103 left
   clean — throwaway container + `/tmp/iw-build` removed; only the rebuilt
   `isolinear-worker:dev` image retained beside the compose-managed
   ollama/frigate/plex/caddy. (Note: the homelab `docker_host` role has since
   LANDED — the earlier coordination dependency is resolved; deploying the
   worker as a compose service is now an available homelab follow-up.)

2. **Repair-everything (`a038b9b`, integration).** The packet-4 `unsafe_code`-
   is-terminal rule is gone: every sandbox failure class is repairable, bounded
   by `max_codegen_repair_attempts`; the worker re-runs the full static check +
   sandbox on every fresh dispatch, so the security boundary still enforces —
   repair only gets another try at the gate, never around it. `unsafe_code`
   through exhaustion still terminates (now → fallback, see #3).
   `CODEGEN_TERMINAL_SANDBOX_ERROR_CODES` deleted.

3. **Codegen-primary render default (`940887b`, integration + card, 0.2.0→0.2.1).**
   The `codegen_enabled` opt-in boolean is replaced by a **`render_path` select
   (`auto` | `pillow`, default `auto`)**; legacy stored `codegen_enabled` values
   are dropped to `auto` on options normalization. With `auto` + a worker +
   planner, codegen renders; **codegen failures (generation failure, repair
   exhaustion incl. persistent `unsafe_code`, worker transport fault) now FALL
   BACK to the trusted Pillow renderer and COMPLETE the job — surfaced, never
   silent**: the artifact + snapshot `chart` carry `render_path` +
   `render_fallback_reason` (additive optional fields on both synced copies of
   the artifact-metadata + job-snapshot schemas), and the Lit card renders a
   warning-colored fallback notice under the caption. An explicit
   `render_path: pillow` renders in-process with **no** fallback reason (a
   choice is not a fallback). This supersedes packet-4's fail-closed
   `codegen_render_failed` posture (whose only purpose was keeping the packet-5
   eval unpolluted — that eval has run and ADR-0029 is decided KEEP; silent
   masking is still forbidden, hence the mandatory surfacing).

**Invariant #6 rewritten in BOTH `AGENTS.md` and `CLAUDE.md`** to
"Codegen-primary, fallback-safe rendering" (ADR-0030, ADR-0008) — the prior
session updated CLAUDE.md only; the stale AGENTS.md copy (still "chart-spec-
first … codegen is an opt-in advanced path") was caught + aligned at this
closeout. The two files are now byte-identical for #6.

**Verification:** full suite **312 passed / 4 skipped** (309 baseline + 3 net
new codegen tests); frontend **23 passed** (2 new fallback-notice tests);
`codegen-generation-path` spec + BDD + evidence revised (10 scenarios A/B/C/D/
D2/E/F/G/H/I, raw outputs, timestamped); all six touched evals PASS
(`codegen_sandbox`, `codegen_generation_path`, `worker_http_server`,
`timeline_render_family_routing`, `composition_membership_prune`,
`model_resolved_window_data_source`); schema byte-parity + bundle sync green;
architecture review OK (no invariant violations; the flip executes accepted
ADR-0030, no new ADR); BDD-evidence review OK. **NOT pushed** (commit-only per
norms; ask before pushing).

**DIRECTION PIVOT declared this session (Colin) — ADR-0031, not yet written:**
with pandas + open-ended sandboxed codegen, Isolinear expands beyond charts to
answer questions in **natural language** ("are the upstairs and downstairs
temps correlated?" → "Yes — the correlation coefficient is 0.42"), computed by
the worker. Decisions captured: **always answer + supporting chart** in the
first slice (so `answer_text` is purely additive — the PNG pipeline is
untouched); the **grounding principle** that the generated code both computes
AND formats the answer sentence (f-string over computed values — the number
can't be hallucinated; same trust level + repair loop as charts, NOT a second
free-text pass); **modality intent model-decided, deterministically validated**
(invariant #9 intact — modality sits above chart-family routing); the
**earlier-scoped transforms spec (cross-sensor math + smoothing) MERGES into
ADR-0031** as the shared compute layer; **TTS deferred** (card-side browser
speech is read-only-safe; HA TTS service calls collide with invariant #2 — its
own decision). **Next packet = write ADR-0031 + spec `model-authored-analysis`
+ BDD (draft), then implement.** The runner's `render_chart` metadata dict is
the wire for the answer (no sandbox change); render-result/artifact/snapshot
gain optional `answer_text`; the card promotes the caption slot.

### 2026-07-02 (2nd session) — ADR-0029 resolved KEEP; ADR-0030: matplotlib codegen is the primary render path; the simulated scaffold is purged

The human resolved the ADR-0029 kill condition on the packet-5 data: **KEEP**.
The worker and the codegen path are permanent architecture. The same session
recorded the larger direction change as **ADR-0030 (accepted)** and executed a
project-wide cleanup.

**ADR-0030 decides:** sandboxed **matplotlib codegen is the PRIMARY render
path** when a healthy worker is configured; the **Pillow renderer becomes the
fallback** (no worker / unhealthy / repair exhaustion — always surfaced in
render metadata and the card, never silent) and remains an explicit option.
The **ChartSpec stays the validated planning contract and the data boundary**
(invariants #1/#3/#4/#5 unchanged). The **model is empowered to transform data
in generated code** — cross-series math (e.g. averaging two sensors),
resampling, derived series — instead of growing the closed ChartSpec transform
enum (which the Pillow renderer never implemented anyway: every operation but
`none` returns `transform_not_supported`). **pandas** is added to the worker
image; the **sandbox memory cap rises 256MB → 1024MB**; and **every sandbox
failure class is repairable, including static security rejections** — bounded
by `max_codegen_repair_attempts`, with the full static check + sandbox re-run
on every attempt (the boundary still enforces; repair just gets another try at
the gate). `CLAUDE.md` invariant #6 is rewritten accordingly.

**The purge (commit `f8f7760`):** the entire pre-pivot simulated universe is
deleted — `src/Isolinear/` (~15K LOC of `*_anchor.py` verifiers + the
3,334-line `fake_slice.py`), 29 anchor test files, 48 fake-path evals, and 23
`*scaffold-spec.md` docs: **135 files, ~40,156 deletions**. Production code
imported none of it (verified; only docstring mentions remain). The suite drops
from 623 to **309 passed / 4 skipped (~7s)** — the deleted half tested only the
deleted scaffold. The 7 real-path evals (`codegen_*`,
`composition_membership_prune`, `model_resolved_window_data_source`,
`timeline_render_family_routing`, `worker_http_server`) plus `evidence.py`
remain.

**ADR consolidation (commit `255b0c3`, human-approved immutability exception):**
0004 superseded by 0030 (its ChartSpec-contract half carried forward); 0029
draft→accepted with the KEEP outcome recorded; 0018 + its spec draft→accepted
(artifact serving has been implemented and live since ~0.1.20); 0015/0016
deprecated and moved to `docs/decisions/archive/` (designed for the simulated
worker — their runtime machinery in `custom_components/` still runs and is
scheduled for simplification); 0017 labeled historical in the index.

**Version: 0.1.49 → 0.2.0** (closeout addendum, human's call) — the minor bump
marks the ADR-0030 direction change; `manifest.json` + `const.py` updated,
suite re-verified green post-bump.

**Next packet — implement ADR-0030 in code:** (1) pandas into
`worker/requirements.txt` + image rebuild on CT103; (2) memory cap 1024MB +
update the `memory_limit_mb <= 256` test; (3) the repair policy in
`job_orchestration.py` (packet-4 currently makes `unsafe_code` terminal);
(4) flip the render default to codegen-primary with surfaced Pillow fallback
(spec update + version bump). After that: the model-authored transforms spec;
simplify the deprecated worker-durability machinery (~3.4K LOC); split the
7.7K-line `job_orchestration.py`.

### 2026-07-02 — ADR-0029 packet 5 landed: the codegen reliability eval + sandbox codegen-friendliness fixes (the keep/remove data)

Packet 5 produces the data the ADR-0029 keep/remove decision rests on: a
**codegen accept/reject/repair reliability eval** run **live through the CT103
worker sandbox**. The eval (`evals/codegen_reliability.py`) drives the new
**42-prompt real benchmark corpus** (`evals/prompts/benchmark_prompts.json` +
README; 35 of the 42 are chartable) through two 3060-class local models —
**`gemma4:e4b`** and **`qwen2.5-coder:7b`**: each model **generates** matplotlib
from a schema-valid ChartSpec plus synthetic history, the code is **rendered LIVE
through the CT103 worker sandbox**, and an **integration-orchestrated repair
loop** (max 2 repairs) feeds sandbox errors back on recoverable failures. The
report gallery is regenerated by `evals/prompts/gen_report.py` into
`evals/prompts/reliability_results.json` + `reliability_report.md` +
`renders/` (66 PNGs).

**Result: both models accept 33/35 (3 recovered via repair each).**
`gemma4:e4b` went **24/35 strict → 33/35** with the refined repair policy
(repair recovered syntax typos plus `typing`/pandas imports);
`qwen2.5-coder:7b` went **30/35 → 33/35**. Crucially there were **no sandbox
false positives** — all 4 remaining rejects are legitimate: gemma `ov-02` is a
forbidden `locals()` call (the security gate working as intended — terminal);
qwen `ov-03`/`ov-04` are a real numpy `isfinite` `TypeError` (a genuine code bug
the repair didn't fix); gemma `agg-03` is `output_missing` (the code ran but
never wrote the PNG).

**The refined repair policy** (built in the eval, recommended for the
integration) distinguishes genuine **SECURITY** violations — `forbidden_import`,
`forbidden_attribute`, `forbidden_call`, `dunder_attribute`, `scope_escape` —
which stay **TERMINAL**, from **recoverable static failures** (`syntax_error`,
`import_not_allowlisted`) and `runtime_error`, which are **REPAIRABLE** (the
sandbox error is fed back to the model). This is a refinement of the packet-4
loop, which currently treats *all* `unsafe_code` as terminal.

**The key finding is a strong KEEP signal for ADR-0029:** the two models fail in
**characteristically different ways** — gemma trips **STATIC** checks it can
repair (syntax / imports), while qwen trips **RUNTIME** limits (the 256 MB
address-space cap). 3060-class local models produce good, safe matplotlib at
**~94% accept with repair**.

Alongside the eval, a batch of **sandbox codegen-friendliness fixes** landed —
each a **boundary-preserving correction of an under-specified allowlist**, not a
relaxation of the security model: allow `from`-imports that target an
allowlisted module (checks the module after `from`, not the qualified name;
forbidden and relative imports still rejected — **security-reviewed OK**,
`40b9464`); expand safe builtins (`next`/`iter`/`map`/`filter`/`set`/… plus
common exceptions) and allow `datetime._strptime` (`a11ae4f`); whitelist
`numpy`/`itertools`/`functools`/`collections` and unblock the `replace`
attribute false-positive (`str.replace` is safe; `os.replace` is unreachable and
audit-blocked, `03fa792`); whitelist `typing` (`bfd99a0`); and pre-warm a
**READ-ONLY** matplotlib font cache in the Dockerfile
(`ISOLINEAR_WORKER_MPL_CACHE`, ~20% faster renders, no font warning, **no
write-policy relaxation**, `882af2e`). All sandbox changes are **worker-only** —
no integration version bump (still **0.1.49**). The full suite stayed
**623 passed, 4 skipped** throughout.

**Three open decisions recorded for the human (all non-blocking):** (1) **pandas
support** — gemma reached for pandas (not installed) and repair worked around it;
adding it is an image-size decision; (2) **raise the 256 MB sandbox memory cap**
— qwen's two remaining rejects plus earlier `MemoryError`s hit it, and there is
an explicit test asserting `memory_limit_mb <= 256`; this is a resource-policy
call; (3) **adopt the security-vs-recoverable repair distinction in
`job_orchestration.py`** — the packet-4 loop treats all `unsafe_code` as
terminal, and the eval showed distinguishing repairable syntax/import failures
from terminal security violations recovers most gemma failures.

**Remaining ADR-0029 work:** the eval data now exists, so the **keep/remove
DECISION** is decidable but not yet decided — ADR-0029 stays **draft** until the
human calls it. Deploy target unchanged: CT103/10.0.1.39, standalone amd64
GPU-less Docker via the homelab `docker_host` role.

### 2026-07-01 — ADR-0029 packet 4 landed: the model codegen path + integration-orchestrated repair (0.1.49, `b22992b`)

The worker can render matplotlib (packet 3); packet 4 is the *integration side*
that makes codegen a real product path — the model that **generates** the
matplotlib code and the loop that **repairs** it on a retryable sandbox error.
It is an **opt-in** render path behind a new options toggle **`codegen_enabled`
(default `False`)**: when off, the trusted in-process ChartSpec renderer is the
default and untouched (invariant #6, chart-spec-first). Codegen uses a
**separately configurable model** — **`codegen_model`** (config field, already
present) that **defaults to the planner model when unset** (`codegen_model or
planner_model`), so codegen can point at a code-specialized model without
touching the planner. Both knobs are cleanly removable (packet 5 may revisit).

**Model-provider generation** (`custom_components/isolinear/model_provider.py`):
two new methods on the Ollama-compatible client emit **freeform Python** via one
`/api/chat` call each — **`generate_chart_code`** (system prompt asks for a
single `render_chart(data, output_path)` matplotlib function implementing the
already-validated ChartSpec) and **`repair_chart_code`** (feeds the previous
code plus the sandbox error — `error.code`, `error.message`, and the traceback
from `error.details` — back and asks for corrected code). Output is
markdown-stripped with the existing `_strip_markdown_json` helper; **no
constrained-decoding `format`** is set (Ollama's `format` is for JSON, not
Python). Only the validated ChartSpec + normalized, allowlist-checked render
data cross into the prompt — the **data-boundary projection
`_codegen_request_view`** strips `request_id`/tokens/secrets, so no HA token,
worker token, model token, or secret is ever placed in a generation/repair
prompt (data boundary; invariants #1/#3).

**The repair loop is integration-orchestrated**, in
`job_orchestration.py`. When `codegen_enabled` is true and a worker client is
configured, only the render step is replaced (planning, entity selection,
allowlist enforcement, and deterministic render-family routing stay upstream and
unchanged): **generate** the code, dispatch a `render_mode: "codegen"` request
carrying `codegen.python_code` over the existing `HttpJsonWorkerRenderClient`,
and on a **retryable** sandbox error (`runtime_error`/`timeout`/`output_missing`/
`output_too_large`) ask the model to repair given the previous code + error/
traceback and **re-dispatch**, up to `max_codegen_repair_attempts` (each
re-dispatch is a fresh `POST /v1/render`; the worker re-runs static safety every
attempt). **`unsafe_code` is terminal** — never repaired (it's a security gate,
not a correctness bug). The worker-local `invoke_codegen_with_repair` convenience
is **NOT** used over HTTP: the data boundary forbids the worker from holding a
model client, so the integration drives the loop with its own model provider.

**Fail-closed, no silent fallback.** On generation failure, `unsafe_code`, or
exhausted repair, the codegen path returns a dedicated card-facing
**`codegen_render_failed`** failed snapshot carrying the final sandbox/provider
error code — it does **not** silently fall back to the trusted renderer.
Rationale: a silent trusted fallback would mask codegen failures and muddy the
packet-5 accept/reject/repair eval — the very data the ADR-0029 keep/remove
decision rests on.

**Proven LOCALLY only.** The full orchestration (generate → dispatch → repair →
serve / fail-closed) is exercised against an **in-process sandbox worker**, and
the wire end-to-end is proven by booting the **real packet-2
`isolinear_worker.http_server` on an ephemeral port** and driving the loop over
the actual HTTP boundary into a real PNG (`evals/codegen_generation_path.py`). No
CT103 / remote host is touched. The **live CT103 end-to-end + the codegen
accept/reject/repair reliability eval are packet 5** — the data the keep/remove
decision rests on. Suite `620 passed, 4 skipped`; both evals PASS
(`codegen_generation_path.py`, `worker_http_server.py` — no regression). Version
bumped **0.1.48 → 0.1.49**. `codegen-generation-path` spec + BDD promoted
draft→ACCEPTED (both reviews OK — architecture review: no invariant violations;
BDD-evidence review: OK).

### 2026-07-01 — ADR-0029 packet 3 PROVEN LIVE on CT103 (+ OpenBLAS sandbox fix `2bb2747`)

The packet-3 worker container image is no longer a deferred artifact — it was
**built and run live on the deploy target CT103** (`docker-host`, `10.0.1.39`,
Debian 13 trixie, x86_64, Docker 29.5.2, 6 cores) from a fresh clone at commit
`2bb2747`, and **all six previously-deferred BDD scenarios (A–F) now pass** with
raw outputs recorded in the evidence file. The image **builds on amd64 with
matplotlib-3.11.0 installed from prebuilt wheels** (no source build; final image
418MB); `GET /v1/health` reports **`ready`** (matplotlib importable under
`python -I` from the system site-packages — the packet's whole purpose); a
**real matplotlib chart rendered end-to-end over `POST /v1/render`** (a valid
16557-byte PNG, signature `89504e470d0a1a0a`, written to the container work
root); the **three matplotlib-gated tests un-skip and pass in-container**
(`24 passed`, zero skips); the image is **HA-agnostic** (an in-image `find`
returns nothing from `custom_components`/`src`); the container **`HEALTHCHECK`
reports `healthy`**; and startup still **fails closed** on a missing or short
token. This validates the core ADR-0029 premise for real: **the sandbox can
actually render matplotlib in the target deployment** — a key de-risking of the
codegen experiment before packet 4 (the codegen model) and packet 5 (the
accept/repair reliability eval).

**The live build surfaced a real bug — the most important thing it produced.**
matplotlib *imported* fine under `-I` (so health was `ready`), but the **first
actual render failed** with
`OpenBLAS error: Memory allocation still failed after 10 retries, giving up.`
Root cause: numpy's OpenBLAS backend reserves **per-core address space** for its
thread pool **at import time**, scaled to the host CPU count — CT103 has **6
cores**, so that reservation exceeded the sandbox's **256 MB `RLIMIT_AS`** cap
and aborted before any chart was drawn. It only surfaced here because the safe
(non-numpy) render path is unaffected and the matplotlib tests skip on the dev
box (where `-I` cannot import matplotlib at all). **Fixed in `2bb2747`:** pin
`OPENBLAS_NUM_THREADS` / `OMP_NUM_THREADS` / `MKL_NUM_THREADS` /
`NUMEXPR_NUM_THREADS` / `VECLIB_MAXIMUM_THREADS` to `1` in the sandbox's stripped
subprocess environment (`_sandbox_environment` in
`worker/isolinear_worker/codegen_sandbox.py`) and add them to the policy's
`explicit_environment_keys`. These variables only ever **reduce** resource use,
so the **sandbox is not weakened** — the `-I` isolation, import allowlist, audit
hook, fixed output path, timeout, and `resource` limits are all unchanged
(invariant #3 intact). After rebuilding the image at `2bb2747`, all scenarios
pass.

The **`worker-container-image` spec is now `accepted`** (the documented
acceptance trigger — Scenarios A–F passing with raw outputs recorded — is met);
the BDD scenarios A–F are retagged verified-on-Docker-host, and the evidence
file carries the raw CT103 outputs plus a dedicated OpenBLAS finding/fix
subsection. The integration is **untouched and NOT version-bumped** (worker-only,
matching packets 1–3). The dev-box suite is unchanged (`595 passed, 3 skipped` —
the 3 matplotlib skips only flip inside the container). The bearer token used on
CT103 was an ephemeral `secrets.token_urlsafe(24)` (never printed) and the temp
clone was removed; the **proven `isolinear-worker:dev` image (418MB) is retained
on CT103**.

**Remaining ADR-0029 packets:** (4) codegen path in the model provider + real
repair model; (5) end-to-end proof + the codegen accept/repair reliability eval
the keep/remove decision rests on. Deploy target: CT103/10.0.1.39, standalone
amd64 GPU-less Docker via the homelab `docker_host` role.

### 2026-07-01 — ADR-0029 packet 3 landed: the standalone amd64 worker Dockerfile

The packet-2 HTTP server now has a container to run in. A single-stage
**`worker/Dockerfile`** (`python:3.12-slim`) plus **`worker/.dockerignore`**
packages the self-contained `isolinear_worker` package into a linux/amd64 image.
The load-bearing choice: **matplotlib is installed into the interpreter's
*system* site-packages** — no venv, no `--user`, a plain
`pip install -r requirements.txt` as root — because the sandbox runs generated
code under `python -I` (isolated mode excludes user site-packages). Only a
system-site install lets the packet-2 readiness probe's `python -I -c "import
matplotlib"` subprocess succeed, so **`GET /v1/health` flips from `not_ready` to
`ready`** and the worker can actually render. That flip is the whole purpose of
this packet — it dissolves the ADR-0017 matplotlib-on-HAOS/aarch64 blocker by
moving matplotlib into the worker's own amd64 image.

The image runs unprivileged as a non-root **`worker` user (uid/gid 10001)**; the
`work_root` where PNGs are written is created, chowned to that user, and declared
a `VOLUME` so a host/orchestrator can mount durable or tmpfs artifact storage.
Config is 12-factor and matches packet-2's `load_config_from_env` exactly
(`ISOLINEAR_WORKER_BIND_HOST`/`_PORT`/`_WORK_ROOT` as `ENV`); crucially
**`ISOLINEAR_WORKER_TOKEN` is never an `ENV`/layer** — it is a secret supplied at
`docker run` time, and with no valid token the entry point fails closed (non-zero
exit, no socket bound). The **`HEALTHCHECK` is stdlib-only** (no curl/wget added):
it reads the token + port from the container's own runtime env, makes an
authenticated `/v1/health` request, and exits 0 only when the transport returns
200 **and** `health.status == "ready"`. The entry point is
`ENTRYPOINT ["python","-m","isolinear_worker.http_server"]`, mapping directly to
the packet-2 `__main__` guard. The image is **HA-agnostic by construction**: the
build context is `worker/`, so nothing from `custom_components/`, `src/`, or
`frontend/` is even reachable (the `.dockerignore` trims the rest).

Docker is **not installed in this authoring environment**, so the **image build +
container run proofs are DEFERRED to a linux/amd64 Docker host** (deploy target
CT103/10.0.1.39). **6 of the 9 BDD scenarios (A–F: image build, fail-closed
startup on a missing/short token, `/v1/health` → `ready`, `/v1/render` returning a
PNG, the 3 matplotlib-gated tests un-skipping in-container, and no HA code in the
image) are honestly marked `DEFERRED (needs Docker host)` with exact reproduction
commands recorded in the evidence file** — no build log is fabricated, matching
the repo's established live-retest deferral pattern. The 3 STATIC scenarios (G
entry-point, H config-contract, I suite-green) carry real raw outputs. Because
the core proof is that deferred live build, the **spec is intentionally left
`draft`** (not promoted to accepted) until it passes on a Docker host. The
integration is **untouched and NOT version-bumped** (worker-only, matching
packets 1–2). Full suite unchanged: **`595 passed, 3 skipped`** (the 3 matplotlib
skips only flip inside the container). BDD-evidence review OK; architecture review
OK (no invariant violations — the sandbox security model at invariant #3 is
untouched: matplotlib in system-site only makes an already-allowlisted import
present, and the allowlist still governs generated code; base image / non-root
user / healthcheck / VOLUME are all within ADR-0029's decided
"standalone amd64 Docker first" scope, so no new ADR). One optional note carried
forward: digest-pin `python:3.12-slim` when the image is first built.

**Remaining ADR-0029 packets:** (4) codegen path in the model provider + real
repair model; (5) end-to-end proof + the codegen accept/repair reliability eval
the keep/remove decision rests on. Deploy target: CT103/10.0.1.39, standalone
amd64 GPU-less Docker via the homelab `docker_host` role.

### 2026-07-01 — ADR-0029 packet 2 landed: the standalone worker HTTP server

The packet-1 worker module now has an HTTP front door. A new standalone server
at **`worker/isolinear_worker/http_server.py`** wraps the self-contained
`isolinear_worker.codegen_sandbox` public API in a long-running process built on
the Python stdlib `http.server`/`ThreadingHTTPServer` — **no new runtime
dependency** (invariant #8), which also keeps the packet-3 image minimal. It
serves the ADR-0012 worker transport: **`POST /v1/render`** (run the sandbox on a
model-generated matplotlib render request) and **`GET /v1/health`** (ADR-0014
readiness probe).

Request handling is **strictly fail-closed and ordered on every request**: auth →
API-version → envelope-schema → sandbox. Bearer auth uses a constant-time
`hmac.compare_digest` compare, and **no sandbox subprocess is ever spawned for an
unauthenticated request**. The transport/sandbox failure split is deliberate:
**sandbox-level failures ride inside an HTTP 200** as `{"render_result": {...}}`
(an `unsafe_code`/`runtime_error`/`timeout` outcome is a valid *render* result,
not a transport fault), while **transport faults are non-200** — 401
`unauthorized`, 400 `unsupported_api_version` / `invalid_request`. Token material
never reaches responses or logs (redacted to `Bearer <redacted>`).

Config is 12-factor and HA-agnostic: `ISOLINEAR_WORKER_TOKEN` (**≥24 chars,
fail-closed at startup** — a missing/short token exits 1 with no socket bound),
plus bind host/port and `work_root`. `create_worker_app(config)` is socket-free
and unit-testable; `serve(config)` / `python -m isolinear_worker.http_server` bind
and serve. The server **imports nothing from `custom_components/isolinear/` or
`src/Isolinear/`** — verified by an import-graph test — so it stays deployment-
independent per the ADR-0029/ADR-0012 boundary; the only cross-boundary import
lives correctly in the wire-interop *eval*, not the server.

`GET /v1/health` returns the `integration-worker-health` `response` sub-schema
under `{"health": ...}` (HTTP 200 in both ready and not_ready). On the dev box it
reports `not_ready` with matplotlib `unavailable`: the `-I` sandbox can't import
user-site matplotlib, so this is the **expected dev-box behavior** and flips to
`ready` in the packet-3 container (matplotlib in the system site). The
`evals/worker_http_server.py` wire-interop eval drives the **real
`HttpJsonWorkerRenderClient`** (the integration-side ADR-0012 client) against a
live loopback instance of the server, proving the two halves speak the same
transport. Single `invoke_codegen_sandbox` call — no repair loop (packet 4) — and
the `image_path` is returned as-is (no base64 yet — packet 5).

The HACS-shipped integration is **untouched and NOT version-bumped** (worker-only
change, matching packet 1). One deferrable future refinement noted by review:
`_read_body` returns `b""` on an oversized/invalid `Content-Length`, which
surfaces as a generic `invalid_request` 400 — acceptable fail-closed behavior, not
changed now. Spec + BDD promoted draft→accepted. Verify: full suite
`595 passed, 3 skipped` (the 3rd skip is the new matplotlib-render scenario, same
`-I`/user-site limitation as packet 1's 2 skips); `evals/worker_http_server.py`
PASS; `evals/codegen_sandbox.py` PASS; BDD-evidence review OK; architecture review
OK (no invariant violations).

**Remaining ADR-0029 packets:** (3) standalone amd64 Dockerfile with matplotlib
(where health flips to `ready`); (4) codegen path in the model provider + real
repair model; (5) end-to-end proof + the codegen accept/repair reliability eval
the keep/remove decision rests on. Deploy target: CT103/10.0.1.39, standalone
amd64 GPU-less Docker via the homelab `docker_host` role.

### 2026-06-30 — ADR-0029 packet 1 landed: codegen sandbox promoted to a self-contained worker module

The proven codegen sandbox is now a real, importable, Home-Assistant-agnostic
worker package at **`worker/isolinear_worker/`** (promoted from the retired
`src/Isolinear/codegen_sandbox_anchor.py`). It carries its own minimal schema
validator (`_schema_validation.py`, a deliberate subset-copy of the integration's
`contracts.py`) and a bundled copy of the five schemas it validates
(`worker/isolinear_worker/schemas/`), so it imports nothing from
`custom_components/isolinear/` or `src/Isolinear/` — the deployment-independence
boundary ADR-0029/ADR-0012 require. The sandbox **security model is unchanged and
preserved at parity** (`-I` isolation, import allowlist, audit hook, fixed
output-path write, timeout, `resource` limits, max output bytes); only the
anchor/fixture/verifier scaffolding was dropped and two public signatures cleaned
up (`work_root` replaces `output_directory`; `repo_root` removed; the repair loop
takes an injected `repair(prev, error)->next` callable instead of a pre-baked
code list — a real repair model is packet 4). The HACS-shipped integration is
**untouched** (no new dependency, no version bump).

`tests/test_codegen_sandbox.py` drives the public API for sandbox-codegen
scenarios A-G plus the promotion scenarios (self-containment via a clean-subprocess
`sys.modules` import-graph check; a schema byte-parity drift guard; an
injected-repair loop; a timeout). The matplotlib-rendering scenarios are
`skipUnless` the `-I` sandbox can import matplotlib: on a dev box matplotlib is
user-site-only and `-I` excludes it, so they skip there and run on the worker
container (where matplotlib is in the system site). Suite is green —
`584 passed, 2 skipped` (the prior "3 pre-existing codegen-sandbox failures" were
exactly this environment limitation, now honest skips). `evals/codegen_sandbox.py`
repointed and passing; a real PNG was produced through the promoted public API and
eyes-on-confirmed. Spec + BDD promoted draft→accepted; ADR-0029 stays draft until
the experiment's accept/repair-rate kill condition is decided. Architecture review
OK; its drift-guard recommendation is implemented as a test.

**Remaining ADR-0029 packets:** (2) the worker HTTP server (`POST /v1/render`,
`GET /v1/health`, bearer auth, versioned headers, 12-factor/HA-agnostic) wrapping
`isolinear_worker.codegen_sandbox`; (3) standalone amd64 Dockerfile with
matplotlib; (4) codegen path in the model provider + real repair model; (5)
end-to-end proof + the codegen accept/repair reliability eval the keep/remove
decision rests on. Deploy target: CT103/10.0.1.39, standalone amd64 GPU-less
Docker via the homelab `docker_host` role (homelab half waits on that role
landing).

### 2026-06-30 — Direction: revive the worker to evaluate sandboxed codegen (experiment branch)

A rewrite-vs-refactor review concluded the architecture is sound and the worker
tree is **not** dead weight — it is load-bearing (`__init__.py` aborts setup
without `worker_token_lifecycle`; `job_orchestration.py:55` imports
`worker_renderer`) and ADR-0017 *defers* it on purpose. The new direction
(ADR-0029, draft) **revives** the deferred worker as a deployment-agnostic HTTP
service that runs the existing sandbox on model-generated matplotlib code — the
original product intent, never evaluated because matplotlib won't install on the
HAOS/aarch64 (Alpine) Pi. The worker dissolves that: matplotlib lives in the
worker's own amd64 image.

This is an **experiment with a kill condition**: if a 3060-class local model
can't produce good-enough matplotlib (accept/repair eval), the worker subsystem
is removed and the architecture refactors to in-process-only (its own
superseding ADR). In-process trusted rendering stays the default throughout.

**Data boundary (defense-in-depth):** entity selection, allowlist enforcement,
and history retrieval stay integration-side; only normalized, allowlist-checked
render data crosses to the worker, which never queries HA. The integration
controls what data goes in; the sandbox controls what the code can do.

**Build plan:** (1) promote the sandbox anchor → self-contained
`worker/isolinear_worker/` [spec `codegen-sandbox-module-promotion`, drafted];
(2) worker HTTP server (`/v1/render`, `/v1/health`, 12-factor, HA-agnostic);
(3) standalone amd64 Dockerfile with matplotlib; (4) codegen path in the model
provider + real repair model; (5) end-to-end proof + reliability eval. The hard
parts already exist (the sandbox and the integration-side worker client);
the missing piece is the worker server.

**Deployment:** standalone Docker on CT103/10.0.1.39 (the ollama box), amd64,
GPU-less, deployed via the homelab `docker_host` Ansible role (two-repo split:
Isolinear publishes the image, homelab deploys it; the HA add-on for other users
is a later aarch64 packaging wrapper, deferred). All of this lives on branch
`adr-0029-worker-codegen-eval` (planning committed, not pushed; no integration
code changed yet).

---

MVP design phase closed. The first production Home Assistant custom integration
scaffold, config-flow/options surface, dashboard resource registration surface,
WebSocket command registration surface, job state scaffold, approved entity
catalog, approved history retrieval, and job orchestration scaffold are
anchored, including clarification-answer, retry continuation,
subscription/progress, artifact storage, and render planning scaffold paths.
The model-provider planning scaffold, model-provider retry/backoff policy
scaffold, model-provider health diagnostics scaffold, worker
dispatch/rendering scaffold, worker token provisioning/readiness scaffold,
worker progress streaming scaffold, worker retry/backoff policy scaffold,
worker transport failure retry-classification scaffold, worker failure
snapshot/manual retry integration scaffold, worker health/readiness endpoint
scaffold, worker token rotation/repair scaffold, durable worker health
polling checkpoint scaffold, and durable worker token lifecycle scaffold are
now anchored. The durable
polling maintainability refactor is complete: the checkpoint still stands as
the completed ADR-0015 behavior packet, and the large production and verifier
modules have been split into focused helper modules without schema,
BDD/evidence, eval, or dashboard-card contract changes. A narrow durable
polling hardening follow-up now rejects persisted cancelled polling state
during storage load/resume so unload-cancelled scheduler metadata cannot
resurrect after restart. ADR-0016 now anchors integration-owned durable worker
token lifecycle storage: setup restores only valid same-entry persisted tokens
after lifecycle storage succeeds, fails closed before readiness/renderer setup
on lifecycle storage rejection, and records redacted repair-issue metadata
when restore is impossible.

The reality-pivot implementation packet is now in place under accepted ADR-0017:
the existing Home Assistant WebSocket job flow can use approved metadata,
approved history, an Ollama-compatible planner result, and trusted in-process
matplotlib rendering when the first-real-slice route is enabled and no worker
dispatch is used. ADR-0018 now replaces the temporary WebSocket data URL proof
with production artifact serving: rendered PNG bytes are validated, written to
integration-owned artifact storage, served from `/api/isolinear/artifacts`, and
returned to the dashboard card as same-origin URLs while local filesystem paths
stay server-side. Manual verification has now
run against real Home Assistant core with a real SQLite recorder database and a
network Ollama endpoint using `gemma4:e4b`. That live run closed two runtime
drift issues: registered WebSocket commands now use Home Assistant's
`async_response` scheduler and offload blocking orchestration through Home
Assistant's executor, and the Ollama structured-output schema now narrows
`chart_spec` to the first-slice `time_series` ChartSpec shape.

The dashboard-card long-running smoke hardening packet is complete. The Lit
card now treats `planning`, `fetching_history`, `rendering`, and `validating`
snapshots as active jobs, disables duplicate prompt submission, and polls
`isolinear/v1/job/snapshot` through the integration-owned Home Assistant
connection until a terminal snapshot arrives. The mounted `happy-dom` Vitest
smoke proves delayed `job/start` -> automatic `job/snapshot` -> chart-first PNG
result behavior, while the focused Python smoke proves the same command shapes
complete through the registered WebSocket handler path with only the
allowlisted entity and zero worker dispatches.

The production artifact-serving hardening packet is complete. Config-entry
setup now prepares integration-owned artifact storage and registers the static
artifact path at `/api/isolinear/artifacts`. The first-real-slice
trusted-renderer path validates the render request, render result, PNG payload,
artifact metadata, and final job snapshot around the file write; repeated
snapshot requests reuse the completed PNG and URL; hidden provider entities
still fail before rendering; failed complete-snapshot validation rolls back the
written PNG plus artifact/render/provider bookkeeping; and registered
WebSocket responses expose the served URL without local artifact filesystem
paths. The dashboard-card long-running smoke now expects and renders the served
artifact URL.

The worker-rendered artifact-serving hardening packet is complete. When the
real-slice planner path has a configured worker renderer, the integration sends
the same schema-valid render request through the ADR-0012 worker transport,
requires a successful PNG `RenderResult` with bounded base64 image bytes,
validates the payload, writes it to the existing served artifact store, and
stores rendered artifact metadata plus redacted worker dispatch metadata.
Worker tokens, worker-local paths, local artifact filesystem paths, and base64
image bytes are stripped from registered WebSocket responses. Missing worker
image bytes fail before artifact, render-plan, dispatch, complete-snapshot, or
file storage, oversized image bytes fail the shared schema `maxLength` gate
before decode, and post-write progress rejection removes the just-written PNG
plus artifact-write metadata. The older worker dispatch scaffold still proves
no-file placeholder behavior when the real-slice model-provider plan is absent.

The HACS install-packaging packet is complete. The repository is now shaped as
a HACS custom integration repository with root `hacs.json`, manifest
`issue_tracker` metadata, and exactly one packaged Home Assistant integration
under `custom_components/isolinear`. Runtime JSON Schemas are bundled under
`custom_components/isolinear/schemas`, the dashboard card bundle is bundled
under `custom_components/isolinear/frontend/dist`, local brand icons are
bundled under `custom_components/isolinear/brand`, and runtime validators plus
dashboard resource registration resolve package-local assets so HACS installs
do not require separately copying repo-root `docs/schemas` or `frontend/dist`.
`scripts/frontend.ps1 build` refreshes the packaged card bundle after frontend
builds, and the README now documents the HACS custom-repository install and
redownload update loop.

A live HACS-installed options-flow regression has been closed. When editing
the entity allowlist, plain entity text for
`sensor.family_room_sensor_temperature` could surface a base-level
`must_be_object` if the options flow did not retain the Home Assistant config
entry, while JSON-style pasted list text was validated as a literal malformed
entity ID. The options-flow factory now passes the config entry into
`IsolinearOptionsFlow`, the allowlist normalizer accepts a raw single entity
string and JSON-style pasted list text before the existing schema validation
gate, and the config-flow/options spec, BDD, eval outline, eval, and evidence
capture the regression.

The follow-up live HACS-installed options-flow regression is also closed. A
redownload/restart confirmed the previous commit was installed, but options
editing still returned base-level `must_be_object` when the existing config
entry reached the options flow with missing stored setup data. Options-only
edits now normalize missing config-entry data to the local-first safe defaults
before validation, so `sensor.family_room_sensor_temperature` is accepted from
the same options form while explicitly malformed or secret-bearing config data
continues to fail closed. The visible HACS/Home Assistant package version is
now `0.1.1` in both `manifest.json` and the integration constant, and future
completed implementation packets default to bumping the patch version unless
the human says otherwise.

The live dashboard-card config-entry usability regression is closed in the
repository and is ready for HACS retest. Recreating the card from the picker
previously left `config_entry_id: fake-config-entry`, so clicking **Ask** could
look inert because Home Assistant rejected the command as
`unknown_config_entry` and the card did not surface the rejection. The card now
defaults to `config_entry_id: auto`, the registered WebSocket boundary resolves
`auto` to the only configured Isolinear entry before job state, history,
planner, renderer, or worker code can run, and zero or multiple entries fail
closed with a clear config-entry error. Start-command WebSocket rejections now
render visible failed snapshots instead of leaving the card idle. The visible
package version is now `0.1.2`, the packaged dashboard card bundle has been
rebuilt, bundled schema byte parity is green, and the README documents the
explicit `/config/.storage/core.config_entries` fallback for older builds.

The live `0.1.2` HACS retest showed the repository fix did not yet translate
into a reliable Home Assistant dashboard experience. After redownload/restart
and card recreation, the picker still defaulted to
`config_entry_id: fake-config-entry`; the committed `0.1.2` bundle no longer
contains that string, so the next packet should treat stale dashboard resource
delivery as the primary failure mode. Manually changing the card to
`config_entry_id: auto` also did not produce useful Isolinear WebSocket log
evidence, so the same packet should add lightweight registered-command
observability and make `auto` resolution fall back to Home Assistant's
config-entry registry rather than depending only on `hass.data[DOMAIN]`.

That dashboard resource cache-busting packet is now closed in the repository
and ready for live HACS retest as version `0.1.3`. Lovelace resource metadata
now uses `/api/isolinear/static/isolinear-card.js?v=0.1.3` while the integration
continues to serve the stable static asset path. Existing stale Isolinear
Lovelace resource metadata is updated in place when the base URL matches the
integration card module, avoiding both stale reuse and duplicate resource
records. Registered WebSocket command decisions now write capped runtime-only
observability records and non-secret logs for accepted/rejected command
decisions, and `config_entry_id: auto` can resolve through Home Assistant's
config-entry registry when runtime `hass.data[DOMAIN]` entry data is not
available yet. Zero or multiple candidate entries still fail closed before job
state, history, planning, rendering, worker dispatch, or mutation-capable code
can run.

The live `0.1.3` HACS retest narrowed the dashboard-card issue further:
Home Assistant had the correct single Lovelace resource URL
`/api/isolinear/static/isolinear-card.js?v=0.1.3`, but the card editor still
received the obsolete `config_entry_id: fake-config-entry` value. The
repository is now ready for live HACS retest as version `0.1.4`. The dashboard
card normalizes that legacy placeholder to `auto` before the graphical editor
displays it or any versioned WebSocket command is sent, and mounted-card tests
prove both paths. The package also now includes Home Assistant brand icons at
`custom_components/isolinear/brand/icon.png` and `icon@2x.png`; HACS packaging
tests and eval evidence prove those assets ship with the integration. Lovelace
resource metadata now resolves to
`/api/isolinear/static/isolinear-card.js?v=0.1.4`.

The live `0.1.4` HACS retest then proved the placeholder/cache issue was
closed in a fresh browser: `config_entry_id: auto` reached the dashboard card's
WebSocket request. That exposed the next live boundary bug: Home Assistant's
registered WebSocket routing schema only declared `type`, so Home Assistant
rejected the card's valid `id`/`version`/`config_entry_id`/`prompt` transport
envelope as `extra keys not allowed` before Isolinear could strip transport
metadata and run its deterministic validator. The repository is now ready for
live HACS retest as version `0.1.5`. Registered Isolinear WebSocket handlers
now use a permissive Home Assistant routing schema (`type` plus extra transport
fields) while preserving the strict internal `IntegrationWsCommand` validator:
valid card envelopes route to Isolinear, Home Assistant transport `id` stays
outside the internal command contract, and unexpected card payload keys still
fail closed before orchestration.

The live `0.1.5` HACS retest then proved commands reached Isolinear, but
`job/start` still returned the obsolete job-state scaffold snapshot
(`waiting for a later orchestration packet`, validation `not_run`) instead of
the first-real-slice orchestration path. That happened because registered
WebSocket routing only entered orchestration when the setup-time approved
catalog already had at least one item; an empty or unavailable catalog silently
fell back to the old scaffold. The repository is now ready for live HACS
retest as version `0.1.6`. Once an entry has completed orchestration setup,
registered commands route through orchestration even if the approved catalog is
empty, so the card receives a deterministic approved-entity failure such as
`no_approved_entities_available` rather than `orchestration_not_implemented`.

The live `0.1.6` HACS retest then proved the orchestration gate was fixed, but
exposed an options/catalog refresh bug. Pasting
`["sensor.family_room_sensor_temperature","sensor.bathroom_sensor_temperature"]`
into the allowlist was accepted, but reopening the options form displayed the
stored list as fused text without quotes, brackets, comma, or newline. The
dashboard then still saw an empty approved catalog and failed at
`NO_APPROVED_ENTITIES_AVAILABLE`. The repository is now ready for live HACS
retest as version `0.1.7`. Stored allowlists redisplay as comma-separated text
that round-trips through the existing normalizer, and config-entry setup
registers an options update listener that refreshes the runtime approved
catalog plus allowlist-derived history/orchestration setup metadata before the
next dashboard command.

The live `0.1.7` HACS retest showed the allowlist text no longer fused
separators, but a one-entry allowlist containing
`sensor.bathrrom_sensor_temperature` still produced generic dashboard
`NO_APPROVED_ENTITIES_AVAILABLE`; the Isolinear icon also appeared on the Home
Assistant integrations page but not in HACS. The repository is now ready for
live HACS retest as version `0.1.8`. The options flow uses Home Assistant's
native multi-entity selector for the allowlist while preserving explicit
entity-ID storage and legacy text/list normalization. When catalog setup failed
because the configured allowlist referenced an entity Home Assistant could not
resolve, orchestration now reports `unknown_allowlisted_entity` with the exact
missing ID before any history read rather than flattening the problem into an
empty-catalog dashboard failure; retrying that failed job preserves the same
structured failure. Root `brand/icon.png` and `brand/icon@2x.png` are now
present for HACS and match the package-local Home Assistant brand assets.

The live `0.1.8` HACS retest then proved the Home Assistant multi-entity
picker surface itself worked: a dozen or so temperature sensors could be
selected. The dashboard still failed at `approved_entity_catalog` with generic
`NO_APPROVED_ENTITIES_AVAILABLE`, which showed the saved selector values were
not reaching the runtime catalog. The repository is now ready for live HACS
retest as version `0.1.9`. Catalog setup now treats config-entry `data` and
`options` as mapping-like values rather than requiring plain `dict`, so Home
Assistant read-only mapping options from the selector build the runtime
approved catalog and refresh history/orchestration setup metadata before the
next dashboard command. The attached live logs also showed setup-time schema
`read_text` blocking warnings in worker token lifecycle/readiness/polling;
that remains the existing separate event-loop cleanup item and was not the
catalog-empty failure.

The live `0.1.9` HACS retest then reached the next edge: an ambiguous
temperature prompt correctly produced deterministic clarification options, but
selecting one entity could complete with scaffold placeholder artifact metadata
and a broken served image URL. The repository is now ready for live HACS retest
as version `0.1.10`. Clarification-answer continuation with a configured
planner is covered through the real first-slice path and writes a rendered
served PNG for the selected entity. If the first-real render path has no
configured model-provider planner, snapshot polling now records a card-facing
failed snapshot with `model_provider_planner_not_configured` before artifact
metadata or PNG storage, rather than returning scaffold placeholder success.

The live `0.1.10` HACS retest then proved that clarification no longer returns
placeholder artifact success, but selected-entity continuation still failed at
`model_provider_planner_not_configured`. That exposed the same Home Assistant
read-only mapping shape on config-entry `data` that previously affected
allowlist `options`: model-provider planner setup required a plain `dict` and
therefore disabled the planner even when Ollama settings were present. The
repository is now ready for live HACS retest as version `0.1.11`.
Model-provider planner setup accepts mapping-like config-entry data, and
focused production artifact-serving coverage proves `mappingproxy` config data
configures the planner and completes with a served PNG artifact.

The live `0.1.11` HACS retest then showed the selected clarification entity
reached `job_orchestration_clarification_continuation_ready` and appeared to
start the Ollama planner, but the dashboard card later switched to a local
`SNAPSHOT_POLL_FAILED` state while waiting for `job/snapshot`. The repository
is now ready for live HACS retest as version `0.1.12`. The dashboard card now
retries bounded transient snapshot poll failures such as Home Assistant
frontend timeouts while keeping terminal Isolinear rejections visible, and the
backend snapshot artifact/render path now has per-job single-flight protection:
overlapping snapshot polls during planner/render work return the current active
planning snapshot with `job_orchestration_artifact_snapshot_in_progress`
instead of starting duplicate planner calls. Later snapshot polls reuse the
completed served PNG artifact.

The live `0.1.12` HACS retest still reached `SNAPSHOT_POLL_FAILED`. Edge showed
the prior local snapshot-poll failure text, while the Home Assistant iPhone app
showed `Isolinear WebSocket command rejected.`, proving at least one path was a
registered WebSocket rejection rather than only a frontend timeout wrapper. The
repository is now ready for live HACS retest as version `0.1.13`. The dashboard
card now keeps polling through bounded active-job snapshot failures when Home
Assistant wraps transient timeouts or connection loss as generic `fail`
errors, while terminal Isolinear command errors such as `unknown_job` remain
visible failures. Model-provider output validation failures, including invalid
provider ChartSpecs and hidden-entity provider output, now append sanitized
card-facing failed snapshots with `model_provider_planning` details instead of
surfacing as generic registered WebSocket command rejections; render/artifact
validation failures still fail closed before PNG writes.

The live `0.1.13` HACS retest still showed the card-local
`SNAPSHOT_POLL_FAILED` state, so the repository is now ready for live HACS
retest as version `0.1.14` with stronger backend diagnostic logging rather than
another speculative behavior change. Registered WebSocket command decisions now
log and store sanitized diagnostic fields for Home Assistant message ID,
command type, requested and resolved config-entry IDs, job ID, decision code,
orchestration/result code, snapshot status, progress stage, failure code, and
exception type when present. Unexpected registered Home Assistant WebSocket
handler exceptions are caught at the boundary and returned as structured
`isolinear_websocket_command_exception` errors while logging only sanitized
context. Prompt text, tokens, endpoints, raw history, generated code, generated
images, local filesystem paths, and image bytes remain excluded from the
diagnostic records.

The live `0.1.14` HACS retest then produced useful backend evidence: after the
dashboard reached real recorder history, `job/snapshot` was rejected with
`code=in_process_renderer_failed`, identifying the trusted matplotlib renderer
path rather than a frontend-only polling issue. The repository is now ready for
live HACS retest as version `0.1.15`. The Home Assistant manifest declares the
trusted renderer runtime dependency `matplotlib==3.11.0`, and packaging/scaffold
proof fails if that dependency is omitted. In-process renderer failures now
append sanitized card-facing failed job snapshots with
`failure.stage: chart_rendering` and `failure.code: in_process_renderer_failed`
instead of surfacing as snapshot-poll command rejections; no PNG file, artifact
metadata, render plan, or provider plan is written on that failure path.

The live `0.1.15` HACS redownload then showed commit `18f95bd` installed, but
the dashboard resource metadata still pointed at
`/api/isolinear/static/isolinear-card.js?v=0.1.14` after a full hardware
reboot. Local proof already showed stale query-string Isolinear resources
update in place when Lovelace resource storage is available, so the likely live
gap was cold-boot ordering: Isolinear setup could run before Lovelace resource
storage existed because the manifest declared no Lovelace dependency. The
repository is now ready for live HACS retest as version `0.1.16`. The Home
Assistant manifest declares `dependencies: ["lovelace"]`, HACS packaging proof
fails if that dependency is omitted, and dashboard resource evidence proves the
current package-versioned URL is `?v=0.1.16`.

The live `0.1.16` reinstall then failed before the first setup form rendered:
Home Assistant spent about 30 seconds on
`Please wait, starting configuration wizard for Isolinear` and returned
`Config flow could not be loaded: 500 Internal Server Error`. That points to
pre-flow integration loading rather than config-flow validation. The repository
is now ready for live HACS retest as version `0.1.17`. The renderer-only
`matplotlib==3.11.0` manifest requirement has been removed so Home Assistant
does not try to install a heavy compiled dependency before config-flow loading;
the trusted in-process renderer still imports matplotlib lazily and returns a
sanitized card-facing chart-rendering failure if the module is unavailable.
HACS/scaffold proof now fails if renderer-only config-flow-blocking
requirements are reintroduced, and dashboard resource evidence proves the
current package-versioned URL is `?v=0.1.17`.

Subsequent live tests confirmed `0.1.17`/`0.1.18` loaded but charts failed
closed with `RENDERER_DEPENDENCY_UNAVAILABLE` (matplotlib not present), so
`0.1.19` re-added `matplotlib>=3.7,<4` as a loose-range manifest requirement.
That install also failed: on the live Home Assistant Python 3.14 runtime the
range resolved to `matplotlib==3.11.0`, which has no prebuilt wheel for CPython
3.14, so pip built from source and failed with
`PermissionError: [Errno 13] Permission denied: 'meson'` (the package-install
sandbox cannot run the meson build backend). A failed manifest-requirement
install makes the integration fail to load entirely, which is why `0.1.19`
showed "not loaded" and left the dashboard resource pinned at `?v=0.1.18`
(setup never reached resource registration). matplotlib-via-manifest is a dead
end in this environment.

ADR-0019 resolves this: the trusted in-process renderer now draws with Pillow,
which Home Assistant core already ships, so the manifest declares no renderer
`requirements` (now `[]`). The renderer identifier is `in_process_pillow` (the
`IntegrationArtifactMetadata` schema enum is updated in both synced copies), the
scaffold guard forbids any `matplotlib` requirement regardless of version pin,
and the renderer imports Pillow lazily and still fails closed as
`renderer_dependency_unavailable` if it is somehow absent. The render interface,
supported scope (safe numeric `time_series` line charts), failure codes, and
served-PNG artifact contract are unchanged.

Live `0.1.20` then confirmed the Pillow renderer works end-to-end, but the chart
was illegible on a phone and the window was wrong. `0.1.21` enlarged the
renderer fonts/strokes for the mobile downscale and (temporarily) added a
keyword regex for the window. The window design was then redirected to be
model-driven, landing as `0.1.22` across ADR-0020 and ADR-0021.

ADR-0020 makes the chart time window **model-resolved**: the planner request
carries `now` and the Home Assistant `time_zone`; the planner emits an absolute
`chart_spec.time_range {start, end}`; the integration validates and clamps it
deterministically (tz-normalize to UTC, `start < end`, clamp `end <= now`, span
`<= 366` days, floor `60s`) and falls back to a fixed last-24h window on any
failure (no planner, missing/invalid/unclampable window). The keyword regex is
removed entirely. For the first-real-slice path, history is now fetched **after**
planning using the resolved window, so a window older than recorder retention is
no longer rejected at `job/start`; the legacy scaffold path keeps its start-time
raw fetch (statistics tiering is opt-in through an `allow_statistics` flag).

ADR-0021 adds a **tiered history data source**: raw recorder states for
recent/short windows, hourly long-term statistics up to 60 days, and daily
statistics beyond that, single-source-per-window. Long-term statistics are read
through `statistics_during_period` (read-only, off the event loop via the
existing executor offload). Each `HistorySeries` records its `source`
(`recorder_states` | `long_term_statistics`) and `resolution`
(`raw` | `hourly` | `daily`); statistics buckets carry `value` (mean) plus
`value_min`/`value_max`, and the Pillow renderer shades a min/max band behind the
mean line. An entity without long-term statistics over a beyond-retention window
fails closed with a card-facing `no_long_term_statistics` snapshot. The
HistorySeries schema gains the band point fields and the source/resolution
fields; the planner request gains `now`/`time_zone` (propagated into the
model-provider plan and retry-policy schemas); all synced schema copies are
byte-identical. The repository is ready for live HACS retest as version `0.1.22`;
the next packet is live confirmation of the model-resolved window and the
statistics tier (the only path whose live recorder calls are not unit-tested).

Live `0.1.22` testing then confirmed single-entity long-term-statistics charts
render correctly and surfaced two classes of Home Assistant event-loop/threading
warnings (open-queue item (f)), resolved in `0.1.23` as an event-loop / executor
hygiene packet with no contract changes. First, bundled JSON Schema files were
read and parsed on the event loop on every contract validation. A memoized
`load_schema_document()` plus `preload_schema_documents()` were added in
`_paths.py`; all 24 schema read sites across the integration now use the cached
loader, and `async_setup_entry` warms the cache from an executor before the first
validating setup step, so first reads happen off-loop and later validations are
cache hits. The loader returns a deep copy, preserving the prior per-call
fresh-dict contract. Second, recorder reads (`get_significant_states`,
`statistics_during_period`) ran on Home Assistant's general executor rather than
the recorder's dedicated database executor. A new `_read_via_recorder_executor()`
seam in `history_retrieval.py` bounces the read through the loop onto
`recorder.get_instance(hass).async_add_executor_job(...)` via
`asyncio.run_coroutine_threadsafe(...).result(timeout=60)` — sound because job
orchestration runs synchronously on a general-executor worker thread distinct
from both the loop and the recorder executor — and falls back to an inline read
when no recorder or loop is present (repo tests, non-recorder installs). The
architecture review returned OK (no invariant violation, no new ADR). The
session also created the missing `.claude/agents/code-reviewer.md` subagent
definition, which the architecture-review protocol referenced but which had no
backing agent file (a Codex-port dangling reference). The repository is ready for
live HACS retest as version `0.1.23`; live confirmation that the schema and
recorder blocking-call warnings are gone is folded into the existing live retest
item. The seam's real-HA leg remains `# pragma: no cover` (exercised in tests via
a fake recorder on a real background loop), so the warning removal needs the live
retest to confirm.

A card-facing failure-logging packet then landed as `0.1.24` (open-queue item
(g) part (1)). During `0.1.22` live testing the `binary_sensor.kitchen_door`
"not on the approved list" failure produced no visible Isolinear log line: a
command can be *accepted* at the WebSocket boundary yet return a card-facing
failed `IntegrationJobSnapshot` (`status: failed` with a `failure.code`), and
`_record_websocket_decision` logged those at `INFO` because the decision was
"accepted". `_record_websocket_decision` in `websocket_api.py` now escalates the
visible log to `WARNING` whenever the command is rejected **or** an accepted
command returns a failed snapshot (status `failed` or any captured
`failure_code`), so failure codes such as `entity_not_in_approved_catalog`,
`no_long_term_statistics`, and `in_process_renderer_failed` are diagnosable from
Home Assistant logs instead of buried at `INFO`. The visible log line now also
prints `failure_stage` next to `failure_code` (both were already in the runtime
observability record). No schema or contract changed — log level and format
only — so no ADR was required and the change is below the architecture-review
bar; the WebSocket-command-registration spec's observability requirement now
records the per-outcome log level and the `failure_stage` field. Item (g) part
(2) — whether the all-or-nothing approved-catalog rebuild should fail per-entity
instead of clearing the whole catalog — remains open. The repository is ready
for live HACS retest as version `0.1.24`; the live retest should confirm a
kitchen_door-class failure now emits a visible HA `WARNING` log line.

A categorical timeline render family then landed as `0.1.25` under **ADR-0022**,
resolving the `binary_sensor.kitchen_door` failure for real rather than
dead-ending it. The `0.1.24` WARNING logging surfaced the precise cause: the
door prompt failed with `model_provider_chart_spec_hidden_entity` at the
planning stage, not the intended `no_long_term_statistics`. A binary entity
cannot satisfy the numeric-only planner schema, so the model substituted an
entity and the deterministic entity-validation gate rejected it **before**
history retrieval (the ADR-0020 reorder runs history after planning, so the
planning failure masks the stats gate). The fix makes binary/categorical
entities chart: the integration now **deterministically routes the render family
from each resolved entity's `_series_kind` before planning** (new invariant #9):
all-numeric → `time_series`/`line`; all binary/categorical → a new
`timeline`/`step` family; mixed numeric + binary → fail closed with
`mixed_chart_composition_unsupported` (the overlay composition is the documented
0.1.26 target, ADR-0022 D4/D5). The integration selects the per-family Ollama
structured-output schema (`load_planner_result_schema(family)`), so the model
never picks `chart_type`. The live Pillow renderer gained `_render_timeline_png`
(one lane per series, binary on/off fills + categorical bands, phone-legible)
built on a shared `_binary_on_regions` primitive that the 0.1.26 overlay reuses
without a rewrite. The misleading hidden-entity code was split into honest
`model_provider_referenced_unapproved_entity` (absent from the approved catalog)
vs `model_provider_substituted_entity` (approved but not disclosed for this job);
the legacy code is retained as a classification alias. No **core** schema change
was needed — `chart-spec.schema.json` already allows `timeline`/`step` and a
first-class `overlays[]` array. The `no_long_term_statistics` gate stays after
planning for its intended numeric class (not regressed); a beyond-retention
binary timeline fails closed through that same gate. Verification: full suite
`388 passed`, new `timeline_render_family_routing` eval + 51 prior evals `PASS`,
the two-lane timeline anchor PNG eyes-on verified legible at a 380px phone
downscale, architecture review `OK` (no invariant violations), BDD-evidence
review `OK`, `git diff --check` clean, bump to `0.1.25`. **Caveat:** unit- and
artifact-verified; the live HACS `0.1.25` retest should confirm a real
`binary_sensor` prompt renders an on/off timeline instead of the old
hidden-entity failure. The numeric + binary overlay ("temperature and when the
AC was running") is open-queue item (i) for `0.1.26`.

The numeric + binary overlay composition then landed as `0.1.26`, completing
ADR-0022's target architecture (D4/D5). "Show me the temperature and when the AC
was running" now renders a numeric `time_series` line with the binary entity
shaded as `shaded_intervals` overlay bands behind it. `_resolve_render_family`
gained a `time_series_overlay` family for **exactly one numeric primary + one or
more binary** entities; for that family the planner is disclosed **only** the
numeric primary as a chartable series (new `entity_ids` argument on
`_model_provider_planner_request`), and the integration injects the binary
overlays deterministically **after** planning via `_compose_binary_overlays`
(the model never composes overlays — invariant #9 / D5). The live Pillow numeric
renderer gained an overlay pass: vertical "on"-region bands across the full plot
height drawn behind the primary line, reusing the `_binary_on_regions` primitive
from 0.1.25; the numeric unsupported-gate now accepts `shaded_intervals` overlays
with an entity source and rejects any other overlay shape with
`unsupported_chart_spec`. `select_prompt_entity_ids` auto-resolves a fuzzy prompt
matching one numeric + one-or-more binary entities to the composition
(`source: numeric_with_overlay`) instead of single-entity clarification. The
composition is **binary-only** by design (architecture-review scope tightening):
a non-binary categorical mixed with numeric has no "on" region to shade, so it
stays `mixed` (fail closed) rather than shading nothing, and two or more numeric
series mixed with a binary also stay `mixed` (no deterministic primary). No core
schema change was needed (`overlays[]` is already first-class). The entity
allowlist invariant holds: restricting the planner disclosure only narrows what
the model may chart, while the injected overlay entity is still validated against
the full disclosed `source_snapshot`. Verification: full suite `393 passed`,
`timeline_render_family_routing` eval extended with the overlay routing + render
cases + 51 prior evals `PASS`, the temperature+AC overlay anchor PNG eyes-on
verified legible at a 380px phone downscale, architecture review `OK` (no
invariant violations; its one note — categorical-as-overlay — was addressed by
the binary-only tightening), BDD-evidence review `OK`, `git diff --check` clean,
bump to `0.1.26`. **Caveat:** unit- and artifact-verified; the live HACS `0.1.26`
retest should confirm a real mixed prompt renders the overlay.

The categorical (climate) overlay path then landed across several `0.1.45`-era
fixes: state-based overlays now shade by the `hvac_action` attribute (climate
entity *state* is a constant HVAC mode, so band detection reads the cycling
attribute, captured as `attrs` on categorical history points), and history points
are timestamped by `last_updated` rather than `last_changed` — the latter is
frozen for an entity whose state never changes, which had collapsed every cooling
snapshot onto one stale block.

ADR-0027 (`0.1.47`) then moved the chart **legend out of the PNG and into the
card**. The renderer emits a `render_metadata.legend` color manifest
(`{label, entity_id, color, kind, states?}`, overlays carrying per-state child
colors) as the single source of truth for colors; the in-PNG legend is removed for
`time_series` / `time_series_overlay` (the other three families keep theirs,
deferred). The model now authors `chart_spec.summary` (the card caption, replacing
the prompt echo) and `planner_result.overlay_labels` (`{entity_id: label}`, applied
to the integration-composed overlay with a deterministic fallback) — extending the
ADR-0023 capability/intent split to presentation while overlay composition, colors,
and routing stay deterministic (invariants #1/#9 intact; the model gains only a
string and a label map). The card renders an interactive **Legend**: swatch +
descriptive label per row, a flip-down exposing the entity_id and any matched
alias, and a split swatch + per-state children for multi-state overlays. Six
schemas extended (all optional/back-compat). Verified by 565 Python + 21 frontend
tests and an anchor PNG (clean chart; manifest carries the series + cooling/heating
colors); BDD-evidence and architecture reviews `OK`. **Caveat:** unit- and
artifact-verified; the live HACS `0.1.47` retest should confirm the summary
caption, the AC split-swatch children, and the descriptive legend labels.

The `0.1.47` live HACS retest (2026-06-27) then **passed** for every shipped
feature — card legend, model summary caption, AC split swatch, histogram,
aggregate_bar, fuzzy/90-day window resolution, the `no_long_term_statistics`
gate, and reasoning streaming. Two prompts failed at
`model_provider_planner_not_chart_spec_ready`: "when was the kitchen door open
today" and "show kitchen temp and when the AC was running". Diagnosis from the
live debug log (plus reproduction against the live `gemma4:e4b`) showed this was
**not** a planner bug but an entity-selection **over-composition** bug:
`select_prompt_entity_ids` composes any numeric + state match sharing a prompt
token, and the location word "kitchen" noise-matched
`sensor.kitchen_ecobee_temperature`. For the door prompt the temperature sensor
became the chart *primary* and the door was demoted to an overlay (the planner
clarified, "which entity tracks the door?"); for the temp+AC prompt
`binary_sensor.kitchen_door` entered as a *spurious second overlay* that tipped
the planner into clarification. The overlay path short-circuited in
`select_prompt_entity_ids` before the ADR-0024 D2 validation pass could run.

ADR-0028 (`0.1.48`) fixes this by **routing the multi-match overlay composition
through the existing D2 `select_entity` selector to prune noise matches** before
render-family routing. A new `_prune_composition_with_model`, gated on
`_composition_has_shared_token` (only fires when ≥2 candidates share a prompt
token), hands the composed candidate set to the model and keeps the subset the
prompt is actually about; the pruned set re-routes through the deterministic
`_resolve_render_family` by entity kind (invariant #9 unchanged) and is
re-validated against the allowlist (invariant #1 unchanged). It fails soft to the
deterministic composition on model abstention, provider failure, no configured
planner, or an empty/unchanged result, so the path is never worse than before and
needs no model in test/scaffold environments. The model prunes both failing cases
correctly from the entity friendly names alone, so the existing D2 request shape
is reused unchanged — no schema or `model_provider.py` change. This is the
composition-path counterpart of ADR-0024 D2 (which already validated/narrowed the
single-entity path) and keeps render family and overlay pairing deterministic, in
line with the lean-on-model-where-it's-safe analysis recorded in the ADR's
rejected alternatives. **Caveat:** unit-, eval-, and live-selector-verified; the
live HACS `0.1.48` retest should confirm the two prompts complete (door timeline;
temp + AC overlay) with no spurious clarification.

Night mode (dark theme) is now a recorded open-queue item ((h) in `STATUS.md`)
with the design decisions captured: scope is **chart PNG + card UI**, theme
source is **auto-follow the Home Assistant theme** (no user toggle), and it
needs a spec plus likely an ADR before implementation because the resolved theme
must be plumbed card -> `job/start` -> render request (schema-touching) and the
Pillow renderer needs a second dark palette baked at render time. It is intended
to be picked up in a fresh session.

## Product summary

Isolinear lets a user ask natural-language questions about approved Home Assistant entities and receive generated data visualizations based on entity history.

## Current architecture direction

- Home Assistant custom integration.
- Install/update path is HACS custom repository of type `integration`.
- TypeScript Lit custom dashboard card as the first UI (`custom:isolinear-card`).
- Optional Home Assistant add-on worker for rendering and sandbox execution.
- Standalone worker mode should remain possible for Home Assistant installs that cannot use add-ons.
- Model provider should be Ollama-compatible, with local-first defaults and optional stronger providers later.
- Trusted chart-spec renderer is the default path.
- The first real prompt-to-chart route renders trusted ChartSpecs either in-process or through the configured worker renderer and returns a same-origin served PNG artifact URL.
- Sandboxed matplotlib codegen is an advanced path.

## Open implementation status

Fake-provider vertical slice implemented as a local Python module with schema-backed contract validation, a pre-render plan validation gate, deterministic render metadata validation, trusted safe-mode rendering for shaded interval overlays, state interval timelines, and aggregate bar charts, fake binary-state interval extraction, confirmed threshold-derived interval extraction, deterministic threshold clarification for continuous power sensors, use-once threshold confirmation handling, deterministic threshold semantic alias creation, reuse of saved threshold aliases, deterministic invalidation of saved threshold aliases that reference unavailable or non-allowlisted entities, and a versioned semantic-memory store envelope anchor that computes invalidity at use time while failing closed for unsupported versions or duplicate alias IDs. Eval scripts now emit structured `CASE` evidence payloads, and implemented eval-backed scenario groups have paired markdown BDD/evidence files under `bdd/<feature>/`.

First real vertical slice pivot implementation is complete and manually
verified against live services through real Home Assistant core and the
registered WebSocket handler path. `custom_components/isolinear` now has a
trusted in-process matplotlib renderer for safe numeric `time_series`
ChartSpecs, best-effort real Home Assistant registry/state metadata enrichment,
best-effort recorder-history retrieval, an async-safe registered WebSocket
bridge, an Ollama structured-output schema narrowed to the first-slice
ChartSpec shape, and a first-real-slice route in the existing
`isolinear/v1/job/start` -> `job/snapshot` flow. The route now writes real PNG
bytes to integration-owned artifact storage and returns
`/api/isolinear/artifacts/<artifact_id>.png` through the card-facing snapshot.
The focused pytest proves the served PNG URL and on-disk PNG signature,
card-facing model-provider failure snapshots for hidden-entity and invalid
provider chart output before rendering/artifact storage, rollback on failed
complete-snapshot validation, idempotent completed-snapshot reuse, no local
filesystem paths in registered WebSocket render details, and no worker
dispatch for the in-process route. A follow-up worker-rendered artifact pytest
now proves the same served URL contract when a configured worker returns
validated PNG bytes, including idempotence, missing-byte failure before storage,
oversized-byte schema rejection, progress-failure rollback, worker render
failure handling, bearer redaction, and path-safe registered WebSocket
responses. The manual
evidence proves real recorder history plus `gemma4:e4b` can complete the same
route with only the allowlisted entity; the production hardening packet replaces
that temporary data URL output with the served artifact URL contract.

Dashboard card implementation technology is decided in ADR-0011: the MVP card is a TypeScript Lit custom element loaded as `custom:isolinear-card`, bundled as an ES module, and kept as a thin client over integration-owned Home Assistant WebSocket commands. The card must not directly call the worker, model provider, Home Assistant history APIs, semantic-memory storage, mutation services, or browser local storage for Isolinear state.

Dashboard card anchor implementation is complete. The repo now has a
Node-backed frontend anchor under `frontend/` with TypeScript Lit source, a
checked-in Vite ES module bundle, fake Home Assistant harness, fixture job
snapshots, Vitest adapter coverage, Python verifier/eval coverage, and raw
BDD evidence proving idle, planning, clarification, complete, failed, and
integration-boundary scenarios. Repo-local setup scripts create `.venv`, run
pytest, resolve the Windows Node.js install, and run frontend install/build/test
commands without depending on ambient PATH. A long-running mounted-card smoke
now covers the active prompt workflow beyond static fixture rendering: delayed
prompt submission, automatic snapshot polling, duplicate-submit suppression,
and chart-first PNG completion.

Worker API transport and authentication is designed and anchored in ADR-0012.
The card-facing API is a versioned Home Assistant WebSocket command set under
`isolinear/v1/` for job start, clarification answer, retry, snapshot retrieval,
and subscription. The worker-facing render API is a versioned HTTP JSON
envelope for `POST /v1/render` authenticated with an integration-owned bearer
token that is never sent to the dashboard card or model provider. The repo has
schemas, a Python verifier, tests, eval evidence, and frontend adapter coverage
for the command/envelope contract, bad-auth and bad-version rejection, and token
redaction.

Sandbox implementation for Raspberry Pi compatibility is anchored. The worker
sandbox spec now defines the concrete codegen strategy: schema validation before
execution, static AST safety checks, isolated Python subprocess execution with
`-I`, stripped environment, fixed `render_chart(data, output_path)` entry point,
runtime audit hook, fixed output-path writes, subprocess timeout, Linux
`resource` CPU/address-space requests where available, and max output image
size enforcement. The repo has a `CodegenSandboxPolicy` schema, Python anchor,
focused tests, executable eval, and paired BDD/evidence proving safe fixed-entry
execution, exact generated-code import allowlisting, allowlisted matplotlib
`Agg` rendering, forbidden import/file/environment/network rejection before
execution, runtime audit denial for arbitrary reads routed through
`pyplot.imread`, oversized output failure, and capped repair-loop behavior with
static checks rerun on every attempt. The dev environment now installs
matplotlib through `requirements-dev.txt`; production worker packaging remains
responsible for providing matplotlib in the isolated worker image.

First trusted renderer release scope is anchored. The chart-spec rendering spec
now defines the safe-mode trusted scope as `time_series` charts with numeric
`line` series, entity-backed sources, no transform except `none`, optional
`shaded_intervals` overlays from supplied `DerivedInterval` records, PNG output,
and no fallback into codegen. The Python trusted-renderer anchor validates
render contracts, fails unsupported schema-valid primitives with structured
`unsupported_chart_spec` details before writing output artifacts, and reports
zero codegen attempts. The renderer BDD/evidence and
`evals/trusted_renderer_primitives.py` prove supported line/overlay rendering
and unsupported primitive rejection. The spec records six follow-up trusted
renderer families: state interval timeline, aggregate bar, calendar/hour
heatmap, event markers, distribution/histogram, and scatter/correlation.
Floorplan heatmaps are deferred until post-MVP because Home Assistant floors
and areas do not provide room geometry; they will require explicit
user-provided geometry and area/entity mappings.

Trusted renderer state interval timeline follow-up is anchored. The chart-spec
rendering spec now selects `state_interval_timeline` as the first follow-up
family and defines safe-mode `timeline` charts with binary/categorical `step`
tracks, entity-backed sources, no transform except `none`, one matching
`DerivedInterval` per track, absolute time-range metadata, PNG output, and no
codegen fallback. The Python anchor uses chart-family-specific unsupported
checks so `time_series` remains limited to numeric `line` series while
`timeline` requires state-like history and matching derived intervals. Timeline
rendering fails closed before artifact creation if the derived interval source
entity does not match the chart series source. The BDD/evidence and
`evals/state_interval_timeline.py` prove timeline rendering, deterministic
metadata, validation, and zero codegen attempts.

Trusted renderer aggregate bar chart follow-up is anchored. The chart-spec
rendering spec now defines the `aggregate_bar_chart` family as safe-mode
`bar` charts with aggregate numeric series, `source.type: aggregate`, one bar
per source entity, `mean`/`min`/`max`/`sum`/`count` operations, no transform
except `none`, no overlays, PNG output, and no codegen fallback. The Python
anchor adds bar-family primitive checks so time-series and timelines remain
entity-backed while bars require aggregate sources. Aggregate rendering
computes values from matching numeric `HistorySeries` records over the chart
time range, emits deterministic x-range metadata, and fails closed before
artifact creation if any aggregate source history is missing or has no numeric
points. The BDD/evidence and `evals/aggregate_bar_chart.py` prove rendering,
metadata, validation, and zero codegen attempts.

Trusted renderer calendar/hour heatmap follow-up is anchored. The chart-spec
rendering spec now defines the `calendar_hour_heatmap` family as safe-mode
`heatmap` charts with one numeric entity-backed series rendered as weekday-by-hour
mean cells from `x_axis.group_by: hour` and `y_axis.group_by: weekday`, no
transform except `none`, no overlays, PNG output, and no codegen fallback. The
Python anchor adds heatmap-family primitive checks for source type, render
primitive, series count, and supported grouping while preserving the existing
time-series, timeline, and bar constraints. Heatmap rendering fails closed
before artifact creation if source history is missing or has no numeric points
in range. The BDD/evidence and `evals/calendar_hour_heatmap.py` prove rendering,
metadata, validation, and zero codegen attempts.

Trusted renderer event markers and distribution/histogram follow-up is anchored.
The chart-spec rendering spec now defines safe-mode `markers` overlays on
numeric `time_series` charts and safe-mode `histogram` charts with one numeric
entity-backed series. Marker overlays are derived from matching validated
`HistorySeries` records using state `active_values`, numeric threshold
crossings, or event-kind points; histogram rendering computes deterministic
fixed-count value bins from `x_axis.bin_count` with a default of 8 bins. The
Python anchor adds marker and histogram primitive checks while preserving the
existing time-series, timeline, bar, and heatmap constraints. Marker rendering
fails closed before artifact creation if source history is missing or no marker
events match; histogram rendering fails closed before artifact creation if
source history is missing or no numeric points exist in range. The BDD/evidence
and `evals/event_markers.py` plus `evals/distribution_histogram.py` prove
rendering, metadata, validation, and zero codegen attempts.

Trusted renderer scatter/correlation follow-up is anchored. The chart-spec
rendering spec now defines safe-mode `scatter` charts with exactly two numeric
entity-backed series rendered as paired values. Scatter specs must provide
`x_axis.source_series_id` matching the first series and
`y_axis.source_series_id` matching the second series. The Python anchor pairs
numeric points only by exact matching timestamps inside the chart time range,
emits deterministic absolute time-range metadata, writes PNG output, and never
falls back into codegen. Scatter rendering fails closed before artifact creation
for unsupported series counts, mismatched axis source IDs, unsupported sources
or history kinds, missing source history, and histories with no paired numeric
points. The BDD/evidence and `evals/scatter_correlation.py` prove rendering,
metadata, validation, and zero codegen attempts.

MVP design readiness review is complete. The review artifact at
`docs/mvp-design-readiness-review.md` records a READY verdict for the first
Home Assistant custom integration scaffold. ADR-0012, the integration API
transport/authentication spec, and the paired BDD are now accepted because the
schema/test/eval/evidence anchor has landed. Eval-outline entries now exist for
the already-executable codegen sandbox, dashboard card, and integration
transport/authentication anchors.

Home Assistant integration scaffold anchor is complete. The repo now has a
minimal `custom_components/isolinear` package with a Home Assistant
`manifest.json`, domain constants, local-first config/options validation for
model endpoint, worker endpoint, render mode, repair attempts, and entity
allowlist, plus fail-closed `isolinear/v1/` WebSocket command-boundary stubs.
The scaffold accepts schema-valid command shapes and returns schema-valid
`IntegrationJobSnapshot` scaffold snapshots while rejecting unknown,
wrong-version, leaky, mutating, credential-bearing endpoint, and secret-like
configuration payloads before orchestration. It does not call the worker, model
provider, Home Assistant history APIs, semantic-memory storage helpers, or Home
Assistant mutation services. The paired spec/BDD/eval/evidence and
`evals/home_assistant_integration_scaffold.py` prove the anchor. Standalone
architecture reviews should use the updated 10 minute timeout guidance in
`codex/review-architecture.md`.

Home Assistant config flow/options anchor is complete. The manifest now enables
`config_flow`, and `custom_components/isolinear/config_flow.py` provides a
minimal Home Assistant user config step plus options init step. The flow reuses
the existing pure config/options validation helpers, normalizes blank optional
model fields to `null`, normalizes user-facing allowlist text into a
deterministic entity list, and rejects credential-bearing endpoints,
secret-like values, unsupported render modes, duplicate allowlists, malformed
entity IDs, and forbidden secret material before config-entry or options
persistence. The packet remains non-orchestrating: it does not call the worker,
model provider, Home Assistant history APIs, semantic-memory storage helpers,
Home Assistant services, token generation, or dashboard resource registration.
The paired spec/BDD/eval/evidence and
`evals/home_assistant_config_flow_options.py` prove the anchor.

Home Assistant dashboard resource registration anchor is complete. ADR-0013
now records that the integration auto-registers the dashboard card resource.
`custom_components/isolinear/dashboard_resource.py` serves the checked-in
`frontend/dist/isolinear-card.js` bundle from `/api/isolinear/static` and
creates or reuses one Lovelace `module` resource at
`/api/isolinear/static/isolinear-card.js` during `async_setup_entry`. The
registration result is stored under the config-entry ID, repeated setup is
idempotent, pre-existing matching metadata is reused, missing bundles and
unavailable resource collections fail closed before metadata creation, and the
packet explicitly reports dashboard resource metadata creation/reuse as the
only allowed Home Assistant write. It does not call the worker, model provider,
Home Assistant history APIs, semantic-memory storage helpers, Home Assistant
service/state mutation APIs, token generation, job orchestration, or extra
WebSocket command registration. The paired spec/BDD/eval/evidence and
`evals/home_assistant_dashboard_resource_registration.py` prove the anchor.

Home Assistant WebSocket command registration anchor is complete. The
integration now registers the five accepted `isolinear/v1/` card-facing command
names through Home Assistant's `websocket_api.async_register_command` boundary
during `async_setup_entry`. The registration result is stored under the
config-entry ID, repeated setup is idempotent, Home Assistant transport `id`
metadata is stripped before internal command validation, and config-entry scope
is checked before any scaffold snapshot is returned. Home Assistant's decorator
schema owns only command routing; Isolinear's deterministic validator owns
version, payload-shape, forbidden-material, and config-entry-scope rejection so
wrong-version, leaky, mutating, malformed, unknown, and missing-config-entry
commands fail closed with structured errors before orchestration. Registered
callbacks still return schema-valid scaffold `IntegrationJobSnapshot` payloads
until a later packet replaces the scaffold behavior. The boundary does not call
the worker, model provider, Home Assistant history APIs, semantic-memory
storage helpers, Home Assistant service/state mutation APIs, token generation,
job orchestration, or dashboard-resource metadata writes. The paired
spec/BDD/eval/evidence and
`evals/home_assistant_websocket_command_registration.py` prove the anchor.

Home Assistant job state scaffold anchor is complete.
`custom_components/isolinear/job_state.py` now owns the smallest production
in-memory job state surface behind the registered WebSocket commands.
`async_setup_entry` initializes one config-entry-scoped job store, registered
callbacks use it after deterministic command validation and config-entry scope
validation, and `async_unload_entry` removes entry job state by removing the
entry data. The store creates deterministic job IDs and snapshot IDs for a
fresh runtime, validates every scaffold `IntegrationJobSnapshot` against JSON
Schema before storage, returns latest snapshots, records retry and
clarification-answer scaffold snapshots, records a subscription callback/event
shape, rejects unknown and cross-config-entry job IDs with structured
`unknown_job` errors, and keeps all state scoped to the command's
`config_entry_id`. This packet remains non-orchestrating: it does not call the
worker, model provider, Home Assistant history APIs, semantic-memory storage
helpers, Home Assistant service/state mutation APIs, token generation, chart
artifact writes, durable storage, or real job orchestration. The paired
spec/BDD/eval/evidence and `evals/home_assistant_job_state_scaffold.py` prove
the anchor.

Home Assistant approved entity catalog scaffold anchor is complete.
`custom_components/isolinear/entity_catalog.py` now owns the smallest
production config-entry-scoped approved entity catalog surface.
`async_setup_entry` builds and stores one in-memory catalog from the configured
`entity_allowlist` plus fake Home Assistant entity/state metadata, producing
only schema-valid `EntityCatalogItem` records with `visible_to_agent: true`.
Catalog construction validates every item before storage/return, stores
atomically, keeps catalogs isolated per config entry, rejects unknown
allowlisted entities, clears any previous catalog on rejected rebuilds so stale
metadata cannot remain visible, and rejects malformed allowlists and malformed
normalized items with structured errors before storage. This packet remains
non-orchestrating: it does not call the worker, model provider, Home Assistant
history APIs, semantic-memory storage helpers, Home Assistant service/state
mutation APIs, token generation, chart artifact writes, WebSocket command
registration, dashboard-resource metadata writes, durable storage, or real job
orchestration. The paired spec/BDD/eval/evidence and
`evals/home_assistant_approved_entity_catalog_scaffold.py` prove the anchor.

Home Assistant approved history retrieval scaffold anchor is complete.
`custom_components/isolinear/history_retrieval.py` now owns the smallest
production config-entry-scoped approved history retrieval surface.
`async_setup_entry` initializes one in-memory history retrieval store after the
approved entity catalog setup. Retrieval gates requested entity IDs against
visible approved catalog items before reading fake Home Assistant history,
normalizes approved raw state records into schema-valid `HistorySeries`
records, validates every series before storage/return, stores atomically, keeps
stores isolated per config entry, rejects non-catalog entities before history
read, clears stale history on rejected retrievals, and rejects malformed raw
history and malformed normalized series with structured errors before storage.
This packet remains non-orchestrating: it does not call the worker, model
provider, semantic-memory storage helpers, Home Assistant service/state
mutation APIs, token generation, chart artifact writes, chart rendering,
WebSocket command registration, dashboard-resource metadata writes, durable
storage, or real job orchestration. The paired spec/BDD/eval/evidence and
`evals/home_assistant_approved_history_retrieval_scaffold.py` prove the anchor.

Home Assistant job orchestration scaffold anchor is complete.
`custom_components/isolinear/job_orchestration.py` now owns the smallest
production config-entry-scoped `job/start` orchestration scaffold.
`async_setup_entry` initializes one in-memory orchestration store after job
state, approved entity catalog, and approved history retrieval setup. Enabled
`isolinear/v1/job/start` callbacks now create deterministic job state, select
approved entities only through deterministic explicit-ID or single-label-match
resolution, compose approved fake history through the existing retrieval
boundary, append schema-valid planning/fetching-history/scaffold-ready or
failed snapshots, and store per-entry run summaries. Explicit non-catalog
entity IDs fail before history read, missing approved history returns a
structured failed snapshot, and ambiguous prompts including multiple label
matches return a schema-valid `clarification_needed` snapshot without reading
history. This packet remains non-rendering and non-mutating: it does not call
the worker, model provider, semantic-memory storage helpers, Home Assistant
service/state mutation APIs, token generation, chart artifact writes, chart
rendering, durable storage, subscription progress streaming, or production
orchestration beyond scaffold bookkeeping. The paired spec/BDD/eval/evidence
and `evals/home_assistant_job_orchestration_scaffold.py` prove the anchor.
This packet was larger than ideal; follow-on orchestration work should be split
into smaller bounded packets.

Home Assistant job orchestration clarification continuation scaffold anchor is
complete. Enabled `isolinear/v1/clarification/answer` callbacks now resume the
same config-entry-scoped job when its latest snapshot is
`clarification_needed`, require a matching question ID, accept only returned
approved option IDs that resolve to exactly one current approved catalog
entity, retrieve approved fake history through the existing history boundary,
append schema-valid clarification-accepted/fetching-history/scaffold-ready
snapshots, and store per-entry continuation run summaries. Unknown options,
wrong question IDs, colliding option IDs, unknown jobs, non-clarification jobs,
and cross-config-entry jobs fail closed before history read and without
continuation snapshots. The packet remains non-rendering and non-mutating: it
does not call the worker, model provider, semantic-memory storage helpers,
Home Assistant service/state mutation APIs, token generation, chart artifact
writes, chart rendering, durable storage, retry behavior, subscription
progress streaming, or production orchestration beyond scaffold bookkeeping.
The paired spec/BDD/eval/evidence and
`evals/home_assistant_job_orchestration_clarification_continuation_scaffold.py`
prove the anchor.

Home Assistant job orchestration retry continuation scaffold anchor is
complete. Enabled `isolinear/v1/job/retry` callbacks now resume the same
config-entry-scoped job only when its latest snapshot is a failed retryable
scaffold snapshot, reuse the original job prompt through the current approved
catalog and approved fake history retrieval boundary, append schema-valid
retry-accepted/fetching-history/scaffold-ready snapshots, and store per-entry
retry continuation run summaries. Unknown jobs, cross-config-entry jobs, and
non-retryable jobs fail closed before history read and without retry
continuation snapshots. The packet remains non-rendering and non-mutating: it
does not call the worker, model provider, semantic-memory storage helpers,
Home Assistant service/state mutation APIs, token generation, chart artifact
writes, chart rendering, durable storage, subscription progress streaming,
automatic retry loops, worker retry behavior, or production orchestration
beyond scaffold bookkeeping. The paired spec/BDD/eval/evidence and
`evals/home_assistant_job_orchestration_retry_continuation_scaffold.py` prove
the anchor.

Home Assistant job orchestration subscription/progress streaming scaffold
anchor is complete. Enabled `isolinear/v1/job/subscribe` callbacks now validate
the targeted config-entry job's latest `IntegrationJobSnapshot`, record a
deterministic job-state subscription, store one deterministic
config-entry-scoped orchestration progress event envelope containing the latest
schema-valid snapshot, and return that latest snapshot immediately. Unknown jobs and
cross-config-entry jobs fail closed before subscription or progress-event
storage. The packet remains non-rendering and non-mutating: it does not call
the worker, model provider, approved Home Assistant history during subscribe,
semantic-memory storage helpers, Home Assistant service/state mutation APIs,
token generation, chart artifact writes, chart rendering, durable storage,
retry behavior, automatic progress tasks, worker streaming, or production
orchestration beyond scaffold bookkeeping. The paired spec/BDD/eval/evidence
and `evals/home_assistant_job_orchestration_subscription_progress_scaffold.py`
prove the anchor.

Home Assistant job orchestration artifact storage scaffold anchor is complete.
Enabled `isolinear/v1/job/snapshot` callbacks now validate the targeted
config-entry job's latest `IntegrationJobSnapshot`, record one deterministic
config-entry-scoped placeholder artifact metadata envelope for scaffold-ready
jobs, validate it against the `IntegrationArtifactMetadata` schema, append and
return a schema-valid complete snapshot with placeholder chart metadata, and
idempotently reuse existing artifact-backed complete snapshots. Unknown jobs
and cross-config-entry jobs fail closed before artifact metadata or complete
snapshot storage. The packet remains non-rendering and non-mutating: it does
not call the worker, model provider, approved Home Assistant history during
artifact storage, semantic-memory storage helpers, Home Assistant service/state
mutation APIs, token generation, real artifact file writes, chart rendering,
durable storage, retry behavior, automatic progress tasks, worker streaming,
or production orchestration beyond scaffold bookkeeping. The paired
spec/BDD/eval/evidence and
`evals/home_assistant_job_orchestration_artifact_storage_scaffold.py` prove the
anchor.

Home Assistant job orchestration render planning scaffold anchor is complete.
Enabled `isolinear/v1/job/snapshot` callbacks now validate the targeted
config-entry job's latest `IntegrationJobSnapshot`, record one deterministic
config-entry-scoped placeholder render-plan envelope for scaffold-ready jobs,
validate the render plan against `IntegrationRenderPlan`, validate the nested
placeholder `ChartSpec` before storage, reference the same placeholder artifact
metadata, append and return the existing schema-valid artifact-backed complete
snapshot, and idempotently reuse existing render plans and artifacts. Unknown
jobs and cross-config-entry jobs fail closed before render-plan metadata,
artifact metadata, or complete snapshot storage. The packet remains
non-rendering and non-mutating: it does not call Ollama or any model provider,
does not call the worker, does not read approved Home Assistant history during
render planning, does not persist semantic memory, does not mutate Home
Assistant state, does not generate tokens, does not write real artifact files,
does not render charts, and does not add durable storage, retry/backoff,
automatic progress tasks, worker streaming, or production orchestration beyond
scaffold bookkeeping. The paired spec/BDD/eval/evidence and
`evals/home_assistant_job_orchestration_render_planning_scaffold.py` prove the
anchor.

Home Assistant job orchestration model-provider planning scaffold anchor is
complete. Enabled `isolinear/v1/job/snapshot` callbacks now use a
config-entry-scoped Ollama-compatible planner client when provider config is
present, validate the targeted scaffold-ready source snapshot, build
deterministic planner requests from the prompt, approved entity disclosure, and
staged history entity IDs, validate `PlannerResult` and provider-produced
`ChartSpec` before storage, recursively reject hidden entity IDs anywhere in
provider output, record a deterministic `IntegrationModelProviderPlan`
envelope, and store the existing render-plan envelope using the provider
`ChartSpec`. The no-provider placeholder render-plan path remains intact.
Unknown jobs and cross-config-entry jobs fail closed before provider calls,
model-provider plan metadata, render-plan metadata, artifact metadata, or
complete snapshot storage. The packet remains non-rendering and non-mutating:
it does not call the worker, does not read approved Home Assistant history
during model-provider planning, does not persist semantic memory, does not
mutate Home Assistant state, does not generate tokens, does not write real
artifact files, does not render charts, and does not add durable storage,
retry/backoff, automatic progress tasks, worker streaming, or production
orchestration beyond bounded provider/render/artifact bookkeeping. The paired
spec/BDD/eval/evidence and
`evals/home_assistant_job_orchestration_model_provider_planning_scaffold.py`
prove the anchor.

Home Assistant model-provider retry/backoff policy scaffold anchor is
complete. Enabled `isolinear/v1/job/snapshot` callbacks now record one
deterministic config-entry-scoped `IntegrationModelProviderRetryPolicy`
envelope when a configured planner returns a retry-safe provider failure. The
policy stores provider metadata, deterministic planner request metadata,
sanitized failure code/message text, manual-retry/backoff decision metadata,
and `automatic_retry_scheduled: false`, validates against JSON Schema before
storage, and returns only a schema-valid failed `IntegrationJobSnapshot` to the
dashboard card. Malformed retry metadata, secret-like provider failure text,
unknown jobs, and cross-config-entry jobs fail before provider retry-policy
storage. The packet remains read-only and bounded: it does not add provider
health polling, automatic retry, durable retry queues, worker behavior, chart
rendering, token persistence, dashboard UI, or Home Assistant mutation. The
paired spec/BDD/evidence and
`evals/home_assistant_model_provider_retry_backoff_policy_scaffold.py` prove
the anchor.

Home Assistant model-provider health diagnostics scaffold anchor is complete.
Config-entry setup now records explicit provider-health probe availability
without calling the provider. The provider health boundary validates a
schema-valid Ollama-compatible `ModelProviderHealthRequest` for `GET /api/tags`,
calls only the same-entry configured planner client, stores one
schema-valid `IntegrationModelProviderHealth` envelope for `ready`,
`not_ready`, and `unavailable` results, and rejects malformed or
secret-bearing accepted health responses before storage. Unknown entries and
unconfigured entries fail before provider calls or health metadata storage.
Dashboard-card payloads remain unchanged and do not expose provider endpoint,
request details, provider response internals, or internal health metadata. The
paired spec/BDD/evidence and
`evals/home_assistant_model_provider_health_diagnostics_scaffold.py` prove the
anchor.

Home Assistant job orchestration worker dispatch/rendering scaffold anchor is
complete. Enabled `isolinear/v1/job/snapshot` callbacks now use a
config-entry-scoped ADR-0012 worker renderer client when an integration-owned
worker token is already present, validate the targeted artifact-ready render
plan and staged approved history, build schema-valid `RenderRequest` and
`WorkerTransportRequest` envelopes, validate worker `RenderResult` responses,
redact bearer authorization before storing metadata or emitting evidence, and
record deterministic `IntegrationWorkerDispatch` envelopes. Existing worker
dispatches, render plans, artifact metadata, and complete snapshots are reused
idempotently. Worker failures, unknown jobs, and cross-config-entry jobs fail
closed before worker dispatch metadata, render-plan metadata, artifact
metadata, or complete snapshot storage. The packet remains read-only and
bounded: it does not read Home Assistant history during worker dispatch, does
not persist semantic memory, does not mutate Home Assistant state, does not
generate tokens, does not write real chart artifact files from the integration,
and does not add durable storage, retry/backoff, automatic progress tasks,
worker streaming, or production orchestration beyond bounded
provider/render/artifact/worker bookkeeping. The paired spec/BDD/eval/evidence
and
`evals/home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.py`
prove the anchor.

Home Assistant worker token provisioning/readiness scaffold anchor is complete.
Config-entry setup now records schema-valid `IntegrationWorkerReadiness`
metadata and keeps worker rendering disabled when no valid integration-owned
token is present. Explicit in-memory token provisioning stores one
config-entry-scoped integration-owned worker token only after validating
redacted readiness metadata, enables the existing ADR-0012 worker renderer
boundary for that entry, reuses existing valid tokens idempotently, rejects
unknown config entries before token generation, rolls back generated tokens when
readiness validation/storage fails, and keeps readiness/tokens isolated per
config entry. The packet remains read-only and bounded: it does not read Home
Assistant history, persist semantic memory, mutate Home Assistant state, call
the worker, render charts, write real artifacts, write durable token storage,
rotate tokens, perform worker health checks, add retry/backoff, start automatic
progress tasks, stream worker progress, or add production orchestration beyond
readiness bookkeeping and renderer gating. The paired spec/BDD/eval/evidence
and `evals/home_assistant_worker_token_provisioning_readiness_scaffold.py`
prove the anchor.

Home Assistant worker progress streaming scaffold anchor is complete. Enabled
`isolinear/v1/job/snapshot` worker render responses may now carry up to five
bounded progress payloads through the existing ADR-0012 worker render response
metadata. The integration validates each progress payload before storage,
appends schema-valid rendering snapshots before the final complete snapshot,
records redacted config-entry-scoped `IntegrationWorkerProgress` envelopes,
includes existing same-job subscription IDs, and idempotently reuses existing
complete/progress metadata without duplicate worker calls or duplicate progress
records. Invalid progress payloads and secret/token-bearing progress text fail
closed before worker progress metadata, worker dispatch metadata, render-plan
metadata, artifact metadata, or complete snapshot storage. The card-facing
WebSocket handler still returns only `IntegrationJobSnapshot` payloads, keeping
worker progress envelopes and worker endpoint metadata internal. The packet
remains read-only and bounded: it does not read Home Assistant history during
worker progress, persist semantic memory, mutate Home Assistant state, generate
tokens, write real artifact files, add durable worker-progress queues/storage,
add retry/backoff policy, add health checks, start automatic progress tasks,
introduce a new worker transport, or add production orchestration beyond
bounded progress bookkeeping. The paired spec/BDD/eval/evidence and
`evals/home_assistant_worker_progress_streaming_scaffold.py` prove the anchor.

Home Assistant worker retry/backoff policy scaffold anchor is complete. Enabled
`isolinear/v1/job/snapshot` worker render failures that return schema-valid
ADR-0012 `RenderResult` envelopes now record one deterministic
config-entry-scoped `IntegrationWorkerRetryPolicy` envelope before returning a
failed snapshot. The policy stores redacted worker request/response metadata,
bounded exponential backoff metadata, retry eligibility, manual-retry
availability, and `automatic_retry_scheduled: false`; it validates against
JSON Schema before storage. Unknown jobs, cross-config-entry jobs, invalid
worker render results, and secret/token-bearing failure codes fail closed
before policy storage or sensitive metadata exposure. The packet remains
read-only and bounded: it does not read Home Assistant history during policy
recording, persist semantic memory, mutate Home Assistant state, generate or
rotate tokens, write real artifacts, create durable retry storage, perform
worker health checks, schedule automatic retries, introduce a new worker
transport, change job retry behavior, or classify `accepted: false` worker
transport responses. The paired spec/BDD/eval/evidence and
`evals/home_assistant_worker_retry_backoff_policy_scaffold.py` prove the
anchor.

Home Assistant worker transport failure retry classification scaffold anchor is
complete. Enabled `isolinear/v1/job/snapshot` worker client responses that
return `accepted: false` before a valid render result now record one
deterministic config-entry-scoped
`IntegrationWorkerTransportFailureClassification` envelope before returning a
failed response. The classification stores redacted worker request metadata,
sanitized failure code/message, deterministic failure family for connection,
HTTP, malformed-response, unavailable, and unknown transport failures, retry
eligibility, manual-retry availability, `automatic_retry_scheduled: false`, and
bounded exponential backoff metadata. Unknown jobs and cross-config-entry jobs
fail closed before worker calls or classification storage, and secret/token
bearing transport failure codes/messages normalize to `worker_transport_failed`
and a generic message before storage or response. The valid failed
`RenderResult` retry/backoff policy path remains unchanged. The packet remains
read-only and bounded: it does not read Home Assistant history during
classification, persist semantic memory, mutate Home Assistant state, generate
or rotate tokens, leak tokens, write real artifacts, create durable retry
storage, perform worker health checks, schedule automatic retries, introduce a
new worker transport, or store worker dispatch/progress/retry-policy/render
plan/artifact/complete metadata for transport failures. The paired
spec/BDD/eval/evidence and
`evals/home_assistant_worker_transport_failure_retry_classification_scaffold.py`
prove the anchor.

Home Assistant worker failure snapshot/manual retry integration scaffold anchor
is complete. Enabled `isolinear/v1/job/snapshot` worker render failures and
worker transport failures now bridge existing validated retry policy and
transport classification metadata into schema-valid card-facing failed
`IntegrationJobSnapshot` payloads. Failed snapshots use sanitized failure
code/message text, `worker_render` or `worker_transport` stage,
`worker_failure_snapshot_ready` progress, and retry affordance derived from the
existing internal `manual_retry_allowed` decision. Enabled
`isolinear/v1/job/retry` callbacks can now resume retryable worker failed
snapshots through the existing retry continuation path, while non-retry-safe
transport failures reject as `job_not_retryable` before approved history reads
or new snapshots. Unknown jobs and cross-config-entry jobs fail closed before
worker calls, worker failed snapshot storage, retry-policy storage, or
transport-classification storage. The card-facing payload remains only an
`IntegrationJobSnapshot`; worker endpoint, request body, bearer authorization,
retry-policy metadata, transport-classification metadata, render-plan metadata,
artifact metadata, and dispatch metadata stay internal/redacted. The packet
remains read-only and bounded: it does not mutate Home Assistant state, persist
semantic memory, generate or rotate tokens, leak tokens, write real artifacts,
create durable retry storage, perform worker health checks, schedule automatic
retries, start automatic progress tasks, introduce a new worker transport, or
add production orchestration beyond the worker failure snapshot bridge. The
paired spec/BDD/eval/evidence and
`evals/home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold.py`
prove the anchor.

Home Assistant worker health/readiness endpoint scaffold anchor is complete.
ADR-0014 now records `GET /v1/health` as the concrete readiness endpoint over
ADR-0012's versioned bearer-authenticated worker transport.
`custom_components/isolinear/worker_health.py` owns the explicit
config-entry-scoped health probe, setup records only health-probe availability
without calling the worker, and eligible probes require an existing same-entry
ready worker client plus integration-owned worker token. Health requests and
responses validate against `WorkerHealthRequest` and `IntegrationWorkerHealth`
schemas; ready and not-ready worker responses store redacted internal health
envelopes, transport failures store schema-valid `unavailable` metadata
without retry/scheduler/durable side effects, and malformed accepted responses
fail closed before storage. Unknown entries and no-token/not-ready entries
fail before worker calls, tokens remain redacted in metadata and evidence, and
dashboard-card payloads do not expose worker endpoint, request, response,
authorization, or internal health metadata. The paired spec/BDD/evidence and
`evals/home_assistant_worker_health_readiness_endpoint_scaffold.py` prove the
anchor.

Home Assistant worker token rotation/repair scaffold anchor is complete.
`custom_components/isolinear/worker_readiness.py` now owns explicit
config-entry-scoped in-memory worker token rotation and repair functions.
Rotation requires an existing valid same-entry integration-owned worker token,
generates a replacement token, invalidates the old token and renderer client,
validates/stores redacted ready readiness metadata, and refreshes the same-entry
renderer setup. Repair creates a valid token only for known no-token entries
with configured worker endpoints. Unknown and cross-entry requests fail before
token generation or state changes, while readiness validation/storage and
renderer setup failures roll back token, readiness, and renderer state. The
packet remains read-only and bounded: it does not call worker render or health
endpoints, persist tokens durably, schedule repair, mutate Home Assistant state,
or expose worker endpoint, token material, readiness, health, or repair
internals to dashboard-card payloads. The paired spec/BDD/evidence and
`evals/home_assistant_worker_token_rotation_repair_scaffold.py` prove the
anchor. Focused and adjacent worker verification is green; the full Python
suite currently has an unrelated codegen sandbox matplotlib subprocess flake
documented in `STATUS.md`.

Home Assistant durable worker health polling checkpoint scaffold is committed.
ADR-0015 is now accepted, and the checkpoint adds
`custom_components/isolinear/worker_health_polling.py` plus setup/unload wiring
behind the existing worker readiness and ADR-0014 health-client boundaries. The
poller stores schema-valid redacted config-entry-scoped latest polling state in
an integration-owned storage-helper surface, enqueues post-setup polling
without setup-time worker calls, runs eligible scheduled health probes through
ADR-0014, applies the 300 second ready cadence and bounded
30/60/120/300/900 second failure backoff, removes targeted state on unload, and
keeps dashboard-card payloads free of worker endpoint, token material, health
internals, scheduler internals, repair recommendations, and durable polling
metadata. Rescue verification on 2026-06-12 reran the focused polling tests
(`17 passed`), adjacent worker regression bundle (`98 passed`), focused
durable polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`),
full Python suite (`268 passed`), and checkpoint diff formatting
(`git diff --check HEAD~1..HEAD` clean). BDD-evidence review and standalone
architecture review both returned OK with no required follow-up.

Home Assistant durable worker health polling maintainability refactor is
complete. `custom_components/isolinear/worker_health_polling.py` remains the
public orchestration facade, while constants, contract validation, storage
helper behavior, and state/redaction construction now live in focused
`worker_health_polling_*` helper modules. `src/Isolinear/worker_health_polling_anchor.py`
remains the public verifier facade, while fixtures, scenario cases, and the
aggregate verifier live in focused anchor helper modules. The refactor is
behavior-preserving: ADR-0015 polling semantics, schemas, BDD/evidence, eval
output, redaction, dashboard-card safety, and setup/unload wiring remain
unchanged; the existing BDD evidence note was refreshed with the refactor
verification posture. Verification on 2026-06-12 reran focused polling tests
(`17 passed`), the focused durable polling eval
(`PASS home_assistant_durable_worker_health_polling_scaffold`), adjacent
worker regressions (`81 passed`), module `py_compile`, `git diff --check`, and
standalone architecture review. A full `tests/` rerun hit the known unrelated
codegen sandbox matplotlib flake once (`267 passed, 1 failed`), and the exact
failed test passed on rerun.

Home Assistant durable worker health polling cancelled-state hardening is
complete. Persisted `IntegrationWorkerHealthPollingState` entries whose
scheduler metadata has `cancelled: true` are now rejected during
storage-helper load/resume, preventing unload-cancelled timer metadata from
being re-merged after restart. The scaffold spec, BDD, eval outline, evidence,
verifier anchor, and focused tests now prove cancelled persisted polling state
is skipped before merge while valid persisted entries, token-missing
diagnostics, and unsaved in-memory state remain intact. Verification on
2026-06-12 reran the focused polling tests (`17 passed`), focused durable
polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`),
adjacent worker regressions (`98 passed`), module `py_compile`, and
`git diff --check`. Standalone architecture review returned OK with no
recommendations.

Home Assistant durable worker token lifecycle scaffold is complete. ADR-0016
records the storage-helper credential persistence decision and the packet adds
`custom_components/isolinear/worker_token_lifecycle.py` plus setup wiring before
worker readiness and renderer setup. Config-entry setup loads the lifecycle
store, restores only valid same-entry persisted tokens after schema-valid
lifecycle storage succeeds, blocks readiness/renderer setup if lifecycle storage
fails, stores redacted `not_ready` repair-issue metadata when no token can be
restored, and stores disabled lifecycle state when no worker endpoint exists.
Durable explicit provision, rotation, and repair wrappers persist raw token
material privately and roll back old durable token, readiness, and renderer
state on lifecycle validation/storage failure. Dashboard-card token controls,
real Home Assistant Repairs flows, setup-time token generation, automatic repair
execution, worker health/render calls, provider calls, durable retry queues,
scheduler tasks, Home Assistant mutation, and token/endpoint leakage remain out
of scope. Verification on 2026-06-13 reran focused lifecycle tests
(`11 passed`), the focused lifecycle eval
(`PASS home_assistant_durable_worker_token_lifecycle_scaffold`), adjacent
worker regressions (`109 passed`), module `py_compile`, adjacent
worker/orchestration evals, `git diff --cached --check`, inline BDD-evidence
review, and standalone architecture review. The full Python suite previously
hit the known unrelated codegen sandbox matplotlib subprocess flake once
(`298 passed, 1 failed`), and the exact failed test passed on rerun.

The matplotlib loose-range requirement restoration packet is complete. Live
`0.1.18` testing confirmed the lazy-import fail-closed path fires correctly —
the card surfaced `failure.stage: chart_rendering` /
`RENDERER_DEPENDENCY_UNAVAILABLE` / "The trusted chart renderer dependency is
not installed in this Home Assistant environment." Charts cannot render on a
fresh HA install without matplotlib, so `matplotlib>=3.7,<4` is restored to
manifest `requirements`. The strict-pin `matplotlib==3.11.0` that caused the
0.1.16 config-flow 500 is not reused; a loose range delegates version selection
to pip's resolver so exact-pin conflicts with HA's own dependency set are
avoided. The integration scaffold guard is narrowed from flagging any
`matplotlib` prefix to flagging only `matplotlib==` exact pins, so future
accidental re-introduction of strict pins is still caught. The HACS packaging
spec, eval YAML, and proof assertions now require `matplotlib>=3.7,<4`. The
lazy-import fail-closed path remains intact as a backstop when pip install fails
in the target environment. The visible package version is `0.1.19`.

The planner entity_id enum-pin packet is complete (`0.1.27`). Live `0.1.26`
testing kept failing a binary-door prompt at `model_provider_planning` with
`model_provider_referenced_unapproved_entity` even though binary→`timeline`
routing was confirmed live. Root cause: the Ollama structured-output schema left
chart-spec `source.entity_id` a free string, so a small local model could
hallucinate an off-allowlist entity that the post-plan entity gate then rejected.
`load_planner_result_schema(family, *, entity_ids=…)` now pins `source.entity_id`
to an `enum` of exactly the disclosed entities (deduped; blanks dropped), and the
planning call site passes `request["approved_entity_ids"]` so the enum matches
the disclosure; constrained decoding now makes an off-allowlist entity
structurally impossible while the deterministic post-plan gate (Scenario L) stays
as defence in depth (no core schema-file change — the chart-spec sub-schema is
built in code). The packet also adds DEBUG request/response logging on the
`custom_components.isolinear.model_provider` logger (off by default; outgoing body
+ raw provider content + transport errors; no tokens/secrets on the planner path)
to diagnose future chart families. BDD Scenario P + evidence added. Verified
against the real Pillow renderer this session: full suite `394 passed, 3 failed`
(the 3 are the pre-existing codegen-sandbox subprocess flake, confirmed identical
on clean baseline); the live `0.1.27` retest still owes confirmation that a real
binary-door prompt now renders instead of failing at planning.

The structural provider-output entity gate packet is complete (`0.1.28`). The
live `0.1.27` retest revealed the enum-pin was correct but the binary-door prompt
*still* failed `model_provider_referenced_unapproved_entity`: gemma returned a
valid `timeline` spec referencing the approved entity, and the captured DEBUG
response proved the rejection came from our own validation. Root cause:
`validate_model_provider_output_entities` ran the `ENTITY_ID_IN_PROMPT` regex over
**every string** in provider output and mistook the model's `chart_id` slug
`binary_sensor.kitchen_door_timeline` for an off-allowlist entity reference. The
broad textual scan (`_entity_ids_in_provider_output` /
`_walk_provider_output_entity_ids`) was removed; the gate is now **structural** —
it validates only the fields that carry data-access or persistence meaning:
chart-spec `series`/`overlays` sources (unchanged) plus a new
`_memory_proposal_entity_ids` check for `memory_proposals` (a persisted, reusable
reference). Entity-shaped tokens in inert free-text fields (`chart_id`, `title`,
`notes`, axis metadata, `reasoning_summary`) are no longer treated as references —
the renderer never reads them, so this loses no real safety while removing the
false-positive class. The `ENTITY_ID_IN_PROMPT` regex remains for user-prompt
entity parsing only. Posture chosen with Colin: structured-only, with inert
mentions fail-soft and off-allowlist `memory_proposals` still failing closed. The
entity enum-pin (0.1.27) is unchanged; invariant #1 holds (and is strengthened —
it no longer false-rejects valid plans). The recursive anchor/test/eval were
reworked to `hidden_memory` (rejects) + `entity_named_chart_id` (renders), and the
planning-scaffold spec, BDD Scenario C, and evidence were corrected to the new
posture (Scenario C also carried the pre-ADR-0022 stale code
`model_provider_chart_spec_hidden_entity`, now fixed). The repository is ready for
a live HACS `0.1.28` retest confirming the real binary-door prompt now renders a
timeline.

The render-family capability envelope direction is captured as **ADR-0023**
(**accepted**, commit `5010302`) with a paired spec
(`render-family-capability-envelope.md`) and BDD that remain `draft` (they accept
when the implementation anchor lands). The decision: the integration computes a
deterministic *capability envelope* (the set of chart families the resolved data
*shape* supports — density is fail-soft, not a gate), the model selects the
family within it from user intent, and a deterministic post-plan gate rejects
out-of-envelope choices (`model_provider_chart_family_out_of_envelope`). It
revises ADR-0022 invariant #9. First live-renderer tranche is `histogram` +
`aggregate_bar`. Nothing is implemented yet.

The entity-selection specificity + timeout + timeline-readability packet is
complete (`0.1.29`). The live `0.1.28` retest **confirmed** the structural gate
fix — the binary-door prompt renders a timeline end-to-end — but surfaced that
entity *disambiguation* is the next rigidity: every multi-entity prompt forced a
clarification because the catalog matcher matched on *any* shared meaningful
token ("kitchen door" matched both `binary_sensor.kitchen_door` and
`climate.kitchen_ecobee` on the lone shared `kitchen`). **ADR-0024 is accepted**
and its **D1** is implemented: `select_prompt_entity_ids` now scores each
candidate by *how many* of its distinctive tokens the prompt contains and selects
the uniquely top-scoring approved entity (`source: catalog_label_specificity`)
when the set isn't an overlay composition; a top-score *tie* still clarifies
(offering only the tied candidates). Invariant #1 is refined in CLAUDE.md/AGENTS.md
— clarification is the *fallback*, not the first response to any multi-match, and
the allowlist boundary is unchanged. **D2** (model-driven selection on residual
ambiguity — a tie or zero matches) is staged as the next packet: it adds a small
pre-routing model selection call so the user sees a clarification card only when
the model itself abstains, and it ties into the ADR-0023 envelope work. The same
packet raised `DEFAULT_OLLAMA_TIMEOUT_SECONDS` 30 → 90 (a successful live call took
29.8s against the 30s wall; mixed/overlay prompts timed out at exactly 30s), and
fixed the binary timeline renderer to draw a light "off" track across the full
window with the "on" regions on top and an on/off legend, so a door closed all
morning reads as present-but-off instead of a blank lane. **ADR-0025 is drafted**
(not implemented): stream the model's reasoning into the card's chart slot as
ephemeral wait-feedback (`stream:true` + a bounded, sanitized `progress.reasoning`
on the active planning snapshot, surfaced through the existing ~1s poll loop,
replaced by the chart on completion). The cheaper "reasoning on the finished card"
(Tier 1) was rejected by product direction (no clutter); ADR-0025 implementation
is deferred until after ADR-0024 D2 so it streams across both model calls.
Verification: full suite `404 passed, 3 failed` (the 3 = pre-existing
codegen-sandbox flake), relevant evals `PASS`, renderer verified on disk,
architecture review (inline) `OK`. The repository is ready for a live HACS
`0.1.29` retest confirming the kitchen-door prompt skips clarification, mixed
prompts no longer time out, and the timeline reads clearly. Remaining cosmetic:
the timeline lane label clips against the axis.

The `0.1.29` live retest confirmed disambiguation is working. Two bugs surfaced
during testing of the `time_series_overlay` path and are fixed in `0.1.30`. First,
`select_prompt_entity_ids` composite detection was blocked when a categorical entity
(e.g., `climate.kitchen_ecobee`) matched a shared token alongside a numeric+binary
pair — the old guard required all non-numeric matches to be binary, so the composite
path was never reached and the temperature entity was dropped. The guard now requires
only one numeric match plus at least one binary match; categorical noise matches are
discarded (ADR-0022 D4 amended to document this). Second, `validate_chart_spec_contract`
now calls `_check_chart_spec_no_duplicate_series_sources` and rejects chart specs where
two series share the same `(type, entity_id, attribute)` source — this catches the
class of model error where a constrained planner returns two series from the same
entity with hallucinated labels. Verification: full suite `406 passed, 3 failed`
(pre-existing codegen flake), relevant evals `PASS`, architecture review CONCERNS
resolved via ADR-0022 D4 amendment. The repository is ready for a live HACS `0.1.30`
retest with a numeric temperature sensor + binary door sensor in the allowlist.

The model-driven entity selection packet (ADR-0024 D2) is complete (`0.1.31`).
When the deterministic specificity fast-path cannot resolve — a top-score tie
among candidates or zero catalog matches — the orchestrator now asks the model
to select the entity before showing the user a clarification card. A new
`select_entity` call on the planner client sends the candidate entity IDs as a
JSON Schema enum (constrained decoding, same pattern as the 0.1.27 planner
enum-pin) and returns the model's selection. The returned IDs are validated
against both the candidate set and the full approved catalog; any off-allowlist
result fails closed, and model abstention (`clarification_needed`) falls through
to the existing D3 clarification path. When no model provider is configured the
D2 step is skipped entirely. `select_prompt_entity_ids` was extended to include
`candidate_items` in its clarification return so D2 receives the narrowed
candidate set on ties and the full catalog on zero-matches. The BDD (5 scenarios
A–E) is accepted with 14 tests passing. Verification: full suite `420 passed, 3
failed` (pre-existing codegen-sandbox matplotlib subprocess flake, confirmed not
introduced by this packet), all evals `PASS`, BDD-evidence review `OK`,
architecture review `OK`.

**ADR-0025 — live planner reasoning streaming — shipped in `0.1.32`,
bug-fixed in `0.1.33`, hardened in `0.1.34`.** The full workflow landed in
`0.1.32` (ADR accepted, spec, BDD, TDD with 23 tests, frontend bundle rebuild):
the Ollama-compatible planner now streams (`stream: true`), the model's thinking
trace is sanitized and length-capped (2000-char rolling tail) into a per-job
live-reasoning slot, surfaced as `progress.reasoning` + a coarse phase label on
the active planning snapshot through the existing poll loop, and replaced by the
chart (or failure card) on completion. The reasoning is never persisted — the
stored snapshot is never mutated and the slot is cleared in a `finally` on any
terminal state. Streaming spans both model calls (D2 `select_entity` +
`plan_chart`); non-streaming/non-thinking providers fall back gracefully (D6,
nothing shown). The Lit card renders a monospace reasoning block
(`data-testid="planning-reasoning"`) in the chart slot during the wait.

`0.1.33` fixed two bugs found in live testing: (1) thinking-capable Ollama
models never streamed because `"think": true` was never sent — it is now sent on
streaming planner + entity-selector requests only (non-streaming calls
untouched); (2) `resolve_history_window` forced the 24h fallback whenever the
model returned naive ISO 8601 (no offset) — `_parse_window_timestamp` now treats
naive datetimes as UTC instead of rejecting them. Both fixes are test-covered
(`test_streaming_request_sets_think_true`,
`test_streaming_select_entity_request_sets_think_true`,
`test_non_streaming_select_entity_omits_think`,
`test_naive_timestamps_are_treated_as_utc`,
`test_parse_window_timestamp_attaches_utc_to_naive`).

`0.1.34` closed a redaction gap found by this closeout's architecture review:
`sanitize_reasoning` redacted URLs, `Bearer …`, and filesystem paths but **not**
the named secret vocabulary the rest of the card-facing surface already guards
against (`access_token`, `*_token`, `ollama_api_key`, `api_key`), nor bare
secret-like tokens (`sk-…` keys, JWTs). Since the thinking trace is unsanitized
model echo of a prompt that can contain such material, this was an invariant-3 /
ADR-0025 D5 gap. `sanitize_reasoning` now mirrors
`FORBIDDEN_WORKER_PROGRESS_TEXT`'s vocabulary plus `sk-…`/JWT patterns, with four
new redaction tests; entity IDs and the user prompt are still retained. No core
schema change. Verification: full suite `451 passed, 3 failed` (the 3 = the
pre-existing codegen-sandbox subprocess flake), all evals `PASS`, BDD-evidence
review `OK`, architecture review CONCERNS resolved by the `0.1.34` hardening.

`0.1.35` fixed two bugs found while retesting the `0.1.34` reasoning-streaming
build, both correcting existing behavior (no new architecture):

1. **`think`/`format` mutual exclusivity (ADR-0025 D1 correction).** A
   thinking-capable Ollama model still emitted no reasoning because the streaming
   payloads sent `think: true` *and* the structured-output `format` schema
   together — and Ollama silently suppresses thinking whenever `format` is set.
   ADR-0025 D1 had assumed both could coexist; they cannot. The streaming
   (reasoning) path now sends `think: true` and **omits** `format`, relying on
   system-prompt schema guidance plus a new `_strip_markdown_json` helper that
   strips the markdown code fences thinking-mode models wrap around their JSON.
   The non-streaming fallback keeps `format` for strict constrained decoding (it
   requests no thinking). This was confirmed as the last blocker to live
   reasoning streaming for thinking-capable models. ADR-0025 D1 and the streaming
   spec carry a correction note; the existing streaming-payload tests
   (`test_streaming_request_sets_think_true`,
   `test_streaming_select_entity_request_sets_think_true`,
   `test_non_streaming_select_entity_omits_think`) cover the contract and the BDD
   evidence file was refreshed (30 tests).

2. **Stopword fix for distinctive-token scoring (ADR-0022/0024 path).**
   `"temperature"` was wrongly excluded from the distinctive-token set in
   `_catalog_item_meaningful_tokens` (alongside the HA component prefixes
   `sensor`/`binary`), so a "kitchen temperature" prompt scored only on
   `kitchen` and tied with `kitchen_door`. `temperature` now counts toward the
   score, so an ecobee temperature sensor outscores a co-located door sensor
   instead of tying. Covered by the existing vertical-slice entity-selection
   tests.

No core schema change. These are bug fixes in existing mechanisms, so no new
spec/BDD/ADR was created (only correction notes to the ADR-0025/streaming-spec
text the `format` discovery invalidated) and a full architecture-review subagent
was not run (one-line fixes in documented mechanisms, below the review bar).
Verification: full suite `451 passed, 3 failed` (the 3 = the pre-existing
codegen-sandbox subprocess flake, confirmed identical on the clean baseline),
relevant model-provider/streaming/entity-resolution evals `PASS`, BDD-evidence
review `OK`.

`0.1.36` corrected the `0.1.35` fix again — the same ADR-0025 D1 mechanism, one
more layer down. Dropping `format` from the streaming call (the `0.1.35` change)
restored thinking, but it also removed `format`'s constrained decoding from the
*only* model call, and without that structural guarantee the model produced
invalid JSON structure on harder prompts (wrong field names, missing required
fields). Jobs that asked about entities **not** in `approved_entity_ids` — e.g.
"show me temperature and when the AC was running" — failed with
`invalid_planner_result` because the model hallucinated the schema structure.
The fix is a **two-pass approach**: when `on_reasoning` is provided, both
`plan_chart` and `select_entity` now make two sequential `/api/chat` calls.
*Pass 1 (think pass)* — `stream:true, think:true, no format` — streams the
reasoning chunks to the card via `on_reasoning`; its content is discarded and its
failures are non-fatal (reasoning is presentational, D6). *Pass 2 (plan/select
pass)* — `stream:false, format:result_schema, no think` — returns reliable,
schema-constrained JSON; this is the call whose result is parsed and validated.
When `on_reasoning` is None the sole call is Pass 2 (unchanged D6 fallback), so
`_strip_markdown_json` is no longer load-bearing for the result path. This
restores both live reasoning *and* constrained decoding at the cost of one extra
call. ADR-0025 D1 carries a "two-pass correction (0.1.36)" note and the streaming
spec's "Streaming planner transport (D1)" section was rewritten; no contract,
schema, or BDD change (transport-layer fix in a documented mechanism). Tests:
five cases in `tests/test_live_planner_reasoning_streaming.py` were updated to
handle the two-call pattern (routing the fake transport on the request `stream`
flag); `30 passed`. Verification: full suite `451 passed, 3 failed` (same
pre-existing codegen-sandbox flake, identical on clean baseline via `git stash`),
model-provider planning eval `PASS`, BDD-evidence review `OK`.

`0.1.38` fixed the final reason reasoning never appeared in the card. The
architecture (ADR-0025 D3: "surfaced through the existing poll loop at ~1s
granularity") was correct; the implementation failed to achieve the stated
granularity. The poll loop was **sequential** — each poll awaited the WebSocket
response before scheduling the next. The first post-submit poll acquires
`planning_lock` and drives all model calls (~40 s); no second poll fired during
that window, so every in-progress snapshot carrying `progress.reasoning` was
computed but never delivered. The fix (in `isolinear-card.ts`): call
`scheduleSnapshotPoll(generation)` **before** `await getSnapshot()`. Polls now
fire every 1 s regardless of response time. Concurrent polls hit the held
`planning_lock`, return in-progress snapshots with live reasoning immediately
(< 1 ms server cost), and the card renders them. The `pollGeneration` counter
plus `cancelSnapshotPolling()` guard stale responses when the main poll
eventually returns the complete snapshot. No server-side change. No ADR update
(D3 matches the behavior; the polling mechanism is implementation detail).
Frontend smoke tests: poll interval bumped 5 ms → 20 ms (longer than the 5 ms
mock response) so call-count assertions remain exact. Architecture review not
run (frontend-only polling bug fix; no invariant affected).

`0.1.44` ships **ADR-0023 — model-proposed render family within a deterministic capability envelope**. The integration now computes a capability envelope from each resolved entity's data shape before planning, widens the Ollama constrained-decoding schema to all valid families in that envelope, and enforces a deterministic gate that rejects any model-chosen family outside it. `_resolve_render_envelope` (`job_orchestration.py`) wraps the existing `_resolve_render_family`: single_numeric (exactly one numeric entity) → `[time_series, histogram, aggregate_bar]`; multi_numeric, overlay, timeline, and mixed remain single-member envelopes (backward-compatible). `validate_model_provider_chart_family` fires after `validate_chart_spec_contract` and before overlay composition; it is a no-op for single-member envelopes so ADR-0022 behavior is byte-preserved for all non-single-numeric shapes. `load_planner_result_schema` now accepts an `envelope` arg: single-member → identical to the ADR-0022 single-family schema; multi-member → `chart_type` enum widens to all families' values, `render_as` enum widens, `source.type` allows `["entity", "aggregate"]` when aggregate_bar is in the envelope, `source.operation` gains the five aggregate ops, `x_axis` allows optional `bin_count` / `group_by`; entity_id pin to the disclosed entity allowlist is unchanged (invariant #1). Multi-family prompt guidance replaces the single hardcoded "use chart_type X" rule with intent-based guidance telling the model to choose based on the user's question. Two new Pillow renderers added to `in_process_renderer.py`: `_render_histogram_png` bins numeric entity history into N bins (default 8), draws labeled bars; `_render_aggregate_bar_png` groups raw history points by time bucket via `x_axis.group_by` (day/hour, default day), applies one of five aggregate operations, draws one bar per period. Both renderers follow the ADR-0023 D6 fail-soft density rule: zero usable numeric points → `ValueError` → `in_process_renderer_failed`; any non-zero count (even 1) → a valid thin PNG. `render_in_process_chart` dispatch extended with histogram and bar branches alongside existing time_series/timeline. New `PLANNER_RENDER_FAMILIES` entries for histogram and aggregate_bar. All 9 CLAUDE.md invariants hold: #1 entity allowlist pin unchanged; #2 read-only; #3 Pillow is in-process trusted (no subprocess); #4 schema-first (every render request validated); #5 gate fires before render; #7 deterministic routing; #8 no new external dependencies. Tests: 42 new in `tests/test_render_family_capability_envelope.py` (7 envelope shape, 7 gate, 7 schema, 6 histogram renderer, 8 aggregate-bar renderer, 4 single-member regression, 3 PLANNER_RENDER_FAMILIES). Eval: 3 new CASEs (`capability_envelope_routing`, `histogram_render`, `aggregate_bar_render`) in `evals/timeline_render_family_routing.py`. Full suite `554 passed, 3 pre-existing codegen-sandbox flakes`. Spec `docs/specs/render-family-capability-envelope.md` and BDD `bdd/rendering/render-family-capability-envelope-bdd.md` promoted draft→accepted; evidence file written for all 8 BDD scenarios.

`0.1.43` ships **ADR-0026 — model entity selection in the pollable planning phase**, fixing a regression introduced when ADR-0024 D2 landed: model entity selection ran synchronously inside the blocking `job/start` handler, so a live `job/start` measured **15.2s** (gemma4:e4b @ 10.0.1.39) while the card sat inert with no feedback, and the selection reasoning was never polled — ADR-0025 D7 ("continuous reasoning submit→chart") was structurally unsatisfiable. The fix moves the whole selection block (D1 `select_prompt_entity_ids` + `_inject_semantic_aliases` + D2 `_resolve_entity_selection_with_model` + the D3 clarification decision) out of `job/start`/`job/retry` and into the first `job/snapshot` poll, behind the existing single-flight `planning_lock`. `job/start`/`job/retry` now append a new artifact-source `planning` snapshot at stage `ENTITY_SELECTION_PENDING_STAGE` (`_defer_selection_to_planning`) and return immediately with **zero model calls**; the first poll routes that stage through `_resolve_pending_entity_selection` under the lock, which runs the unchanged D1→alias→D2 pipeline and then either appends a clarification/failed terminal snapshot (returned to that poll) or builds the entities-bearing planning snapshot (reusing `_defer_history_to_planning`) and flows straight into planning/render — all under one lock acquisition, so concurrent polls surface the live selection reasoning via `apply_live_reasoning`. Resolution semantics are byte-for-byte unchanged; only the call site moved. An empty approved catalog stays a **synchronous** `job/start` rejection (`_synchronous_empty_catalog_failure`) — pre-model structural rejections are not deferred. The resolved selection caches write-once on `job["entity_selection"]` (D4 idempotency belt-and-suspenders; the lock already guarantees one model call). **Deviation from the spec's unconditional framing:** deferral is gated on `first_real_vertical_slice_enabled`, so the legacy scaffold path keeps synchronous selection (no model latency there; smaller blast radius). Invariants hold — #1 allowlist (selection logic unchanged, off-catalog still fails closed), #2 no mutation, #4 schema-first (every snapshot validated), #5 deterministic validation; the change that triggered ADR-0026 (#8) is the **observable contract of `job/start`/`job/retry`**, which no longer return terminal states. Implemented Opus (the relocation + idempotency) then a **Sonnet subagent** mechanically migrated 8 existing tests that asserted a terminal `job/start` to assert on the first poll. Tests: new `tests/test_entity_selection_pollable_phase.py` (7 — anchor zero-model-call start, clarify-on-poll, render-on-poll, idempotency ×2, synchronous empty-catalog, retry deferral). Full suite `519 passed, 3 pre-existing codegen-sandbox flakes`; affected orchestration/semantic evals PASS. ADR `docs/decisions/0026-entity-selection-in-pollable-planning-phase.md`, spec `docs/specs/entity-selection-in-pollable-planning-phase.md`, BDD + evidence under `bdd/integration/`. **Deployed + live-confirmed:** pushed origin/main `7466ee5`, HACS redownload + HA restart via API; live retest proved `job/start` 0.01s, "Selecting entities…" reasoning streaming 24→1443 chars, then "Planning chart…", completing with a real served PNG — the full submit→selection→planning→chart reasoning stream now works on the API. Card-side display still pending a browser hard-reload (the served bundle is correct and matches the repo; a stale cached `isolinear-card.js` is the suspect). Two follow-ups logged to the open queue: (j) a `gemma4:e4b` multi-concept overlay planning failure (`model_provider_planner_not_chart_spec_ready`, unrelated to ADR-0026), and (k) a cosmetic planning-phase label during deferred selection.

`0.1.42` ships semantic alias **Tranche 2** (propose/confirm/save) per `docs/specs/semantic-alias-save-tranche2.md`. Answering an entity-selection clarification with `remember: true` now saves a `SemanticAlias` so the same concept never needs clarification again. `_clarification_option_for_item` sets `can_remember` (opt-in per clarification type; entity selection passes `True`, future types default `False`); `_append_clarification_snapshot` precomputes `job["alias_suggestions"]` keyed by option_id (internal job state, never serialised) via the new pure helpers `derive_alias_natural_names` + `_entity_id_to_alias_id` in `semantic_memory.py`. On answer, `_maybe_save_semantic_alias` builds the alias (`meaning: {type: entity, entity_id}`, `source: user_confirmed`, prompt sanitised + truncated by `_sanitize_prompt_for_storage`), and persists via `SemanticMemoryStorageHelper.save_alias`. **Key implementation fact:** the `clarification/answer` handler runs in a Home Assistant **executor thread** (not the event loop), so `save_alias` is **synchronous** — it validates the full store envelope, updates the in-memory store (immediate Tranche 1 availability), and schedules a near-immediate `Store.async_delay_save(…, 0)`, mirroring `worker_token_lifecycle.write_token_entry`. The spec's draft "await on the event loop" premise was wrong; the deviation is recorded in the spec's acceptance notes. Save failure is non-blocking (WARNING, job proceeds as `remember: false`). The complete snapshot now carries an `aliases` display array (`{name, meaning}`) built from `job["alias_display"]` via `_alias_display_entries` (fail-open); the `IntegrationJobSnapshot.aliases` schema field already existed, so only the `append_validated_job_snapshot` passthrough was added. Invariants verified by fresh architecture review (OK): #1 (saved aliases reference allowlisted entities; injection validity re-checked at use time), #4 (alias + store-envelope schema-validated before write), #7 (deterministic alias_id, same-id replace, not duplicate), #8 (no new storage mechanism; decision already in ADR-0009/0010). Tests: `tests/test_semantic_alias_save_tranche2.py` (17 — derivation, save append/replace/validate/schedule, full clarification→remember→save→reuse round trip incl. complete-snapshot `aliases`). Eval: new CASE `semantic_alias_save_and_reuse`. Full suite `512 passed, 3 pre-existing codegen-sandbox failures`.

`0.1.41` ships the **ADR-0024 D2 expansion**. D2 model entity selection previously ran only on the residue path (a top-score tie or zero matches); it now also runs as a validation/expansion pass after a *confident* single-entity D1 result (sources `catalog_label` / `catalog_label_specificity`), re-querying the **full** catalog with the D1 pick supplied as `already_selected_entity_ids` so the model can add a concept the prompt named that token scoring missed — the motivating "show kitchen temp and when the AC was running" case where `climate.kitchen_ecobee` shares no token with "AC". A new `_resolve_entity_selection_with_model` helper in `job_orchestration.py` unifies both call sites (job start + retry continuation); `_run_model_entity_selection` gained the `d1_selected_ids` context arg. **Safe fall-back:** if the model abstains, is absent, or returns an off-catalog pick, D1's confident result stands — expansion never downgrades a confident resolution to a clarification, and off-catalog picks still fail closed (invariant #1). Expansion is skipped for `explicit_entity_id`, `numeric_with_overlay`, and `semantic_alias` sources (already certain or user-confirmed) and when D1 already covers the whole catalog. The `select_entity` prompt gained an HA domain hint ("climate entities represent HVAC systems …") so functional vocabulary maps to HA domains without hard-coded word lists. Spec `docs/specs/entity-resolution-spec.md` and `docs/decisions/0024-model-driven-entity-selection.md` (expansion note) updated; BDD `bdd/entity-clarification/model-entity-selection-d2-bdd.md` gained Scenarios F–I + evidence. 11 new tests; full suite `495 passed, 3 pre-existing failures` at packet close. Architecture review OK.

`0.1.40` ships semantic alias live wiring Tranche 1 (ADR-0009/0010). The integration now loads a persisted per-config-entry `SemanticMemoryStore` envelope, matches valid enabled aliases to the prompt by token overlap, and injects matched entity IDs into entity selection before planning. A new `SemanticMemoryStorageHelper` class provides dual-backend storage: Home Assistant `Store` in production and an in-memory backend for tests/scaffold (same pattern as `WorkerTokenLifecycleStorageHelper`). `prepare_semantic_memory_for_planning` computes use-time validity against the current catalog — unavailable or non-allowlisted entities exclude an alias from injection — and never mutates the persisted store. `alias_matches_prompt` tokenizes with `[a-z0-9_]+`, strips trivial stop words, and requires token-overlap ratio ≥ 0.6 with no minimum-length floor (unlike the entity selector's 4-char floor) — "AC" as a 2-char token is the motivating signal. `_inject_semantic_aliases` in `job_orchestration.py` composes alias-injected entity IDs with the direct selection, de-duplicated, with `source: "semantic_alias"` and `matched_alias_ids` recorded for auditability. All 9 CLAUDE.md invariants verified: injected entities are `visible_to_agent: true` (allowlist boundary preserved, invariant #1); no store write occurs in Tranche 1 (propose/confirm/save is Tranche 2); injection is deterministic from a user-confirmed alias (invariant #7). Spec `docs/specs/semantic-alias-live-wiring.md` accepted. 33 new unit tests; 7 BDD scenarios in `bdd/semantic-memory/semantic-alias-live-wiring-bdd.md`; eval anchor CASE `semantic_alias_injection` added to `evals/semantic_memory_store_envelope.py` showing `climate.kitchen_ecobee` injected with `source: semantic_alias` from prompt "show kitchen temp and when the AC was running". Full suite: `484 passed, 3 pre-existing codegen-sandbox failures`.

`0.1.39` adds two operational improvements with no user-facing behavior change: (1) **Entity resolution DEBUG logging** (`job_orchestration.py`): seven `_LOGGER.debug()` calls throughout `select_prompt_entity_ids` — catalog entity list on entry, explicit entity IDs in the prompt, per-candidate scores, and the resolution path taken (single match, overlay composition, unique top scorer, or tie → clarification). Requires `custom_components.isolinear.job_orchestration: debug` in `configuration.yaml`. This was requested after the live 0.1.38 retest to diagnose why "kitchen temperature + AC" dropped `climate.kitchen_ecobee`: the entity IS in the allowlist but its name has no overlap with the token "AC", so the temperature sensor wins specificity (3 tokens vs 2); the root fix is semantic alias live wiring (packet #1). (2) **`num_predict: 512` cap on think pass** (`model_provider.py`, both `_chat_payload` and `_entity_selector_payload`): caps thinking-token generation during the think pass to reduce live latency from 24–44 s to ~10–15 s; the result pass (Pass 2) is uncapped. No new ADR, spec, or BDD — both changes are below the user-facing behavior bar. Verification: `444 passed` (pre-existing codegen-sandbox subprocess flake excluded), entity-catalog and model-provider-planning evals PASS, BDD-evidence review OK. Also records the 0.1.38 live retest findings: reasoning streaming not visible — most likely Edge serving a cached pre-0.1.38 bundle despite `?v=0.1.38`; polling code IS correct in the deployed bundle.

`0.1.37` fixed a semantic bug exposed by the `0.1.36` constrained-decoding pass.
The `_chat_payload` planning rules carried an unconditional rule 2 — "Return
status chart_spec_ready with a ChartSpec for this packet." With Pass 2 now
reliably producing schema-valid JSON, the model satisfied that rule even on
prompts asking about something **not** in `approved_entity_ids`, by relabeling or
reusing an approved entity to stand in for the missing one. For "show me maren's
room temperature and when the AC was running" with only
`sensor.maren_ecobee_sensor_temperature` approved, it returned two series both
sourced from that one temperature entity ("Room Temperature" + "Kitchen AC
Status") — structurally valid, semantically wrong, and a soft brush against
invariant 1 (clarify, never silent guess). The fix replaces the unconditional
rule with three: (1) return `clarification_needed` with a `clarification_question`
when the prompt references a device/sensor/concept not represented by any
approved entity — never invent, relabel, or reuse an entity to stand in for a
missing one; (2) return `chart_spec_ready` only if every requested piece of
information is satisfiable with approved entities; (3) each series must represent
a distinct approved entity, never multiple series for the same `entity_id`. This
is a prompt-engineering change inside `_chat_payload`; the `plan_chart` docstring
documents the two-pass streaming mechanism (ADR-0025), not the rule content, and
the statuses plus clarify-not-guess behavior are already the documented contract
(invariant 1, entity-clarification / entity-allowlist BDD), so no schema, spec,
ADR, or BDD change was needed. Verified live against Ollama (the maren/AC prompt
now returns `clarification_needed` with an appropriate question); full suite
`451 passed, 3 failed` (same pre-existing codegen-sandbox flake; no codegen file
touched), model-provider planning eval `PASS`, BDD-evidence review `OK`.

## Next recommended packet

**Semantic alias live wiring — learned entity knowledge (now #1).**

Root cause: the kitchen ecobee climate entity controls whole-house AC but is
named for its location. The model has no way to know "AC running" →
`climate.kitchen_ecobee`. This pattern is universal (HVAC entities named for
sensor location, not function) and aliases are the right fix.

**What's already in place (do not re-implement):**
- `SemanticAlias` + `SemanticMemoryStore` schemas fully designed (four meaning
  types: `entity`, `state_interval`, `threshold_interval`, `aggregate`).
- `src/Isolinear/fake_slice.py` has alias matching, invalidation, and
  `saved_semantic_aliases` proposal logic — port this to the live path, don't
  rewrite it.
- Evals: `semantic_memory_store_envelope.py`, `semantic_alias_invalidation.py`,
  `threshold_interval_use_once.py`, `threshold_interval_alias_reuse.py`,
  `threshold_interval_use_and_remember.py`.
- ADR-0009 (accepted): HA integration owns the memory store.
- ADR-0010 (accepted): semantic memory store envelope.

**Tranche 1 — load/match/inject (the foundational path):**
1. Persist `SemanticMemoryStore` to HA storage (`hass.data` / `Store`) keyed by
   `config_entry_id`. Load at integration setup; save on write.
2. At entity-resolution time, match enabled aliases against the user's prompt
   tokens (same scoring logic as `fake_slice.py`). Inject matching alias
   entity IDs into the approved entity catalog so the specificity fast-path
   and model-driven D2 selector both see them.
3. Mark alias-resolved entities distinctly in the catalog entry so the planner
   can use them (and the validation gate enforces allowlist membership still
   applies — aliases cannot bypass the allowlist boundary, invariant #1).
4. New spec + BDD for Tranche 1 before any code (ADR-0009 + ADR-0010 are
   already accepted; check if a new ADR is needed for the live wiring contract).

**Tranche 2 — propose/confirm/save (the learning path):**
5. Extend the live planner result schema with optional `saved_semantic_aliases`
   (already in `fake_slice.py` result shape; wire it into the planner output
   schema and validate).
6. After a successful render, if the model proposed aliases, surface a
   "Remember this?" confirmation in the card (new card UI state).
7. On user confirm: write alias to storage. On reject: no-op.
8. Spec + BDD for Tranche 2 before implementing the card UI.

**For the AC case specifically**, the alias the system should eventually learn:
```json
{
  "alias_id": "whole_house_ac",
  "natural_names": ["ac", "air conditioning", "central air", "air conditioner"],
  "meaning": {
    "type": "state_interval",
    "entity_id": "climate.kitchen_ecobee",
    "attribute": "hvac_action",
    "active_values": ["cooling"]
  }
}
```
In the meantime, manually seeding this alias into the store (by editing the
storage JSON) is a valid workaround while Tranche 2 is pending.

**Session start for this packet:** read ADR-0009, ADR-0010,
`src/Isolinear/fake_slice.py` (alias matching section), `semantic-alias.schema.json`,
`semantic-memory-store.schema.json`, and the existing evals before writing any
code or specs.

---

**Live HACS reasoning-streaming retest — RESOLVED in `0.1.35`.** The blocker
behind the `0.1.34` retest item (reasoning text not appearing for
thinking-capable models) was the `think`/`format` mutual-exclusivity bug, now
fixed: with `format` dropped on the streaming path, a thinking-capable Ollama
model emits reasoning into the chart slot during planning. A live HACS `0.1.35`
retest is still worth a quick confirmation in the field (reasoning text appears
in the chart slot during planning; "last 4 hours" resolves to a 4-hour window,
not 24h), but it is no longer a blocking unknown.

**ADR-0023 capability envelope (now #2)** — histogram + aggregate_bar first
tranche; spec + BDD drafted, ADR accepted — implementation-ready.

**Night mode (now #3)** — dark theme for chart PNG + card UI, auto-following
HA theme. Needs spec + likely an ADR (schema-touching: theme plumbed card →
render request).

Confirm the live retest against real Home Assistant + Ollama:

0. A real `binary_sensor` prompt that previously failed with
   `model_provider_referenced_unapproved_entity` now renders (the `0.1.28`
   structural gate — this was the live `0.1.27` false positive). If it still
   fails at planning, capture the DEBUG `Isolinear -> / <- Ollama plan_chart`
   log lines (enable the `custom_components.isolinear.model_provider` logger at
   DEBUG).
1. A real `binary_sensor` prompt (e.g. "kitchen door last 24 hours") renders an
   on/off **timeline** PNG instead of the old
   `model_provider_chart_spec_hidden_entity` failure (0.1.25).
2. A mixed prompt ("show me the temperature and when the AC was running")
   renders a numeric **line with the AC-on regions shaded behind it** (0.1.26).
3. A numeric prompt still renders a line chart; a long-window `state_class`
   sensor still renders daily statistics with a min/max band.
4. Capture the WARNING log line shape for any `mixed_chart_composition_unsupported`
   or disambiguated entity failures.

Then **Night mode** (item (h)) is the next net-new feature (spec + likely ADR).

Then run the served-artifact prompt path against real Home Assistant sensor
history and the configured Ollama planner. The key success signal is a rendered
chart PNG, not `RENDERER_DEPENDENCY_UNAVAILABLE`. The key log line shape is:
`Isolinear WebSocket command accepted/rejected: message_id=... type=...
requested_config_entry_id=... resolved_config_entry_id=... job_id=...
code=... result_code=... snapshot_status=... progress_stage=...
failure_code=... exception_type=...`.

If the card still reports `RENDERER_DEPENDENCY_UNAVAILABLE` after `0.1.19` is
installed, the pip install of matplotlib failed — check HA logs for the exact
pip error before changing the manifest again. Do not restore a strict
`matplotlib==X.Y.Z` pin. If a model-provider failure arrives, it should surface
as `failure.stage: model_provider_planning`. If the logs show
`code=isolinear_websocket_command_exception`, inspect that line's fields before
changing card behavior.

Preserve the known codegen sandbox matplotlib subprocess flake as a historical
caveat; the first-real-slice closeout full Python suite passed cleanly
(`303 passed`) before this manual verification follow-up.

## Known unresolved design details

- Overlay follow-ups beyond 0.1.26: overlay for ≥2 numeric primaries
  (multi-axis), overlay on the `timeline` family, and categorical (non-binary)
  overlays. A dedicated `timeline_history_unavailable` code for beyond-retention
  binary windows (0.1.25/0.1.26 reuse `no_long_term_statistics`).
- Semantic-memory storage-helper implementation, migrations, and repair UI details beyond the envelope contract.
- Aggregate-style ambiguous entity clarification and aggregate alias
  creation/reuse executable evals beyond the existing threshold-backed proofs.
- Optional future allowlist picker ergonomics beyond Home Assistant's native
  multi-entity selector, such as device/area/label grouping. The stored
  allowlist must remain explicit entity IDs.
- Worker token rotation UI or real Home Assistant Repairs/automatic repair
  semantics,
  automatic/durable provider retry semantics, additional durable polling
  production hardening if requested, and long-running worker progress
  streaming semantics beyond the current bounded provider retry-policy,
  provider health diagnostics, worker progress, worker retry-policy,
  transport-classification, worker-failure snapshot, worker-health, token
  rotation/repair, durable token lifecycle, durable polling scaffolds, durable
  polling maintainability refactor, and cancelled-state hardening.
- Production entity-registry, device-registry, area-registry, and label
  adapters beyond the scaffold-compatible approved entity metadata shape.
- Live Home Assistant dashboard browser smoke against a real dev server remains
  unresolved; the completed hardening packet covers a mounted card plus the
  registered command path, and the prior manual proof used real Home Assistant
  core with a test connection object.
- Production worker packaging details for matplotlib and target Home Assistant/Raspberry Pi images.
- Post-MVP floorplan heatmap geometry, upload/storage, and room-mapping contract.
- Production worker token rotation UI or real Home Assistant Repairs/automatic
  repair behavior, automatic/durable provider retry behavior, durable retry
  queue/scheduler behavior, and orchestration retry/backoff policy beyond
  scaffold snapshots.

## Session log

Per-session details live in `STATUS.md` (rolling 5-entry log) and git history. See the rolling log at the top of `STATUS.md` for recent session summary (packet name, what closed/changed, test posture). Older sessions are archived in git commits.
