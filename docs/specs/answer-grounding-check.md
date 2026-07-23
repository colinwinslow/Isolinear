---
status: accepted
date: 2026-07-03
depends-on-adrs: [0031, 0030, 0029, 0022, 0008, 0006, 0005]
---

# Answer grounding check: deterministic verdict verification via a claims ledger

## Status

Accepted (human-ratified 2026-07-03). Defines the contract surface for the
**deterministic answer-grounding check** — ADR-0031 D8a, the open verdict half —
resolving the ADR's explicitly-Open "how to check a free-text verdict
deterministically" item inside the frame D3 fixed. Supersedes nothing. The full
design rationale, alternatives, and D3 reconciliation live in the research note
[docs/research/answer-verdict-grounding-check.md](../../docs/research/answer-verdict-grounding-check.md);
this spec is the implementable contract distilled from it. Implementation is
[model-authored-analysis.md](model-authored-analysis.md) packet 4 (which this
spec expands into sub-packets — see Implementation order).

## Related docs

- [bdd/answer-grounding-check/answer-grounding-check-bdd.md](../../bdd/answer-grounding-check/answer-grounding-check-bdd.md) — observable behavior
- [docs/research/answer-verdict-grounding-check.md](../../docs/research/answer-verdict-grounding-check.md) — full design rationale + alternatives + D3 reconciliation
- [model-authored-analysis.md](model-authored-analysis.md) — the answer channel this checks (packet 4 = §5(a))
- ADR-0031 — model-authored analysis (D3 grounding principle; D8a two-part validation)
- ADR-0022 — deterministic render-family routing (the crisp raw-state transition class anchors reuse)
- [STATUS.md](../../STATUS.md) — current phase and active work

## Context

Isolinear answers questions with a grounded sentence computed in the sandbox
(model-authored-analysis packets 1–2). D8a mandates a deterministic backstop that
verifies the stated number **and** the qualitative verdict. The number half is
mechanical (extract, recompute a reference, compare within tolerance, flag
`nan`/`inf`/`0.00`/unfilled braces). The **verdict half is the open problem**: an
honest number can ride a false verdict — `"Yes — they're correlated (r=0.04)"` —
because the model asserted "Yes" at generation time, before the data existed.
Free text is not deterministically parseable, and D3 forbids the obvious fix
(splitting the sentence into number+label fields assembled integration-side —
closed-vocabulary rigidity; capability-floor rationale).

The load-bearing insight (research note): the real bottleneck is **recompute
fidelity** — to check any numeric claim the integration must independently
reproduce the model's number, which needs the exact window, params, and event
boundary. Correlation hides this by being parameter-free. The solution carries
the full recompute recipe in a machine-readable record used **only for checking,
never for display**.

## Behavior contract

### 1. The claims ledger (the record)

The metadata dict returned by `render_chart` MAY carry one new optional key,
`claims` (a list), riding the existing metadata channel like `answer_text` (no
new boundary, no sandbox change). **The record is used ONLY for verification,
never for display: no display path reads a claim; deleting the ledger leaves the
user-visible output byte-identical.** That is the line between *checking* (this
design) and *assembly* (what D3 rejects) — the ledger is to the answer what the
PNG is to the visual validator, an artifact reviewed not composed.

A claim is `{metric, inputs, window?, params?, value, verdict?, rule?}` — the
**full recompute recipe**, not just a metric name:

- **`metric`** — free string. Registry membership decides *verifiability*, never
  *expressibility* (D3). Parameter-free metrics (e.g. `pearson_r` over the full
  delivered series) may omit `window`/`params`.
- **`inputs`** — entity ids; must be among the job's delivered series.
- **`window`** — required for any windowed registry metric; two forms:
  - *absolute*: `{start, end}` epoch-ms UTC, half-open — the same currency the
    ADR-0031 D9 boundary already hands the model, so "yesterday" is resolved to
    absolute bounds at codegen time (as it already must be to slice the frame).
  - *anchored*: `{anchor, direction: "after"|"before", duration_ms}` — resolved
    to absolute bounds by event re-detection (§1a).
  - The window must lie within the delivered data span; outside → unverifiable
    (caveat), never guessed-at clipping.
- **`params`** — flat dict of JSON scalars in input-data units; free-string keys;
  the **registry** declares the required params per metric (`hours_above` →
  `threshold`; `rolling_mean` → `window_ms`). Missing required param = incomplete.
- **`value`, `verdict`, `rule`** — `value` and `verdict` are the SAME variables
  formatted into the sentence (execution-time truth, not generation-time
  assertion). `rule.bands` is an ordered `[min_threshold, label]` list,
  descending, last threshold `null` (catch-all); `rule.basis` is `"abs"|"value"`.
  Labels are free strings the model invents (no enum). No formatted-string field —
  number-in-sentence verification stays the number half's job.

### 1a. Event anchors — reproducibility criteria

An anchor (inside an anchored window):
`{entity, attribute (None=state), to, from?, occurrence, search:{start,end}, resolved_at}`.
It is **deterministically reproducible iff ALL of**:

1. `entity` is among the job's delivered input series (re-detect from data held;
   no new fetch — the check stays synchronous and gates first display).
2. The event is a **crisp discrete transition** — exact string equality of `to`
   (and `from`, if given) on the normalized raw-state timeline (the ADR-0022
   binary/climate/categorical raw-state class). No fuzzy matching.
3. `occurrence` (1-based; negative from end) + absolute `search` bounds select a
   **unique index** into the finite ordered transition list — same index on both
   sides, no guessing.
4. `resolved_at` lets the check confirm the *same* event (identity, not just
   existence).

Explicitly NOT reproducible → unverified caveat by construction, never attempted:
analog threshold-crossings as anchors (alignment-sensitive; deferrable), rate/
shape conditions ("cooling fast"), anchors on out-of-set entities, anchors
missing `search`/`occurrence`.

### 2. Codegen prompt extension

Extend `_CODEGEN_PROMPT_RULES` (model_provider.py): when `answer_text` makes a
qualitative judgment, the code must compute the judgment from a variable via an
explicit threshold `rule` and ALSO return a `claims` list recording the full
recipe (`metric, inputs, window, params, value, verdict, rule`; anchor when the
analysis is event-scoped), where `value`/`verdict` are the SAME variables
formatted into the sentence and band labels are not substrings of one another.
Cost at the capability floor is a dict literal over variables the code already
bound. **Failure to emit is fail-soft (§4), never a hard gate.**

### 3. The deterministic check

Runs in `job_orchestration.py` inside `_record_codegen_worker_dispatch`, on the
success branch **before** the artifact is served (so it gates first display, D8
progressive verification). A failure is routed into the existing repair branch as
a synthetic sandbox-shaped error (`code: "grounding_check_failed"`, details carry
the claim + reference + expected label) so `repair_chart_code` consumes it
through its existing signature — the grounding failure IS the repair feedback.
Shared budget `max_codegen_repair_attempts`; **no new config knobs.** Per claim,
in order:

1. **Structure** — malformed claim / bands overlapping/empty/no-catch-all →
   `grounding_claim_malformed` (repairable).
2. **Recipe completeness** — registry metric missing a required `window`/`param`,
   or window outside the delivered span → `grounding_recipe_incomplete` (one
   repair; then unverified caveat — bookkeeping, not false-verdict evidence).
   `metric ∉ registry` → skip to step 5 (unverifiable; internal consistency only).
3. **Degeneracy** — non-finite `value` → fail (the `nan`-in-sentence class).
4. **Anchor + reference recompute** — anchored window: anchor fails §1a →
   unverifiable (caveat); criteria met → re-detect the transition; none found →
   `grounding_anchor_unfound` (contradicted; repairable); re-detected ≠
   `resolved_at` → `grounding_anchor_mismatch` (contradicted). Then recompute the
   metric over the claim's window+params with the integration-prescribed
   alignment; `|value − reference|` outside tolerance → `grounding_value_mismatch`.
5. **Verdict containment** — casefold + word-boundary match every band label
   against `answer_text`; the **longest match** is the effective verdict
   (negation-safe: "not correlated" beats "correlated"). None →
   `grounding_verdict_absent`; effective ≠ claim `verdict` →
   `grounding_verdict_ambiguous`.
6. **Verdict consistency** — apply `rule` to the check value (reference when
   available, else recorded `value`) → expected label; expected ≠ claimed verdict
   → `grounding_verdict_contradicted`. **Boundary rule:** evaluate bands at check
   value ± tolerance; if labels differ across that span the claim passes as
   *borderline* (diagnostics note, never a flap-fail).

**Sentence tripwire** (the only free-text parsing, precision-over-recall):
`answer_text` beginning `^\s*(yes|no)\b` with no claim carrying a `verdict` →
`grounding_verdict_unbacked` (one repair, then caveat). No broader lexicon.

### 3a. The verified boundary — three states

`verified` ⇔ `metric ∈ registry` ∧ recipe complete and reproducible ∧ recompute
matches within tolerance ∧ verdict consistent with the rule at the reference.

| State | Meaning | Lands here |
|---|---|---|
| **verified** | Value independently reproduced from allowlisted data; verdict follows the declared rule at the reference | Full pass of steps 1–6 with a registry recompute |
| **unverified-caveat** | Nothing contradicted, but nobody reproduced the value | Metric ∉ registry; fuzzy/curve_fit analysis (surfaces as an unregistered metric); recipe incomplete after repair; window outside span; anchor irreproducible by construction |
| **contradicted** | Positive evidence of inconsistency | Reference mismatch; `anchor_unfound`/`anchor_mismatch`; verdict ≠ rule; non-finite value; verdict absent/ambiguous vs the record |

**Assignment rule: contradicted requires positive evidence; inability to check is
never contradiction.** Unregistered metrics and fuzzy segmentation mean the model
did nothing wrong — caveat, never repair-then-withhold.

### 3b. The guarantee, stated plainly (first-class contract text)

A **two-tier guarantee**, stated verbatim in the spec, the card caveat copy, and
diagnostics — never letting the correlation case advertise for the whole feature:

- **Inside the verified boundary — value↔data.** The integration independently
  recomputed the number from allowlisted history using the claim's own recipe;
  the verdict provably follows from the declared rule at that reference.
- **Outside the boundary — internal consistency only** (value↔verdict↔rule). The
  verdict matches the value the code **claims** to have computed, under the rule
  it **claims** to have used; nobody reproduced that value. Still catches: a
  verdict contradicting the claim's own recorded value, degenerate values, and
  record-vs-sentence divergence. **Cannot** catch a fabricated value paired with
  a matching verdict.

The "unverified" caveat means **"not independently reproduced," not "probably
fine."** Card copy says so plainly. Outside the boundary the system caveats
rather than trusts; the boundary (the registry) is explicit, auditable, and
demand-grown.

### 4. Fail-soft policy

| Outcome | First remedy | After repair exhaustion |
|---|---|---|
| Contradicted (`verdict_contradicted`, `value_mismatch`, `anchor_unfound`, `anchor_mismatch`, non-finite, `verdict_ambiguous`) | Repair via the shared codegen loop (grounding failure as feedback) | **Withhold `answer_text`** — serve the chart with a "couldn't produce a verifiable answer" note (chart-without-answer is already legal — the Pillow fallback ships it) |
| Unbacked (tripwire) / malformed claim / incomplete recipe on a registry metric | One repair requesting a well-formed claim/recipe | Show the answer with the "unverified" caveat |
| Unverifiable (metric ∉ registry; window outside span; anchor irreproducible; internal consistency passed) | None — the model did nothing wrong | Show with the "unverified" caveat |
| Borderline (within tolerance of a band edge) | None — pass, diagnostics note | — |
| No claims, no tripwire, number check green | Pass | — |

**Never strip or rewrite the verdict.** Editing model prose is assembly by
another name (D3) and risks garbling. The only integration verbs: show as-is,
show with a caveat rendered as a **separate UI element** (never spliced into
`answer_text`), or withhold the whole sentence.

### 5. The metric registry

The integration owns a registry mapping `metric` → (recompute implementation over
normalized history, required params). It is shared with the number half's
reference computation. Initial membership = the tranche-1 transform set (§6);
growth is demand-driven, and each addition must satisfy §1a-grade reproducibility
before admission. An unknown metric is `unverified-caveat`, never an error.

**Multi-input `mean` (cross-sensor, 2026-07-14, live-driven — e2e-11 root cause):**
a claim may declare more than one input (`"the average of the kitchen and basement
temperatures"` → `inputs=[kitchen, basement]`). The `mean` recompute for `len(inputs)
> 1` averages **across** the inputs on a shared time grid — resample each input to
5-minute buckets with interior interpolation and keep only buckets present in every
input (`dropna`), then average across inputs per bucket and mean over the grid. This
faithfully mirrors ADR-0036 `isolinear_analysis.align(...).mean(axis=1).mean()` (the
aligned frame the model plots), reproduced in pure Python — grounding stays a
drift-detector, independent of the sandbox helper, verified to 6 decimals against
`align()` on live and synthetic data. Rationale: the prior recompute averaged only
`inputs[0]`, so a correct two-sensor answer could never match the single-sensor
reference within tolerance and the answer was withheld (chart served, `answer_text`
empty). Disjoint coverage (no common bucket) → no reference → `unverified-caveat`,
never a false contradiction. `daily_max`/`daily_min` remain single-input
(`inputs[0]`); a multi-input need there is a future demand-driven extension.
(Multi-input `delta` was that extension — landed 2026-07-20, below.)

**Multi-input `delta` (cross-sensor, 2026-07-20, live-driven — e2e-08):** the
demand this section anticipated arrived. "Compare the kitchen and basement
humidity" is answered with the **average difference between** the two sensors,
computed off the ADR-0036 aligned frame (`(frame[a] - frame[b]).mean()`), while
the recompute returned last-minus-first of `inputs[0]` — a different quantity
entirely (live humidity data: 4.00 against a true 4.63), so a correct two-sensor
answer could never verify. For exactly two inputs the reference now resamples
each onto the shared 5-minute grid, takes the per-bucket difference in
`inputs` order, and means it — mirroring `align()` in pure Python, verified to 4
decimals against real pandas `align()` on live data (4.6387). Single-input
`delta` is unchanged (last − first, change *over time* within one series).

**Three or more inputs return no reference** — a multi-way difference has no
well-defined ordering, and a guessed one could falsely contradict a correct
answer (the failure mode the (cc)/(ff) bugs taught us to fear).

`delta` is the first **order-sensitive** multi-input metric (`mean` and
`pearson_r` are both symmetric) and the first where the claim's inputs are
routinely a SUBSET of the delivered series, so it carries two false-contradiction
hazards the prior two fixes did not. The architecture review reproduced both, and
the prompt rule alone does not cover them — a floor model that is internally
inconsistent (subtracts `b - a` while listing `inputs` in the other order) or
that builds its own frame instead of calling the prescribed helper would have a
CORRECT answer withheld. So the recompute is defensive as well as faithful:

- **Two reference grids are computed, most-faithful first.** The prompt
  prescribes `align(data['history_series'])`, whose `dropna` spans EVERY
  delivered numeric column — so when a third numeric series is delivered, the
  model's frame is narrower than the two claim inputs alone, and
  mean-of-differences is *not* invariant across row sets (measured on live data:
  5.40 on the all-series grid vs 4.65 on the inputs-only grid, a 15× tolerance
  gap). Both readings are legitimate; a value matching EITHER verifies.
- **A sign-only disagreement is a caveat, not a contradiction.** If the stated
  value matches a reference in magnitude but not sign, the answer is served with
  `grounding_delta_sign_ambiguous` rather than withheld. Serving a possibly
  back-to-front direction with a caveat beats suppressing a correct magnitude.

A value matching no candidate grid in magnitude still contradicts, so step 4
remains load-bearing (pinned by
`TestCrossSensorDeltaFalseContradictionGuards::test_wrong_value_still_contradicts_despite_guards`).
No grid overlap → no reference → `unverified-caveat`, never a false contradiction.

**Deliberate reinterpretation:** a two-input `delta` claim now *always* means the
cross-sensor difference. A hypothetical old-shape claim that used two inputs to
mean "change over time of `inputs[0]`" would now be caveated or contradicted.
That shape was never emitted in any observed run, and the prompt rule now names
the cross-sensor reading explicitly, so the ambiguity is closed by contract
rather than guessed at per-claim.

**`rolling_mean` needs no align-grid change (negative result, same session).**
The packet was scoped to fix `delta` *and* `rolling_mean` alignment, but
measurement on real data retired the second half: the raw-point rolling
recompute (73.29) and every aligned-grid variant (73.28–73.31 across 30- and
60-minute windows) agree well inside the 0.05 tolerance, because averaging a
rolling average over a window is insensitive to the resampling basis. The real
obstacle for `rolling_mean` is the registry-required `window_ms` param: absent
it, there is no reference at all regardless of algorithm. That is addressed on
the emission side (the prompt asks for `params.window_ms` whenever a numeric
rolling value is stated) rather than by changing this recompute.

_Reconfirmed 2026-07-23 (0.2.47):_ a live repro of the cross-sensor case ("the
average of X and Y smoothed with a rolling average") showed the model does not
emit `rolling_mean` at all — it reports the mean OF a rolling average under a
`{'metric': 'mean'}` claim, a window-dependent quantity ~0.11 °F off the plain
mean, which `_compute_mean` correctly WITHHELD. The fix is again purely on the
emission side (pin the stated average to the raw aligned frame, not the smoothed
series — see `docs/specs/model-authored-analysis.md`); this recompute is unchanged
and the `rolling_mean` negative result above still stands.

**`pearson_r` on the shared grid (2026-07-16, live-driven — open-queue (ff)):**
the same alignment reasoning applies to correlation. Two sensors read by separate
integrations share **no** raw timestamps, so the prior recompute — which paired
values on the exact-timestamp intersection (`set(map_a) & set(map_b)`) — found an
empty intersection on real recorder data and returned no reference. A correctly
computed correlation (the model does `isolinear_analysis.align(...).corr()`) could
therefore only ever be served as an `unverified-caveat`, never verified — the
correlation analog of the multi-input `mean` bug. The `pearson_r` recompute now
resamples each input onto the same 5-minute grid (interior interpolation), pairs
the values on buckets present in **both**, and computes Pearson r over those pairs,
mirroring `align().corr().iloc[0, 1]` in pure Python (verified to ~12 decimals
against the model's aligned value on synthetic data). Fewer than 3 shared buckets →
no reference → `unverified-caveat`, never a false contradiction.

### 6. Tranche-1 scope (conscious restriction, not a silent gap)

First-slice answer-bearing verification covers **reproducible, registry-covered,
parameter-light metrics** ≈ the tranche-1 transform set: `mean`, `delta`,
`pearson_r`, `rolling_mean`, `daily_max`/`daily_min` (+ `hours_above`-style
threshold counts if the eval corpus wants them). Inside this set every answer
carries the strong value↔data guarantee. **"Works in every context" is a stated
non-goal.** Deferred, explicitly: event-scoped answers (tranche 2 — the anchor
shape is designed now so the claim contract does not churn, but re-detection
ships later); causal/interpretive verdicts ("seeping") are accepted-residual
alongside threshold-gaming (the number is verified, the interpretive word is the
model's judgment); unregisterable analyses (curve_fit, fuzzy segmentation) are
unverified-caveat by construction.

### Schema surface (all additive, optional, back-compatible; both copies)

- `render-result.schema.json`: `render_metadata.claims` — optional array; claim
  objects nest `window`/`params`/`anchor`. Passed through
  `_normalize_render_metadata` like `answer_text`. Diagnostics, not display data.
  **Deviation (2026-07-06, live-driven):** the passthrough is no longer fully
  "unchanged" — `_coerce_claims` sanitizes each claim to the contract shape
  first (plainly-numeric string `value` converted, otherwise the claim is
  dropped; off-type optional fields removed; non-dict entries dropped). The
  schema requires `value: number|null`, and a model-stringified value (measured
  live in the proof-req-#4 benchmark) made the worker's own response validation
  raise as an HTTP 500 — an unrepairable transport fault to the integration. A
  dropped claim degrades to the unverified caveat downstream (inability to
  check is a caveat, never a fabricated value — the D3/three-state discipline
  is unchanged).
- `integration-job-snapshot.schema.json`: optional `chart.answer_verification`
  (`"verified"` | `"unverified"`) — the card's caveat-state hook; a withheld
  answer is simply an absent `answer_text`. Distinct from D8b's
  `verification_status` (the *visual* pass).

### What does NOT change

- The sandbox security model (#3), entity allowlist (#1), render-family routing
  (#9), the data boundary (worker never queries HA), the PNG pipeline. The check
  is integration-side over data it already holds.
- No new config knobs; repair reuses `max_codegen_repair_attempts`.
- The model still authors AND assembles the sentence in-sandbox (D3).

## Anchor artifact

The simplest concrete observable, built first: a seeded claim where the sentence
hard-codes `"Yes — they're correlated"` but the ledger's honest `pearson_r`
recompute over the same two series yields `r ≈ 0.04` under the model's declared
`rule` → the check flags `grounding_verdict_contradicted`, the shared repair loop
runs, and on exhaustion the answer is withheld (chart served, caveat surfaced) —
inspectable in the snapshot (`answer_text` absent, `answer_verification:
"unverified"`) and diagnostics (the contradiction record). Built before the
parametric/anchor paths.

## Implementation order

Sub-packets (concrete-first; extends model-authored-analysis packet 4):

1. **4a — number half + registry.** The metric registry (tranche-1 metrics +
   recompute impls over normalized history), the number check (extract stated
   numbers, recompute, tolerance, degeneracy flags), wired into
   `_record_codegen_worker_dispatch` before serve; repair-on-failure via the
   shared loop; fail-soft. Anchor artifact for the number path.
2. **4b — claims ledger + verdict check.** `render_metadata.claims` schema (both
   copies) + `_normalize_render_metadata` passthrough; the codegen prompt
   extension; the deterministic check steps 1–6 + tripwire; the three-state
   boundary; the seeded false-"Yes" anchor artifact.
3. **4c — surfacing.** `chart.answer_verification` schema + threading; the card
   caveat state + withheld-answer state with the two-tier-guarantee copy.
4. **4d — anchors (tranche 2, shape only if deferred).** Anchor re-detection over
   delivered raw-state series per §1a; `anchor_unfound`/`anchor_mismatch`. May
   ship later; the claim shape is fixed now so the contract does not churn.

## Proof requirements

1. Unit tests green covering: the seeded false-"Yes" caught end-to-end (verdict
   contradicted → repair → withhold); a **parametric** case (`hours_above` with a
   window + threshold independently recomputed — the recipe actually exercised,
   not just the parameter-free case); a **fabricated-anchor** case (narrated event
   with no matching transition → `anchor_unfound` → withheld); longest-match
   negation safety; the boundary-tolerance **non-flap** case (reference 0.29 vs
   model 0.31 at threshold 0.30 → borderline pass); each fail-soft row (withheld
   answer, unverified caveat, borderline, unbacked tripwire); unknown metric →
   unverified caveat (never error); no-claims + green number check → pass.
2. BDD scenarios in
   [bdd/answer-grounding-check/answer-grounding-check-bdd.md](../../bdd/answer-grounding-check/answer-grounding-check-bdd.md)
   pass; a raw-output evidence file is written.
3. The **two-tier guarantee text** appears verbatim in the spec, the card caveat
   copy, and diagnostics (asserted by test).
4. **Claim-emission rate at the capability floor** (`gemma4:e4b`) measured by
   extending the answer-family benchmark (`evals/prompts/benchmark_prompts.json` +
   `evals/analysis_benchmark/`) — does the floor model reliably emit a
   well-formed claim recipe? Real HA data stays gitignored.
5. Full `python3 -m pytest tests/` green; schema byte-parity + bundle sync green;
   architecture review OK; BDD-evidence review OK.

## Non-goals

- **Grounding the number half's window/param fidelity for non-registry metrics** —
  those are unverified-caveat by design (§3b); the registry is the boundary.
- **Event-scoped answer verification shipping in the first slice** — tranche 2
  (§6); the anchor shape is specified now, re-detection is deferred.
- **Policing the model's threshold choice** — accepted residual (§3, D3's own
  canonical example has the model choosing the threshold); auditable, not gated.
- **Any NLP verdict lexicon** beyond the narrow sentence-initial yes/no tripwire.
- **A second-model judge pass** over the answer (non-deterministic; D3 forbids a
  second free-text pass) — the multimodal visual validator (D8b, packet 6) is the
  probabilistic complement.
- **Editing/rewriting model prose** integration-side (assembly by another name).
- Any change to the sandbox security model or the allowlist/render-family boundaries.

## References

- ADR-0031 — model-authored analysis (D3 grounding principle; D8a two-part validation; the Open verdict-check item this resolves)
- [docs/research/answer-verdict-grounding-check.md](../../docs/research/answer-verdict-grounding-check.md) — full design rationale, alternatives rejected, D3 reconciliation
- [model-authored-analysis.md](model-authored-analysis.md) — the answer channel + §5(a) grounding check this specifies
- ADR-0022 — deterministic render-family routing (the crisp raw-state transition class anchors reuse)
- ADR-0030 / ADR-0029 — codegen render path + repair loop the check reuses
- `worker/isolinear_worker/codegen_sandbox.py` — `_normalize_render_metadata` (claims passthrough)
- `custom_components/isolinear/model_provider.py` — the codegen prompt
- `custom_components/isolinear/job_orchestration.py` — `_record_codegen_worker_dispatch` (where the check runs)
