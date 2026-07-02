---
id: 0031
title: Model-authored analysis — Isolinear answers questions, not just charts
status: draft
date: 2026-07-02
supersedes: []
superseded-by: null
tags:
  - product-direction
  - analysis
  - codegen
  - worker
  - sandbox
  - model-empowerment
---

# ADR-0031: Model-authored analysis — Isolinear answers questions, not just charts

## Context

ADR-0030 made sandboxed matplotlib codegen the primary render path and put
pandas in the worker image so the model could transform timeseries in generated
code. That unlocked more than transforms. The packet-5 reliability eval showed
`gemma4:e4b` reaching for pandas unprompted, and pandas + open-ended sandboxed
codegen together put the original product vision in reach: a **plain-language
data analyst for the house**.

The recurring user experience this targets: a one-off question about the home
("how much heat seeps from the attic into the family room on a hot day?") today
means opening HA's history panel, picking a couple of entities, and squinting at
non-overlapping plots — because building a Grafana dashboard is not worth the
effort for a one-off. The user wants to ask the question in plain language and
get a **data-supported answer**, usually with a supporting visualization. For
many such questions the natural primary output is a *sentence with a computed
number in it*, not an image: "Are the upstairs and downstairs temperatures
correlated?" → "Yes — the correlation coefficient is 0.42."

The pieces are already in place: the sandbox runner already returns a metadata
dict from `render_chart(data, output_path)` alongside the PNG (the answer is
one field away — no sandbox change); the card already renders model-authored
text (`chart_spec.summary` became the caption in ADR-0027); the repair loop and
the trust model for generated code shipped with ADR-0029/0030.

## Decision

1. **Isolinear answers questions about approved sensor data in natural
   language, computed by the worker.** The product identity expands from
   "visualization assistant" to data-analysis assistant; a chart and a textual
   answer are two output modalities of one analysis pipeline. (The `CLAUDE.md`
   / `AGENTS.md` identity line updates when this ADR is accepted.)

2. **First slice: every answer ships with a supporting chart.** `answer_text`
   is purely additive — an optional field on render-result / artifact-metadata
   / job-snapshot — and the PNG artifact pipeline is untouched. Answer-only
   responses (no chart) are a later tranche behind their own schema decision.

3. **Grounding principle (load-bearing): the generated code computes AND
   formats the answer.** The model authors the natural-language sentence with
   **placeholders** for data-derived parts; the sentence is assembled *inside
   the sandbox at execution time* from computed variables (an f-string/`.format`
   over e.g. a `df.corr()` result), so those parts cannot be hallucinated —
   they are the computation. The answer is **never** produced by a second
   free-text model pass over the raw data.

   The guarantee extends past the raw number to **any claim contingent on the
   data — including qualitative verdicts.** A placeholder grounds
   `{corr:.2f}`; it does not ground the word "Yes" in
   `f"Yes — they're correlated (r={corr:.2f})"` if the model asserted "Yes" at
   generation time before seeing the data (it could print an honest `0.04`
   under a false "Yes"). So the rule is: **every part of the sentence that is a
   claim about the data — number or judgment — comes from a computed variable
   (`verdict = "Yes" if abs(corr) > 0.3 else "Not really"`); the model's
   free-text is limited to framing true regardless of the data** ("The
   correlation coefficient is…", "Over the last 24 hours…").

   This is **enforced by the prompt, not structurally** (resolved with the
   human, 2026-07-02): the codegen prompt instructs the model to compute its
   verdicts, and the grounding-check eval is the deterministic backstop
   (compare stated claims against a reference computation). We deliberately do
   **not** split the sentence into separate number+label metadata fields
   assembled integration-side — that would drag back the closed-vocabulary
   rigidity ADR-0030 just removed, and it over-invests in protecting against
   sub-baseline model incompetence (see Rationale: capability floor). The
   model's failure mode is choosing a wrong approach — exactly the trust level
   charts already have, covered by the same static checks, sandbox, repair
   loop, and (future) validation.

4. **Output-modality intent is model-decided, deterministically validated.**
   The planner signals whether a prompt wants a picture, an answer, or both;
   the integration validates the signal against the envelope. Invariant #9 is
   intact: modality sits *above* chart-family routing — whatever chart is
   drawn, its family is still deterministically routed from entity kinds.

5. **The transforms scope merges into this ADR.** The "model-authored
   transforms" follow-up spec promised by ADR-0030 decision 4 becomes tranche 1
   of the shared compute layer here: **cross-sensor math + smoothing** —
   multi-sensor average, pairwise delta, deviation-from-house-mean, rolling
   average, daily high/low resample. (Time-of-day profiles, binary+numeric
   analytics, and rates/energy accumulation are explicitly later tranches.)

6. **The analysis library allowlist expands — under a selection principle.**
   A library is allowlisted when it is (a) **saturated in model training data**
   (a local model must already speak it fluently; nobody teaches it new APIs in
   a system prompt), (b) **pure compute** — no network, no subprocess, no
   writes at import or runtime under the `-I` sandbox, and (c) **genuinely new
   capability**, not expressible in a few lines of what is already present.
   Applying the principle now:
   - **Add: `scipy`** (~110MB) — `scipy.stats` (correlation with p-values,
     regression), `scipy.signal` (cross-correlation lag — the attic→family-room
     question is literally this computation — and `find_peaks`), and
     `scipy.optimize.curve_fit` (thermal time constants from cooling curves).
   - **Add: `seaborn`** (~5MB, rides existing matplotlib+pandas) — statistical
     visualization vocabulary the models reach for naturally (`sns.heatmap` for
     day×hour pivots, regression plots as the visual companion to correlation
     answers). Cheap insurance against import-gate repair loops.
   - Already present: `numpy` (allowlisted since `03fa792`; OpenBLAS thread
     pins from `2bb2747` apply).
   - **Tier 2 (named, demand-driven — add when an eval prompt family requires
     them):** `statsmodels` (seasonal decomposition) and `scikit-learn`
     (clustering/anomaly; note its joblib parallelism can attempt subprocess
     spawns the audit hook rightly denies — `n_jobs` friction is a repairable
     failure, and a reason to wait for demand).
   - **Rejected:** `plotly` (native output is interactive HTML; static export
     drags in kaleido/Chromium — the output contract is a PNG), `prophet`
     (compiles Stan models; enormous; wrong tool for one-off questions),
     `duckdb` (redundant with pandas), niche timeseries libs (fail the
     model-familiarity test, which is the actual bottleneck).

7. **TTS is deferred, with the fork recorded.** Card-side browser speech
   synthesis is read-only-safe and available anytime; calling Home Assistant's
   TTS services is a service call and collides with the MVP read-only posture
   (invariant #2). Speaking answers is its own future decision.

## Rationale

- **The grounding principle is what makes this safe to ship.** A model
  paraphrasing raw data hallucinates numbers; code that computes a value and
  f-strings it into a sentence cannot misquote its own result. This confines
  model risk to approach selection — the identical risk profile the packet-5
  eval already measured at ~94% accept-with-repair for charts.
- **Capability-floor assumption (shapes how much guardrail is worth building).**
  `gemma4:e4b` — the smallest model in the packet-5 eval, running on Colin's
  RTX 3060 — is treated as the **baseline**: every deployment is assumed to run
  that or something better (a larger local model, or a cloud model that is
  dramatically more capable). Effort spent structurally protecting the pipeline
  against *sub-baseline* model incompetence is therefore misplaced — it buys
  safety for a configuration that does not exist while re-introducing rigidity
  the project has been removing. This is the explicit reason grounding is
  enforced by prompt + eval backstop (decision 3) rather than by structural
  decomposition, and it generalizes: prefer prompt guidance + a deterministic
  backstop over hard-coded scaffolding whenever the baseline model can already
  do the thing.
- **The wire distance is short.** The runner's metadata return channel already
  exists (no sandbox change, no new entry point, no security-model change);
  the ADR-0027 caption slot already renders model-authored text; `answer_text`
  is additive everywhere it appears.
- **Model familiarity is the real capability bottleneck**, not image size —
  gemma reached for pandas because pandas saturates its training data. The
  library principle encodes that observation so future additions stay
  demand-driven instead of speculative (invariant #8's no-speculative-
  generality, applied to dependencies).
- **Answer quality lives on two axes: library breadth and data breadth.** The
  spec must treat multi-entity disclosure (how many series, at what
  resolution, cross the data boundary) as first-class scope — an analyst asked
  to compare all upstairs rooms needs all upstairs rooms. The composition
  pipeline already resolves multi-entity sets; the codegen disclosure inherits
  it. The data boundary itself is unchanged: entity selection, allowlist
  enforcement, and history retrieval stay integration-side; the worker never
  queries HA (ADR-0012/0029).
- Deterministic-envelope precedent: ADR-0022/0023/0024/0028 all moved judgment
  into the model inside deterministic validation envelopes; decision 4 is the
  same shape applied to output modality.

## Consequences

**Enables:**
- One-off analyst questions with grounded numeric answers + charts
  (correlation, lag, rates, cross-sensor comparisons) — no dashboard-building.
- Day×hour heatmaps and regression/distribution plots via seaborn.
- The saved-live-visualization stub (open queue (l)): a saved card's answer
  channel refreshes for free — live-updating computed numbers, not just PNGs.
- TTS later without rework (the answer is already text).

**Constrains:**
- The answer is never a free-text model pass over data — grounding is
  non-negotiable (this is the analysis counterpart of invariant #1's "never a
  silent guess").
- First slice always produces chart + answer; answer-only needs a new decision.
- Library additions must pass the three-part selection principle; tier-2 libs
  wait for a demanding eval prompt family.
- Worker image grows ~526MB → ~650MB (scipy + seaborn); the in-container check
  must prove matplotlib+pandas+numpy+scipy+seaborn all import together under
  the 1024MB `RLIMIT_AS` cap in the `-I` sandbox.

**Open:**
- Answer length/format policy (one sentence? capped chars? units handling) —
  spec-level.
- Multi-entity disclosure breadth: how many entities / what resolution crosses
  the boundary for "compare all upstairs rooms"-class prompts — spec-level,
  with a resource ceiling.
- scipy codegen reliability is unproven: gemma self-rates scipy "Advanced"
  (its only non-expert self-rating) — the eval corpus must exercise
  scipy-requiring prompts (lag correlation, curve_fit, find_peaks) so
  accept/repair rates decide, as packet 5 did for matplotlib.
- Grounding-check eval design (enforcement backstop resolved to prompt + eval,
  decision 3): assert not only that the stated **number** matches a reference
  computation, but that the **qualitative verdict** is consistent with it (an
  honest number under a false "Yes" must be caught) — not just that the code
  ran. How to check a free-text verdict deterministically is the open part.
- The answer-only tranche trigger and its schema surface.

## References

- ADR-0030 — codegen primary; model-authored transforms (decision 4 lands here)
- ADR-0029 — worker revival, data boundary, repair loop
- ADR-0027 — model-authored summary / card caption slot (the answer's UI lineage)
- ADR-0022 / 0023 / 0024 / 0028 — deterministic-envelope precedents
- ADR-0012 — worker transport + data boundary
- Spec (to be drafted with this ADR): `docs/specs/model-authored-analysis.md`
  + paired BDD
- `STATUS.md` open queue (l) — conversational refinement + saved live
  visualizations (future ADR(s) that ride this one)
- `evals/prompts/benchmark_prompts.json` — to be extended with answer-family +
  grounding-check prompts
