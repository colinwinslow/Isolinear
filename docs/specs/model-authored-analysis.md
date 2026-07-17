---
status: accepted
date: 2026-07-02
depends-on-adrs: [0031, 0030, 0029, 0027, 0022, 0012, 0008, 0006, 0005]
---

# Model-authored analysis: grounded answers + supporting charts

## Status

Accepted. Defines the contract surface for **ADR-0031 tranche 1** — Isolinear
answers a natural-language question about approved sensor data with a **grounded
natural-language answer plus a supporting chart**, both computed by the worker.
The answer channel is purely additive on top of the accepted codegen render path
(ADR-0030 / [codegen-generation-path.md](codegen-generation-path.md)); the PNG
pipeline is untouched. This spec also lands the ADR-0031 decisions that make that
answer trustworthy: the **grounding principle** (decision 3), the **two-part
quality validation** with **progressive-verification UX** (decision 8), the
**data-boundary timestamp normalization** (decision 9), the **scipy + seaborn**
library additions (decision 6), and **tranche-1 transforms** (decision 5).

## Related docs

- [bdd/model-authored-analysis/model-authored-analysis-bdd.md](../../bdd/model-authored-analysis/model-authored-analysis-bdd.md) — observable behavior
- [codegen-generation-path.md](codegen-generation-path.md) — the render path this extends (generate → dispatch → repair)
- [card-legend-and-summary.md](card-legend-and-summary.md) — the ADR-0027 caption slot the answer promotes
- ADR-0031 — model-authored analysis (the direction this implements)
- ADR-0030 — codegen primary render path + pandas + repair-everything
- ADR-0029 — worker revival, data boundary, repair loop
- [STATUS.md](../../STATUS.md) — current phase and active work

## Context

ADR-0030 made sandboxed matplotlib codegen the primary render path and put
pandas in the worker image. With open-ended, sandboxed, repairable codegen the
model can already *compute* over approved history — the missing product piece is
letting it **answer the question in words**, not just draw. Many one-off home
questions ("are the upstairs and downstairs temps correlated?", "how fast does
the family room cool after the AC shuts off?") want a *sentence with a computed
number in it* as the primary output, with the chart as support.

The wire distance is short (ADR-0031 Rationale): the sandbox runner already
returns a **metadata dict** from `render_chart(data, output_path)` alongside the
PNG — the answer is one field on a dict that already crosses the boundary, with
no sandbox-security change. The ADR-0027 caption slot already renders
model-authored text. This spec adds the answer as a first-class, *grounded*
output and the validation that keeps it honest.

The real-data benchmark (`evals/analysis_benchmark/`, ADR-0031 Benchmark
evidence) established three things this spec operationalizes: (1) local
3060-class models produce good analysis code with one repair round **once the
data contract is clean** — but a raw ISO-timestamp contract mugged them via a
`pandas.to_datetime` format-inference gotcha (decision 9); (2) "did it run" is
not "is it right" — confident answers rode broken charts (decision 8); (3) with
a clean contract, scipy correlation and `seaborn.heatmap` work on real HA
history (decision 6).

## Behavior contract

### 1. The answer channel (additive, grounded)

**Sandbox (no security-model change).** The `render_chart(data, output_path)`
contract is unchanged; its returned metadata dict MAY carry a new optional key
`answer_text` (a string). `_normalize_render_metadata` in
`worker/isolinear_worker/codegen_sandbox.py` passes `answer_text` through
(alongside the existing `title` / `series_plotted` / `warnings` / …) as an
optional field, defaulting to absent. No new entry point, no new import, no new
write; the answer is text the generated code already computed.

**Schema surfaces (all additive, optional, back-compatible; both synced copies
per file — `docs/schemas/` and `custom_components/isolinear/schemas/` stay
byte-identical):**

| Schema | Field | Type | Meaning |
|---|---|---|---|
| `render-result.schema.json` | `render_metadata.answer_text` | optional string | The grounded answer sentence returned by the sandbox. |
| `integration-artifact-metadata.schema.json` | `answer_text` | optional string | Persisted with the served artifact. |
| `integration-job-snapshot.schema.json` | `chart.answer_text` | optional string | Delivered to the card on the complete snapshot. |

**Grounding principle (load-bearing, ADR-0031 D3).** The generated code computes
AND formats the answer: the model authors the sentence with **placeholders**
filled *inside the sandbox at execution time* from computed variables (an
f-string / `.format` over e.g. a `df.corr()` result). Every part of the sentence
that is a claim about the data — number **or** qualitative verdict — comes from a
computed variable (`verdict = "Yes" if abs(corr) > 0.3 else "Not really"`); the
model's free-text is limited to framing true regardless of the data. The answer
is **never** a second free-text model pass over raw data. This is enforced by the
**codegen prompt** plus the **deterministic answer-grounding check** (below), not
by structural decomposition into number+label metadata fields (ADR-0031 D3
capability-floor rationale).

### 2. Codegen prompt extension (grounding instruction + the analysis-intent conduit, ADR-0034)

`generate_chart_code` / `repair_chart_code` (model_provider.py) gain a grounding
instruction: emit `answer_text` in the returned metadata dict, assembled from
computed variables, with **verdicts computed, not asserted** (compute
`"Yes"/"No"` from a threshold over a computed value; never write the judgment
before the computation runs). The generation request already carries only the
validated ChartSpec + the normalized render data (the ADR-0029/0030 data
boundary; no token or secret ever enters the prompt).

**The analysis-intent conduit (ADR-0034).** The codegen prompt also carries the
user's original request as a bounded `user_request` field (a generation-time
argument to `generate_chart_code`/`repair_chart_code`, distinct from the render
request — it never enters the worker dispatch), and the codegen task is reframed
to "fulfill user_request" (guided by the ChartSpec). This is load-bearing:
without it the codegen model that writes the matplotlib never sees the ask, so
the answer instruction — previously keyed on "if the prompt asks a question", a
prompt the model was never shown — was dead code, and every transform /
correlation / question prompt collapsed to plotting the raw inputs (measured
live, 16th-session e2e run; and offline on the production path, baseline 0/12
fired vs 12/12 with the conduit). Two codegen prompt rules become
request-conditional:

- **Plot rule (default-with-exception).** Raw-line plotting of each numeric
  series stays the DEFAULT (grounding from §3 preserved); the EXCEPTION is that
  when `user_request` asks for a computed analysis (cross-sensor average,
  difference, correlation, deviation, smoothing, distribution), the model
  computes the derived series from the numeric `history_series` points and plots
  the derived result. An empty `user_request` leaves the exception inert → the
  raw-line default, so callers that omit it are unaffected.
- **Answer rule** keys on `user_request` asking a question. The D3 grounding
  contract (compute-and-f-string, claims ledger, verdicts derived) is unchanged;
  the deterministic answer-grounding check (§5a) now actually gates live answers
  because the answers now fire.
- **Cross-series alignment via the in-sandbox helper (ADR-0036, 0.2.34 —
  supersedes the 0.2.24 literal idiom and the 0.2.31 frame-keying idiom in the
  RULES; both idioms now live INSIDE `isolinear_analysis.align`).** The
  exception clause prescribes: for ANY math across two or more series, call
  `frame = isolinear_analysis.align(data['history_series'])` — a curated,
  integration-authored helper installed in the worker image's system
  site-packages and allowlisted for generated-code import. It aligns every
  numeric series onto one shared interpolated grid and returns a DataFrame
  whose **columns ARE the entity_id strings**, raising a specific,
  repair-actionable `ValueError` on degenerate inputs (no numerics, no finite
  points, no overlap) instead of ever yielding an empty/all-NaN frame. The
  rule then gives the per-member one-liners (`frame.mean(axis=1)`, column
  difference, `frame.corr().iloc[0,1]`, `frame.sub(frame.mean(axis=1),
  axis=0)`) and forbids hand-rolled alignment outright.
  - **History.** This is the third rung of the idiom-over-prose ladder: prose
    (failed live: union-index mean spike e2e-11, empty delta e2e-12, no-common-
    timestamps correlation e2e-13) → literal idiom in the rules (0.2.24
    resample idiom gated 9/9 vs 2/6 by `evals/alignment_rule_gate.py`; 0.2.31
    entity-id-keyed concat gated 0/40 vs 2/40 KeyErrors by
    `evals/crossmath_frame_keying_gate.py`) → callable (ADR-0036). The idiom
    rungs eliminated their target classes but left transcription variance:
    the 0.2.32 "nan °F" empty frame and e2e-18's repair-exhaustion cascade.
  - **Gate (`evals/analysis_helper_gate.py`,** production codegen path, 4
    cross-math members × 6 runs × 2 arms, disjoint irregular fixtures with
    known analytics, execution-truth judges): mean/delta/correlation 6/6
    first-attempt + fired in BOTH arms (no regression); **deviation — the live
    e2e-18 residual FAIL — 6/6 fired with the helper vs 4/6 with 2
    repair-exhaustions on the idiom arm** (the live Pillow-fallback failure
    reproduced offline); with the helper, repairs converge in ONE round
    instead of cascading through hand-rolled plumbing errors; helper adoption
    24/24; the rule text shrinks ~415 chars. Both arms share an unrelated
    deterministic first-attempt SyntaxError on the deviation prompt (a
    mis-bracketed literal, likely a series-valued claims attempt) — a separate
    emission quirk logged for follow-up.
  - The retired idiom text is preserved in the gate's `LEGACY_IDIOM` constant
    so the baseline stays re-runnable.
- **Chart-family degrade (open-queue (w), 0.2.26).** The integration owns the
  chart FAMILY — line, histogram, bar (invariant #9: the model never chooses
  `chart_type`); `user_request` owns only the COMPUTATION within it. A heatmap
  is a family, not a computation, and the ADR-0023 envelope has no heatmap
  family, so codegen must never draw a 2-D heatmap / matrix / grid (no
  `seaborn.heatmap`, `pcolormesh`, `imshow`, `hist2d`). A single-sensor
  "heatmap … by hour of day and day" request degrades to a histogram of that
  sensor's values (the distribution) — the family the planner already routes it
  to (`scripts/repro_e2e15_planner.py`, 6/6 → `histogram`). Rationale: the live
  e2e-15 garbage was the planner-chosen histogram spec colliding with a
  "heatmap" `user_request` inside codegen; locking the family to the planner's
  choice resolves the conflict and, per Colin's "ship simple" call
  (2026-07-07), keeps the word "heatmap" reserved for a future spatial /
  floorplan renderer (open-queue (c)). A temporal calendar heatmap, if ever
  built, becomes its own NAMED family, not an overload of "heatmap". Eval-gated
  with `evals/heatmap_rule_gate.py` (production codegen path, the live
  histogram chart_spec + the heatmap `user_request`, with/without the sentence,
  execution-truth judge = a clean 1-D histogram, not a 2-D `QuadMesh`/image).
- **Verdict/rule only for band judgments (open-queue (cc), 0.2.40 — a TWO-PART
  fix the gate surfaced).** _Prompt half:_ a claim carries `verdict`+`rule` ONLY
  when `user_request` asks a Yes/No or categorical judgment ("are they
  correlated?", "was it above 70?", "high or low?"). For a plain descriptive
  value answer ("what was the average / delta / total?"), the model emits a
  value-only claim (`metric`+`inputs`+`value`) and OMITS `verdict`+`rule`.
  Rationale: the grounding step-5 verdict containment (§5a, `answer_grounding.py`)
  requires the claimed `verdict` to appear verbatim as a band label in
  `answer_text`; a descriptive sentence like "the average was 72.9 °F" has no
  Yes/No label, so a spurious `verdict`+`rule` fails containment
  (`grounding_verdict_absent`/`_ambiguous`) and — because every re-generation
  recomputes the same correct number — burns the entire repair budget on a
  non-bug (live 25th-session e2e-11 log; masked until the 0.2.37 value-mismatch
  fix stopped withholding earlier at step 4). _Grounding half (which the gate
  proved necessary):_ under the prompt rule gemma nulls the `verdict` but often
  leaves a vestigial empty `rule: {"bands": []}` stub, which step-1 structure
  validation rejected as `grounding_claim_malformed`. But a rule is inert
  without a verdict (steps 5 and 6 both gate on `verdict is not None and rule is
  not None`), so `_check_claim` now skips rule-structure validation when
  `verdict is None` — treating a verdict-less claim as value-only. Together the
  descriptive mean is value-verified at step 4 and never blocked by an unusable
  verdict/rule. Eval-gated with `evals/verdict_omission_gate.py` (production
  codegen path, a descriptive two-sensor mean prompt, with/without the sentence,
  execution-truth judge = the real `run_grounding_check` SERVES the answer,
  `withheld=False`): **with-rule 3/3 served vs without-rule 0/3** (all three
  without-arm runs reproduced the live withhold via `grounding_verdict_absent`).
- **Correlation-answer emission + grounding (open-queue (ff), 0.2.41 — a
  TWO-PART fix).** Correlation prompts rendered the two input series but the
  analysis-answer layer under-fired: mean/delta/deviation/distribution/rolling
  all serve grounded answers, correlation did not (live 28th-session e2e-13/14/20;
  `scripts/repro_correlation_answer.py`). _Prompt half:_ unlike a mean/delta —
  which produces a derived SERIES the model plots (and plotting it reminds the
  model it did the analysis) — a correlation is a single SCALAR with nothing new
  to plot, so the floor model plots the two raw sensors, treats the chart as the
  deliverable, and returns WITHOUT an `answer_text`. A `_CODEGEN_PROMPT_RULES`
  sentence makes the coefficient the mandatory deliverable of a correlation
  question: plotting the raw sensors is explicitly not enough; the model MUST also
  compute `frame.corr().iloc[0, 1]` and report it in `answer_text`. _Grounding
  half (§5a, `answer_grounding.py`):_ even when the model emitted a correct
  coefficient, `_compute_pearson_r` recomputed on the exact-timestamp intersection
  of two sensors that share NO raw timestamps → empty → no reference → the answer
  could only ever be an `unverified-caveat`, never verified (the correlation
  analog of the 0.2.37 multi-input `mean` bug). The recompute now resamples each
  input onto the shared 5-min `align()` grid and correlates the paired buckets,
  matching the model's value to ~12 decimals. Eval-gated with
  `evals/correlation_answer_gate.py` (production codegen path, a correlation
  prompt over two genuinely-correlated sensors, with/without the sentence,
  execution-truth judge = the real `run_grounding_check` SERVES the answer):
  **with-rule 4/4 served and all 4 verified vs without-rule 0/4** (2 withheld
  `grounding_verdict_absent`, 2 runtime-exhausted).
- **Correlation verdict basis — the live-surfaced third part (open-queue (ff),
  0.2.44).** The 30th-session full live e2e (0.2.42) showed correlation STILL not
  serving on the same-metric temp-temp prompts (e2e-13, e2e-20). A faithful real-
  data repro (`scripts/repro_correlation_emission_realdata.py` — REAL kitchen/
  basement history, exact prompt) reproduced it **6/6** and revealed it was NOT an
  emission miss: the model emitted a CORRECT coefficient (`r ≈ -0.40`, grounding
  recompute matched to 13 decimals) but the answer was WITHHELD as
  `grounding_verdict_contradicted`. Root cause: the model derives its verdict from
  **magnitude** (`verdict = 'Yes' if abs(corr) > 0.3 else 'Not really'`) but the
  prompt's `pearson_r` example declared the rule with **`basis: 'value'`**. For a
  negative correlation strong enough that `|r| > 0.3` but `r < 0.3` (−0.40), the
  declared rule re-derives 'Not really' while the model claims 'Yes' → contradiction
  → withheld (and a withheld answer is suppressed on the card, so it looked exactly
  like a plot-only emission miss). Fix: the correlation claim's rule uses
  **`basis: 'abs'`** (correlation strength is magnitude), matching the `abs(corr)`
  verdict, plus an explicit CRITICAL rule that `basis` must match how the verdict
  was derived. `_apply_rule` already supported `basis: 'abs'`; the fix is purely
  the prompt. Grounding contract pinned by
  `TestCrossSensorPearsonR.test_negative_correlation_{value,abs}_basis_*`
  (value → contradicted+withheld, abs → verified).
- **Repair-intent retention (open-queue (B) — INVESTIGATED, NOT shipped).** The
  (B) packet was first framed as a repair-only instruction to preserve the
  `previous_code`'s derived series + `answer_text` while fixing a runtime error
  (targeting the rarer erosion the 20th session observed once — a two-repair
  chain that kept the mean series but dropped `answer_text`). Eval-gated on the
  production repair path (`evals/repair_intent_retention_gate.py`: a seeded
  `previous_code` that computes a cross-sensor mean + `answer_text` with a fixable
  runtime error, with/without the sentence), it showed **no separation — 3/3
  retained in both arms**: on a clean fixable error gemma minimally fixes it and
  keeps intent regardless. Per the 0.2.22 "failure-driven hints must earn their
  accept-rate" principle it was DROPPED. The investigation was still the key to
  (B): reproducing the live runtime_error showed it is an entity-id `KeyError` (a
  fix-RATE bug), not intent erosion — so the real fix is the entity-id-keyed
  frame rule above. The eval file is retained as a documented negative result.

### 3. Data-boundary timestamp normalization (ADR-0031 D9)

The render data handed to the codegen path MUST carry timestamps as **epoch
integers (milliseconds)**, not raw HA ISO strings. The normalization happens at
the integration data boundary, in the render-request projection that builds the
`render_mode: "codegen"` dispatch (`_build_worker_render_request` and the codegen
request it feeds) — history `points[].ts` are converted from the `date-time`
string form to epoch-ms integers before the data crosses to the worker. The
model never parses raw HA timestamps. (Rationale: the benchmark's dominant
failure was `pandas.to_datetime` inferring one format from HA's mixed-precision
first row; epoch-ms erases the whole class — gemma 2/16 → 12/16 strict.) The
Pillow fallback path and the trusted `render_mode: "safe"` worker path are
unaffected (they consume the existing `ts` shape).

**Prompt view vs. runtime data (context-window discipline, grounded preview).**
The generation and repair *prompts* MUST carry, per series,
`entity_id`/`kind`/`unit` and other series-level metadata, plus `point_count`,
`ts_epoch_ms_range`, `value_stats` (numeric series) or `distinct_states`
(binary/categorical state series, capped — ADR-0022), **and a bounded,
evenly-downsampled PREVIEW of the real points** — kept under the SAME key the
runtime data uses (`points`, with a `points_truncated` flag), first and last
point retained so the span is visible (`_history_series_prompt_view` /
`_downsample_preview`, `_CODEGEN_PROMPT_PREVIEW_POINTS`). The prompt MUST NOT
carry the full point list. The model authors code against this shape; the
COMPLETE points are delivered to `render_chart(data, output_path)` at runtime in
the sandbox under the same `points` key, so accessors written against the preview
iterate every point when they execute.

Both extremes were observed to fail live. **Dumping the whole series** overflows
the model's context on real windows (thousands of points ≈ tens of thousands of
tokens vs. the model's small default `num_ctx`), evicting the system prompt/rules
so the model replies with prose instead of code (`syntax_error@L1` plus
`missing_fixed_entry_point` / leading-zero partial-truncation variants), with
repair unable to recover. **A pure summary with no real points** is the opposite
failure: with nothing concrete to anchor on, the floor model (gemma4:e4b) drifts
to plotting/labeling off the `chart_spec` — which carries a planner-guessed unit
and no top-level `entity_id` — producing EMPTY plots with wrong units (measured
~2/3 of generations; a bounded preview of ≥6 points restored full grounding in a
live experiment; the default is 12 for margin). Renaming the preview key away from
`points` (a 0.2.18 `sample_points`) is also unsafe: the model binds to a key
absent at runtime → `KeyError` / empty plot. The prompt rules make `history_series`
the sole data authority (plot every series by iterating it directly; the
`chart_spec` is intent-only — never read data, units, or the series list from it).
The codegen `/api/chat` options also set an explicit `num_ctx` as defense-in-depth.
Only the prompt view is downsampled; the dispatched `render_mode: "codegen"` render
request still carries the full points (that path is the runtime `data`).

**Authoritative series unit (planner cannot guess; catalog may be stale).** The
`PlannerResult` schema requires a `unit` on every series, but the planner prompt
never carries the real unit, so the model guesses (observed live: `°C` on `°F`
sensors). After planning, the integration overwrites each series' `unit` from the
authoritative catalog `unit_of_measurement` (`_apply_catalog_units`, keyed by
`source.entity_id`), so no model-guessed unit reaches either render path. The
catalog `unit_of_measurement` is itself snapshotted at build time, and a cloud
entity is often `unavailable` then (no unit attribute) — so the snapshot can be
`null` even though the entity now reports a unit, which surfaced live as an empty
axis label (`"Value ()"`). `_approved_catalog_items` therefore backfills a missing
unit from the entity's **live state** (`backfill_catalog_units_from_state`) before
it is used, for both the codegen `history_series.unit` the model reads and the
`_apply_catalog_units` overwrite; a unit the catalog already carries is never
overridden.

**State overlays are integration-precomputed bands (ADR-0033).** Shading when a
binary/categorical entity is active (e.g. when the AC was cooling/heating, from
`climate` `hvac_action`) is NOT left to the model — live it plotted the raw state
(`"cool"`) as a line on the value axis. The integration precomputes the shaded
bands (`_compute_overlay_bands`, reusing the Pillow renderer's attribute-aware
region logic) into the render request's `derived_intervals`
(`{start_ms, end_ms, color, label}` per band). Prompt rules: plot only
`kind == "numeric"` series as lines (never `binary_state` / `categorical_state`);
draw each `derived_intervals` band as `ax.axvspan(...)` behind the lines. The
overlay series stays in `history_series` (for grounding/answer) but is not plotted.

**Runtime overflow detection (safety net).** Even with the summary, a
pathological request (very many series) or a shrunk `num_ctx` / smaller model
could still overflow. Ollama truncates silently and reports `prompt_eval_count`
capped at exactly `num_ctx`, so `prompt_eval_count >= num_ctx` is a definitive
overflow signal (`_context_overflow`). The codegen generate/repair results carry
a `context_overflow` marker when detected; the orchestration then **short-circuits
the doomed repair loop** (the model never saw its instructions, and each repair
prompt is larger) and falls back to Pillow with the distinct
`codegen_context_overflow` reason instead of a misleading downstream
`syntax_error`. The card renders actionable guidance for that reason (raise the
codegen model's `num_ctx` / `OLLAMA_CONTEXT_LENGTH`, request fewer series, or use
a larger-context model/GPU — the time range is irrelevant since the prompt is a
per-series summary, not the points) and the fallback WARNING log carries the
`prompt_eval_count` / `num_ctx` numbers.

### 4. Output-modality intent (model-decided, deterministically validated)

`planner-result.schema.json` gains an optional additive `output_modality` signal
(`"chart"` | `"answer"` | `"both"`). The planner signals what the prompt wants;
the integration validates the signal against the render envelope. **Invariant #9
is intact:** modality sits *above* chart-family routing — whatever chart is
drawn, its family is still deterministically routed from entity kinds (ADR-0022).
**First-slice constraint (ADR-0031 D2):** every answer ships with a supporting
chart, so an absent/`answer` signal is normalized to `both`; answer-only (no
chart) is a later tranche behind its own decision and is out of scope here.

> **STATUS (ADR-0034, 2026-07-06): PARKED as redundant for this slice.** With
> the user's request disclosed directly to the codegen model (the §2 conduit),
> the model reads compute-vs-plot and answer-vs-chart from `user_request`
> itself; a separate planner-emitted modality signal is not needed to make the
> analysis layer fire. `output_modality` is not implemented. What ADR-0034 DID
> add on the planner side is a rule that **an analysis prompt over approved
> entities is satisfiable** — the planner returns `chart_spec_ready` with one
> series per input entity the analysis needs (generated code does the math),
> instead of refusing an analysis request as "not representable by an entity"
> (which live produced `clarification_needed` / `not_chart_spec_ready` for
> correlation and heatmap prompts). Revisit `output_modality` only if a future
> answer-only tranche needs the planner to suppress the chart.

### 5. Two-part quality validation + progressive-verification UX (ADR-0031 D8)

Execution success is not quality. Two complementary checks:

**(a) Deterministic answer-grounding check** (cheap, 100% reliable; gates the
FIRST display). Before the chart+answer is shown, the integration scans the
`answer_text` for degenerate markers — a stringified non-finite float (`nan` /
`inf` / `-inf` / `infinity`, whole-word) or an unfilled template placeholder
(`{…}`, an f-string that never evaluated) — **and independently of any claim**,
so a plain aggregate that emits an `answer_text` but no verdict claim (which
otherwise reaches the "no claims → pass" branch) is still guarded. It then
verifies the stated number **and** qualitative verdict against a reference
computation over the same normalized data. A degenerate answer routes through the
codegen repair loop (reusing the ADR-0030 machinery, the grounding failure as the
feedback signal), bounded by `max_codegen_repair_attempts`, and is **withheld**
on exhaustion (the chart still serves; the answer is suppressed rather than
showing "nan °F"). NOTE: `0.00` is deliberately NOT a degenerate marker — a
genuinely zero result (a delta of 0.00 °F) is a valid answer. Implemented
`grounding_nonfinite_answer` tripwire in `run_grounding_check` (0.2.33, after a
live-observed "…the average … was nan °F" served past the no-claims path).
**Inert-rule tolerance (0.2.40, (cc)):** a claim's `rule` is only meaningful in
service of a `verdict` — steps 5 (containment) and 6 (consistency) both gate on
`verdict is not None and rule is not None`. So `_check_claim` skips the step-1
`rule`-structure validation when `verdict is None`, treating a verdict-less
claim as value-only. This makes the check robust to the common shape where a
small model omits the verdict on a descriptive answer but leaves a vestigial
empty `rule: {"bands": []}` stub (which otherwise tripped
`grounding_claim_malformed`); the stated number is still recomputed and verified
at step 4. Pairs with the §2 prompt rule that scopes `verdict`+`rule` to band
judgments.

**(b) Capability-gated visual validator** (catches broken *pictures* — flat/empty
panels, single-point scatters, mislabeled axes — that no text check sees). Runs
**after** the first render is already on screen. It is gated on model capability:
the integration probes the configured validator model's Ollama `/api/show`
`capabilities` for `"vision"`; **default ON when supported**, silently skipped
otherwise (a coder model with no vision, e.g. `qwen2.5-coder:7b`, falls back to
the deterministic check alone). The validator uses a **structured checklist
prompt** (data-sufficiency / read every text element for nan-inf-contradictions /
does-it-answer-the-question), **not** "does this look right", and runs
`think:false` (thinking consumed the whole token budget and returned empty
otherwise). The **visual-repair loop reuses the codegen repair machinery** — the
feedback signal is the rendered image + the validator's critique instead of a
sandbox traceback.

**Configuration:** the validator model is `visual_validator_model` (the existing
config scaffold — `config_schema.py` / `config_flow.py`); when unset it defaults
to the codegen/planner model. A `max_visual_revise_attempts` option (int ≥ 0,
default 1) bounds the visual-repair loop.

**Progressive-verification UX (resolves the latency concern).** The two checks
run at different times so the user never just waits:

- `integration-job-snapshot.schema.json` gains an optional `verification_status`
  enum (`"verifying"` | `"revising"` | `"verified"`). The card treats
  `verifying` and `revising` as **non-terminal** and keeps polling
  `job/snapshot` (extends the ADR-0025 poll-until-terminal loop; the served-PNG
  URL already exists at first display). Note this is a *sub-state of a `complete`
  render*, not a new top-level `status` enum value — the top-level `status` enum
  is unchanged; `verification_status` rides alongside a served chart.
- On first valid render (deterministic check passed): the card shows the chart +
  answer immediately in a **provisionally-complete** state with a "Checking our
  work…" indicator, `verification_status: "verifying"`.
- **PASS** → `verification_status: "verified"`, indicator drops.
- **REVISE** → `verification_status: "revising"`, the card shows a user-facing
  message (*"Isolinear found something off with this chart — revising it now"*;
  the specific critique goes to diagnostics, not the user), the bounded
  visual-repair loop runs, and the chart re-renders in place.
- **Fail-soft:** if it never PASSes within `max_visual_revise_attempts`, surface
  the last render with a soft caveat — never an infinite loop, never a blank wait
  (consistent with ADR-0030's surfaced-never-silent posture).

**Accepted tradeoff (ADR-0031 D8):** optimistic rendering may briefly show a
chart that is then revised (a *visually* degenerate one — broken numbers are
already gated out by check (a)); the prominent "checking" indicator frames it as
provisional, preferred over a long blank wait.

### 6. Library additions (ADR-0031 D6)

Add to `worker/requirements.txt` and the sandbox import allowlist
(`worker/isolinear_worker/codegen_sandbox.py`), exact-match alongside
numpy/pandas:

- **`scipy`** (~110MB) — `scipy.stats`, `scipy.signal`, `scipy.optimize`.
- **`seaborn`** (~5MB) — rides existing matplotlib + pandas.

Both are pure-compute, no network / subprocess / import-or-runtime writes under
the `-I` sandbox. The worker image grows ~526MB → ~650MB. The in-container check
MUST prove `matplotlib` + `pandas` + `numpy` + `scipy` + `seaborn` all import
together under the **1024MB `RLIMIT_AS`** cap in the `-I` sandbox (the OpenBLAS
thread pins from `2bb2747` apply). Tier-2 libs (`statsmodels`, `scikit-learn`)
are **not** added here — they wait for a demanding eval prompt family (ADR-0031
D6).

**Addendum (2026-07-06):** the pure-plotting matplotlib submodules
`matplotlib.patches`, `matplotlib.lines`, `matplotlib.ticker`, and
`matplotlib.colors` are allowlisted exact-match alongside `matplotlib.dates` —
an under-specified-allowlist omission, not a loosening (same trust tier as
matplotlib itself; no I/O). Live-driven: the ADR-0033 legend rule's "e.g. a
Patch" hint steered every gemma generation to `import matplotlib.patches`,
which burned 1–2 repair attempts per render on `import_not_allowlisted` (and
would one-shot to the Pillow fallback at the default
`max_codegen_repair_attempts: 1`).

### 7. Tranche-1 transforms (ADR-0031 D5)

The "model-authored transforms" scope promised by ADR-0030 D4 lands as
generated-code capability (no closed transform enum — the model writes pandas):
**cross-sensor math + smoothing** — multi-sensor average, pairwise delta,
deviation-from-house-mean, rolling average, daily high/low resample. This is
enabled purely by (a) multi-entity disclosure crossing the data boundary (the
composition pipeline already resolves multi-entity sets — ADR-0028) and (b) the
libraries above; it is proven by eval prompts, not new integration code paths.
Time-of-day profiles, binary+numeric analytics, and rates/energy accumulation
are explicitly **later tranches** (ADR-0031 D5).

### What does NOT change

- The **sandbox security model** — import allowlist, `-I` isolation, audit hook,
  fixed output path, timeout, `resource` limits (invariant #3). scipy/seaborn
  only make already-governed imports *available*; the allowlist still gates
  generated code.
- **Entity allowlist enforcement (#1)**, schema-validation-first (#4),
  deterministic plan validation (#5), and **render-family routing (#9)** — all
  upstream and untouched. Modality sits above family routing.
- The **data boundary** — entity selection, allowlist enforcement, and history
  retrieval stay integration-side; the worker never queries HA (ADR-0012/0029).
- The **PNG artifact-serving pipeline** — the answer rides existing served
  artifacts; `answer_text` is additive metadata.
- The **Pillow fallback** — a fallback render carries no `answer_text` (the
  trusted Pillow renderer does not compute answers); the card shows the chart
  without an answer line, consistent with ADR-0030 surfaced fallback.

## Anchor artifact

The simplest concrete observable, built first: with codegen active and a
worker configured, the model generates a `render_chart` body that computes a
correlation over two approved sensors, **f-strings the coefficient into an
`answer_text`**, and returns it in the metadata dict; a locally-booted worker
(packet-2 `isolinear_worker.http_server` on an ephemeral port) renders the PNG,
and the integration serves the PNG **and** delivers `chart.answer_text` (e.g.
"The correlation coefficient is 0.42.") on the complete snapshot — inspectable on
disk (the PNG) and in the snapshot JSON (the answer). Built before the modality
signal, the validators, and the library-dependent transforms. (Dev-box `-I`
cannot import matplotlib — the documented packet-1 limitation — so the matplotlib
variant is `skipUnless`-gated exactly as the codegen path gates it, and a
non-matplotlib `render_chart` body carries the answer-channel proof in every
environment.)

## Implementation order

Concrete-first, in bounded packets:

1. **Answer channel (anchor).** `answer_text` passthrough in
   `_normalize_render_metadata`; the three additive schema fields (both copies);
   thread `answer_text` through the artifact + complete snapshot; card promotes
   the answer slot under the caption. Grounding instruction in the codegen
   prompt. Proof: the anchor artifact above.
2. **Timestamp normalization (D9).** Epoch-ms projection in the codegen
   request-view; regression-guard that the codegen path never sees a raw ISO
   `ts`. (Do early — it de-risks every downstream analysis eval.)
3. **Libraries (D6).** scipy + seaborn into `worker/requirements.txt` +
   allowlist; rebuild the image on CT103; in-container all-imports-under-cap
   proof (live, `tar | ssh`, per the worker-deploy memory — no rsync on CT103).
4. **Deterministic answer-grounding check (D8a).** Parse + reference-compute
   verification; repair-on-failure reusing the codegen loop; fail-soft.
5. **Output-modality signal (D4).** Additive `output_modality` on planner-result;
   validate + normalize to `both` for the first slice.
6. **Visual validator + progressive-verification UX (D8b).** `/api/show` vision
   probe; checklist prompt (`think:false`); `verification_status` snapshot field;
   card non-terminal `verifying`/`revising` handling + "checking" indicator;
   bounded visual-repair loop; fail-soft.
7. **Tranche-1 transforms (D5).** Eval-driven; no new integration path — extend
   the benchmark corpus (see Proof requirements).

## Proof requirements

1. Unit tests (new `tests/test_model_authored_analysis.py` + additions to the
   codegen-path and sandbox tests) green, covering: `answer_text` passthrough in
   `_normalize_render_metadata`; the three schema fields validate and are
   optional/back-compatible; `answer_text` reaches the complete snapshot;
   codegen timestamps are epoch-ms (never raw ISO); the grounding check catches
   `nan`/`inf`/`0.00`/placeholder + verdict-vs-number mismatch and drives a
   bounded repair then fail-soft; `output_modality` validates and normalizes to
   `both`; the vision probe gates the visual validator on/off; the
   visual-repair loop is bounded and fail-soft; `verification_status` transitions
   `verifying`→`verified` and `verifying`→`revising`→`verified`.
2. BDD scenarios in
   [bdd/model-authored-analysis/model-authored-analysis-bdd.md](../../bdd/model-authored-analysis/model-authored-analysis-bdd.md)
   pass; an evidence file with **raw** outputs is written at
   `bdd/model-authored-analysis/model-authored-analysis-evidence.md`.
3. **Local end-to-end proof:** extend `evals/codegen_generation_path.py` (or a
   sibling `evals/model_authored_analysis.py`) to boot the packet-2 worker
   in-process and drive generate→dispatch→answer to a real PNG **plus** a
   grounded `answer_text` (raw request/response captured, authorization
   redacted). No CT103 / remote host touched by the eval.
4. **Analysis proof gate (ADR-0031, extended benchmark).** Extend
   `evals/prompts/benchmark_prompts.json` + `evals/analysis_benchmark/` with an
   **answer-family** (grounded correlation / cross-sensor math / smoothing) with
   **answer-grounding checks** (stated number *and* verdict match a reference
   computation) and **scipy `signal`/`curve_fit`** prompts (still unproven per
   ADR-0031 Open). Real HA data stays gitignored (private).
5. **Live library proof:** the in-container import-under-cap check (req. 3 above)
   passes on CT103; the rebuilt image is retained.
6. Full `python3 -m pytest tests/` green (the matplotlib-in-`-I` dev-box skips
   stay skipped locally); schema byte-parity + bundle sync green; architecture
   review OK; BDD-evidence review OK.

## Non-goals

- **Answer-only responses (no chart)** — first slice always ships chart + answer
  (ADR-0031 D2); answer-only is a later tranche behind its own schema decision.
- **TTS / spoken answers** — deferred (ADR-0031 D7; HA TTS collides with
  invariant #2).
- **Tier-2 libraries** (`statsmodels`, `scikit-learn`) — added only when a
  demanding eval prompt family requires them (ADR-0031 D6).
- **Later transform tranches** — time-of-day profiles, binary+numeric analytics,
  rates/energy accumulation (ADR-0031 D5).
- **Conversational refinement + saved live-refresh cards** — STATUS open-queue
  (l), future ADR(s) riding this one.
- Any change to the **sandbox security model**, the worker transport/auth/health
  contracts, or the entity-allowlist / render-family-routing boundaries.
- **Alignment/resample policy** — the benchmark's same-question answer drift
  (0.34 vs 0.66 correlation) traces to differing resample choices; a prescribed
  resample interval or a range-tolerant grounding check is an open spec-level
  item (ADR-0031 Open) carried alongside, refined as the answer-family eval lands.

## References

- ADR-0031 — model-authored analysis (decisions 1–9)
- ADR-0030 — codegen primary render path; pandas; repair-everything
- ADR-0029 — worker revival, data boundary, repair loop
- ADR-0027 — model-authored summary / card caption slot (the answer's UI lineage)
- ADR-0022 — deterministic render-family routing (invariant #9)
- ADR-0012 — worker transport + data boundary
- [codegen-generation-path.md](codegen-generation-path.md) — the render path extended
- `worker/isolinear_worker/codegen_sandbox.py` — `_normalize_render_metadata` (answer passthrough)
- `custom_components/isolinear/model_provider.py` — codegen prompt + vision probe
- `custom_components/isolinear/job_orchestration.py` — request projection, grounding check, validators
- `evals/analysis_benchmark/` — the ADR-0031 benchmark whose evidence backs D6/D8/D9
- `visual_validator_model` — the config scaffold the visual validator activates
