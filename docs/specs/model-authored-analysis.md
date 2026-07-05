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

### 2. Codegen prompt extension (grounding instruction)

`generate_chart_code` / `repair_chart_code` (model_provider.py) gain a grounding
instruction in the system prompt when the resolved output modality includes an
answer: emit `answer_text` in the returned metadata dict, assembled from computed
variables, with **verdicts computed, not asserted** (compute `"Yes"/"No"` from a
threshold over a computed value; never write the judgment before the computation
runs). The generation request already carries only the validated ChartSpec + the
normalized render data (the ADR-0029/0030 data boundary; no token or secret ever
enters the prompt) — unchanged here.

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

**Prompt view vs. runtime data (context-window discipline).** The generation
and repair *prompts* MUST carry only a compact **summary** of each series —
`entity_id`/`kind`/`unit` and other series-level metadata, plus `point_count`,
`ts_epoch_ms_range`, `value_stats` (numeric series) or `distinct_states`
(binary/categorical state series, capped — ADR-0022), and a few `sample_points`
showing the point dict keys — **never the full point list**
(`_history_series_prompt_view`). The
model authors code against a schema; the COMPLETE points are delivered to
`render_chart(data, output_path)` at runtime in the sandbox, so the code
iterates every point when it executes. Dumping the whole series into the prompt
overflows the model's context on real windows (thousands of points ≈ tens of
thousands of tokens vs. the model's small default `num_ctx`), which evicts the
system prompt/rules and makes the model reply with a prose description instead of
code — observed live as `syntax_error@L1` plus `missing_fixed_entry_point` /
leading-zero partial-truncation variants, with repair unable to recover (the
repair prompt is even larger). The codegen `/api/chat` options also set an
explicit `num_ctx` as defense-in-depth. Only the prompt view is summarized; the
dispatched `render_mode: "codegen"` render request still carries the full points
(that path is the runtime `data`).

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

### 5. Two-part quality validation + progressive-verification UX (ADR-0031 D8)

Execution success is not quality. Two complementary checks:

**(a) Deterministic answer-grounding check** (cheap, 100% reliable; gates the
FIRST display). Before the chart+answer is shown, the integration parses the
`answer_text` for degenerate markers (`nan` / `inf` / `0.00` / unfilled
placeholder braces) and verifies the stated number **and** qualitative verdict
against a reference computation over the same normalized data. A broken *number*
is caught before anything is shown; on failure the codegen repair loop is invoked
(reusing the ADR-0030 machinery, the grounding failure as the feedback signal),
bounded by `max_codegen_repair_attempts`, then fail-soft.

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
