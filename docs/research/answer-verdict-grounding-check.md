---
title: Deterministic verdict-grounding check for model-authored answers
status: promoted-to-spec
date: 2026-07-03
revised: 2026-07-03 (hardening pass — recompute fidelity)
---

# Research: Answer verdict-grounding check (ADR-0031 D8a, the open half)

## Question

Packet 4's deterministic answer-grounding check has two halves. The number
half is mechanical (extract stated numbers, recompute a reference, compare
within tolerance, flag `nan`/`inf`/`0.00`/unfilled braces). The **verdict
half is open**: an honest number can ride a false qualitative claim —
`"Yes — they're correlated (r=0.04)"` — because the model asserted "Yes" at
generation time, before the data existed. Free text is not deterministically
parseable. How does the integration deterministically catch a free-text
verdict that contradicts the computed data, **without** violating ADR-0031
D3's rejection of integration-side sentence assembly?

## Context

- ADR-0031 D3 (load-bearing): the generated code computes AND formats the
  answer in-sandbox; grounding is enforced by **prompt + deterministic
  backstop**, explicitly NOT by splitting the sentence into number+label
  metadata fields assembled integration-side (closed-vocabulary rigidity;
  capability-floor rationale).
- ADR-0031 D8a mandates the backstop verify "the stated number *and*
  qualitative verdict against a reference computation."
- The failure is real at the floor: the benchmark's single-point regression
  confabulated "power tends to remain stable" from `r=nan`; two models gave
  0.34 vs 0.66 on the same correlation question. A verdict check that only
  scans for degenerate tokens ships the false-"Yes" class.
- Check (a) gates the FIRST display (D8 progressive verification), so this
  check must be cheap, synchronous, and 100% deterministic.

## Revision note (hardening pass, 2026-07-03)

The first draft's claim shape `{metric, inputs, value, verdict, rule}` is a
complete recompute recipe **only for parameter-free metrics**. Correlation is
the flattering case — a pure function of two full aligned series, no window,
no threshold, no event. Almost every other real Isolinear question is
parametric: "average yesterday" needs window bounds; "hours above 75°F" needs
a threshold and a window; "how fast did it cool after the AC shut off" needs
an event anchor. The load-bearing step — *the integration independently
recomputes the metric and matches within tolerance* — was under-specified for
all of them. The generalization bottleneck is **recompute fidelity**, not
verdict-vs-number. This pass: (1) extends the claim to carry the full
recompute recipe (window / params / event anchor); (2) draws a precise
verified boundary with three crisp outcome states; (3) states the guarantee
downgrade outside that boundary explicitly, as part of the contract; (4)
scopes tranche 1 consciously. The sentence-side design — never edit prose,
shared repair loop, D3 reconciliation — is unchanged.

## Design: the claims ledger

**The generated code emits, alongside `answer_text`, a machine-readable
record of each data-contingent claim — used ONLY for verification, never for
display.** The sentence remains authored and assembled entirely in-sandbox;
the integration never constructs, edits, or splices display text from the
record. Deleting the record changes nothing the user sees. That is the line
between *checking* (this design) and *assembly* (what D3 rejected).

### 1. What the generated code emits

The metadata dict returned by `render_chart` MAY carry one new optional key,
`claims` (a list), riding the existing metadata channel (`title` /
`series_plotted` / `warnings` / `answer_text` — no new boundary, no sandbox
change). A claim is `{metric, inputs, window?, params?, value, verdict?,
rule?}` — the **full recompute recipe**, not just the metric name. Canonical
parametric example ("How many hours was the nursery above 75°F yesterday?"):

```python
hrs = hours_above(df["nursery"], 75.0)      # computed over yesterday's slice
verdict = "quite a while" if hrs > 4 else "not long"
answer_text = f"{verdict.capitalize()} — about {hrs:.1f} hours above 75°F."
claims = [{
    "metric": "hours_above",                    # what was computed
    "inputs": ["sensor.nursery_temp"],
    "window": {"start": 1751515200000,          # epoch-ms UTC, [start, end)
               "end":   1751601600000},
    "params": {"threshold": 75.0},              # units of the input data
    "value": hrs,                               # SAME variable as the sentence
    "verdict": verdict,                         # SAME variable as the sentence
    "rule": {"basis": "value",
             "bands": [[4, "quite a while"], [None, "not long"]]},
}]
```

Field spec:

- **`metric`** — free string. Registry membership decides *verifiability*,
  never *expressibility* (D3). Parameter-free metrics (pearson_r over the
  full delivered series) may omit `window`/`params`; everything else carries
  them.
- **`inputs`** — entity ids; must be among the job's delivered series.
- **`window`** — required for any windowed registry metric. Two forms:
  - *absolute*: `{"start": <epoch_ms>, "end": <epoch_ms>}`, half-open,
    UTC epoch-ms — the same currency the ADR already hands the model, so
    "yesterday" is resolved by the model into absolute bounds at codegen
    time, exactly as it already must be to slice the dataframe.
  - *anchored*: `{"anchor": <anchor>, "direction": "after"|"before",
    "duration_ms": <int>}` — resolved to absolute bounds via event
    re-detection (below).
  The window must lie within the delivered data span; the integration cannot
  recompute over data it does not hold (outside → unverifiable, caveat).
- **`params`** — flat dict of JSON scalars (numbers/strings/bools), values in
  input-data units. Keys are free strings; the **registry** declares, per
  metric, which params are required (e.g. `hours_above` → `threshold`;
  `rolling_mean` → `window_ms`). Missing required param = incomplete recipe.
- **`value`, `verdict`, `rule`** — unchanged from the first draft: `value`
  and `verdict` are the SAME variables formatted into the sentence;
  `rule.bands` is an ordered `[min_threshold, label]` list, descending, last
  threshold `null` (catch-all); labels are free strings the model invents.
  No `stated`/formatted-string field — number-in-sentence verification stays
  the number check's job.

### 1a. Event anchors — what makes one deterministically reproducible

The anchor object (used inside an anchored `window`):

```python
"anchor": {
    "entity": "climate.family_room",   # must be in the delivered series
    "attribute": None,                 # None = state; else attribute name
    "to": "off",                       # exact value after the transition
    "from": "cooling",                 # optional exact prior value; None = any
    "occurrence": -1,                  # 1-based from start; negative from end
    "search": {"start": ..., "end": ...},  # absolute epoch-ms scan bounds
    "resolved_at": 1751592300000,      # epoch-ms the generated code resolved
}
```

An anchor is **deterministically reproducible** iff ALL of:

1. `entity` is among the job's delivered input series — the integration
   re-detects from data it already holds; no new fetch, so check (a) stays
   cheap and synchronous.
2. The event is a **crisp discrete transition**: exact string equality of
   `to` (and `from`, if given) against the normalized raw-state timeline —
   the binary/climate/categorical class ADR-0022 already handles as raw
   states. No fuzzy matching, no "approximately off."
3. `occurrence` + absolute `search` bounds select a **unique index** into the
   finite ordered list of matching transitions — the same index on both
   sides, no guessing.
4. `resolved_at` lets the check confirm the *same* event was found (identity,
   not just existence).

Explicitly NOT reproducible — degrades to the unverified caveat by
construction, never attempted:

- Numeric threshold-crossings on analog series as anchors (crossing time is
  resample/alignment-sensitive; deferrable once the alignment prescription
  lands, not banned forever).
- Rate/shape conditions ("when it was cooling fast") — fuzzy segmentation is
  not a crisp function of the data; there is no recipe to carry.
- Anchors on entities outside the delivered series.
- Anchors missing `search` bounds or `occurrence`.

### 2. What the codegen prompt instructs

Extend `_CODEGEN_PROMPT_RULES` (model_provider.py), replacing the tail of the
current verdict rule:

> If `answer_text` makes a qualitative judgment about the data (yes/no,
> strong/weak, warmer/cooler, rising/stable), compute the judgment from a
> variable via an explicit threshold rule, and ALSO return a `claims` list in
> the metadata dict recording how: each claim is
> `{metric, inputs, window, params, value, verdict, rule}` where `value` and
> `verdict` are the SAME variables formatted into the sentence, `window` is
> the exact epoch-ms bounds the computation used, `params` holds any
> thresholds or parameters (in input-data units), and `rule` is
> `{basis: "abs"|"value", bands: [[threshold, label], …, [None, label]]}` —
> the exact rule the code used. If the analysis is scoped to an event (e.g.
> "after the AC turned off"), record the event as an anchor:
> `{entity, attribute, to, from, occurrence, search, resolved_at}` naming the
> exact state transition the code located. Band labels must not be substrings
> of one another.

Plus the §1 canonical example. Cost at the capability floor: the model
already returns a metadata dict, already resolved "yesterday" to slice
bounds, and already bound every variable the claim records — the claim is a
dict literal over values it just used. Failure to emit is fail-soft (below),
never a hard gate.

### 3. What the integration deterministically checks

Runs in `job_orchestration.py` inside `_record_codegen_worker_dispatch`, on
the success branch **before** `_finish_codegen_success` serves the artifact
(so check (a) still gates first display). A failure is routed into the
existing repair branch as a synthetic sandbox-shaped error
(`{code: "grounding_check_failed", details: {claim, reference, expected_label,
observed}}`) so `repair_chart_code` consumes it through its existing
signature — the grounding failure IS the repair feedback. Shared budget:
`max_codegen_repair_attempts`. No new config knobs.

Per claim, in order:

1. **Structure.** Claim malformed (missing value/verdict-with-no-rule, bands
   overlapping/empty/no catch-all) → `grounding_claim_malformed` (repairable).
2. **Recipe completeness.** `metric` ∈ registry but a registry-required
   `window`/`param` is missing, or the window lies outside the delivered
   span → `grounding_recipe_incomplete` (one repair; after exhaustion →
   unverified caveat — a bookkeeping failure is not evidence of a false
   verdict). `metric` ∉ registry → skip to step 5; the claim is
   **unverifiable** (caveat), and steps 5–6 still run against the recorded
   `value` (internal consistency).
3. **Degeneracy.** `value` non-finite → fail (same class as `nan` in the
   sentence).
4. **Anchor resolution + reference recompute.** If the window is anchored:
   anchor fails the §1a reproducibility criteria → unverifiable (caveat);
   criteria met → re-detect the transition on the delivered series. No
   matching transition exists → `grounding_anchor_unfound` (contradicted
   class — the claimed event is not in the data; repairable). Re-detected
   event ≠ `resolved_at` → `grounding_anchor_mismatch` (contradicted class;
   repairable). Resolved anchor yields concrete absolute bounds. Then
   recompute the metric over the claim's window with the claim's params and
   the **integration-prescribed alignment** (the ADR's open resample item —
   the reference is where the prescription bites). `|value − reference|`
   outside tolerance → `grounding_value_mismatch` (repairable).
5. **Verdict containment.** Casefold + whitespace-collapse + word-boundary
   match every band label against `answer_text`; the **longest matching
   label** is the sentence's effective verdict (longest-match makes negation
   safe: "not correlated" beats its substring "correlated"). No label matches
   → `grounding_verdict_absent`. Effective verdict must equal the claim's
   `verdict` field → else `grounding_verdict_ambiguous`.
6. **Verdict consistency.** Apply `rule` to the check value (the reference
   when available, else the recorded `value`) → expected label. Expected ≠
   claimed verdict → `grounding_verdict_contradicted`. **Boundary rule:**
   evaluate the bands at check value ± tolerance; if the labels differ across
   that span, the claim passes as *borderline* (diagnostics note, never a
   flap-fail over sub-tolerance differences).

Sentence-level tripwire (the only free-text parsing, deliberately
precision-over-recall): `answer_text` beginning `^\s*(yes|no)\b`
(case-insensitive) with **no** claim carrying a `verdict` →
`grounding_verdict_unbacked` (one repair asking for a claim, then caveat). No
broader verdict lexicon is attempted — a wider NLP detector would be
non-deterministic in effect and its false positives would burn repair
attempts on good answers.

Why this catches the ADR's exact case, `"Yes … (r=0.04)"` — and the new
event-scoped analogs:

- Code computed the verdict honestly → everything passes (the good path).
- Sentence hard-codes "Yes", record honest → containment mismatch (step 5).
- Record hard-codes `verdict: "Yes"` too → rule vs reference 0.04 (step 6).
- Record hard-codes `value: 0.5` as well → reference recompute (step 4).
- **New:** model narrates "after the AC shut off" but no such transition
  exists in the data → anchor re-detection finds nothing (step 4,
  `anchor_unfound`) — a fabricated-event class the first draft could not see.
- Model games the *threshold* (`bands: [[0.01, "Yes"], …]`) → passes.
  **Accepted residual**: threshold choice is the model's analytic judgment —
  D3's own canonical example has the model choosing 0.3 at generation time.
  Now explicit and auditable (diagnostics, eval corpus); no runtime
  threshold policing (closed-vocabulary creep in numeric clothing).
- Model fabricates an entire claim under an unknown metric → unverifiable,
  ships with the "unverified" caveat. This bounds what can be *silently
  trusted*, not what can be *said*.

### 3a. The verified boundary — three states, precisely

**verified** ⇔ `metric ∈ registry` ∧ recompute recipe complete and
reproducible (required window/params present; window within delivered span;
any anchor meets §1a) ∧ reference recompute matches within tolerance ∧
verdict consistent with the declared rule at the reference.

| State | Meaning | What lands here |
|---|---|---|
| **verified** | The integration independently reproduced the value from allowlisted data and the verdict follows from the declared rule at the reference | Full pass of steps 1–6 with a registry recompute |
| **unverified-caveat** | Nothing contradicted, but **nobody reproduced the value** | Metric ∉ registry; fuzzy segmentation / curve_fit-class analysis (shows up simply as an unregistered metric — no special mechanism needed); recipe incomplete after repair; window outside delivered span; anchor irreproducible by construction (§1a) |
| **contradicted** | **Positive evidence** of inconsistency | Reference recompute mismatch; anchor re-detection finds a different event or none; verdict ≠ rule(check value); non-finite value; verdict absent/ambiguous vs the record |

Assignment rule: **contradicted requires positive evidence; inability to
check is never contradiction.** Fuzzy segmentation and unregistered metrics
mean the model did nothing wrong — caveat, never repair-then-withhold.

### 3b. The guarantee, stated plainly (first-class contract text)

The check gives a **two-tier guarantee**, and the spec must say so verbatim
rather than let the correlation case advertise for the whole feature:

- **Inside the verified boundary**: *value↔data*. The integration
  independently recomputed the number from allowlisted history using the
  claim's own recipe; the verdict provably follows from the declared rule at
  that reference. This is the strong property.
- **Outside the boundary**: *internal consistency only* —
  value↔verdict↔rule. The verdict matches the value the code **claims** to
  have computed, under the rule the code **claims** to have used; nobody
  reproduced that value. This still deterministically catches: a verdict
  contradicting the claim's own recorded value (steps 5–6 run regardless),
  degenerate/non-finite values, and record-vs-sentence divergence. It
  **cannot** catch a fabricated value paired with a matching verdict.

The "unverified" caveat is the honest surface of exactly this gap: it means
"not independently reproduced," not "probably fine." Card copy for the
caveat state should say that plainly. Safe-but-weaker is the design point —
outside the boundary the system *caveats rather than trusts*, and the
boundary itself is explicit (the registry), auditable, and demand-grown.

### 4. Fail-soft policy

| Outcome | First remedy | After repair exhaustion |
|---|---|---|
| Contradicted (`verdict_contradicted`, `value_mismatch`, `anchor_unfound`, `anchor_mismatch`, non-finite value, `verdict_ambiguous`) | Repair via the shared codegen loop (grounding failure as feedback) | **Withhold `answer_text`** — serve the chart with a "couldn't produce a verifiable answer" note (surfaced-never-silent; chart-without-answer is already a legal state — the Pillow fallback ships it) |
| Unbacked (tripwire hit, no claim) / malformed claim / incomplete recipe on a registry metric | One repair requesting a well-formed claim/recipe | Show the answer with the "unverified" caveat |
| Unverifiable (metric outside registry; window outside delivered span; anchor irreproducible by construction — internal consistency passed) | None — the model did nothing wrong | Show with the "unverified" caveat |
| Borderline (within tolerance of a band edge) | None — pass, diagnostics note | — |
| No claims, no tripwire, number check green | Pass | — |

**Never strip or rewrite the verdict.** Editing model prose integration-side
is assembly by another name — the exact thing D3 rejects — and risks garbling.
The only integration verbs are: show as-is, show with a caveat rendered as a
**separate UI element** (never spliced into `answer_text`), or withhold the
whole sentence.

### 5. Contract surface (all additive, optional, back-compatible)

- `render-result.schema.json`: `render_metadata.claims` — optional array
  (worker passes it through `_normalize_render_metadata` like `answer_text`);
  claim objects now nest `window`/`params`/`anchor`. Claims persist to
  diagnostics; they are not display data.
- `integration-job-snapshot.schema.json`: optional
  `chart.answer_verification` (`"verified"` | `"unverified"`) — the card's
  hook for the caveat states; a withheld answer is simply an absent
  `answer_text`. (Distinct from D8b's `verification_status`, the *visual*
  pass.)
- Codegen prompt: the §2 instruction + example.
- Integration: the §3 check + registry (metrics + their required params),
  wired into the existing repair loop.

### 6. Tranche-1 scope — a conscious restriction, not a silent gap

First-slice ANSWER-bearing prompts restrict to **reproducible,
registry-covered metrics** — approximately the tranche-1 transform set:
`mean`, `delta`, `pearson_r`, `rolling_mean`, `daily_max`/`daily_min`, plus
`hours_above`-style threshold counts if the eval corpus wants them. All are
parameter-light: at most an absolute `window` and one scalar param
(`threshold` / `window_ms`). Inside this set, every answer carries the
strong value↔data guarantee.

Deferred, explicitly:

- **Tranche 2 — event-scoped answers** ("how fast did it cool after the AC
  shut off"): the anchor shape is designed *now* (§1a) so the claim contract
  doesn't churn, but anchor re-detection ships later.
- **Accepted residual — causal/interpretive verdicts** ("is the attic heat
  *seeping* into the family room"): the lag-correlation value is checkable;
  the word "seeping" is an interpretive leap no deterministic rule can
  ground — same class as threshold-gaming. The number gets verified; the
  interpretation is the model's analytic judgment, auditable via
  diagnostics and the eval corpus.
- **Unregisterable analyses** (curve_fit time constants, fuzzy
  segmentation): unverified-caveat by construction.

**"Works in every context" is a non-goal.** The design guarantees the strong
property inside a declared boundary and an honest caveat outside it; the
boundary grows demand-driven (registry growth mirrors the D6 library
principle), and each growth step must satisfy §1a-grade reproducibility
before admission.

### Edge cases

- **Pure-number answer, no verdict** ("The correlation coefficient is
  0.42."): claims optional; a claim without `verdict`/`rule` still feeds
  step 4 (a stronger number check); absence entirely is fine.
- **Qualitative-only answer, no number** ("Yes, they track each other."):
  the number check has nothing to grip; the claim is the *only* possible
  deterministic ground — this case is why the record must exist.
- **Multiple claims in one sentence**: one claim per judgment; each checked
  independently; all must pass.
- **Claim window ⊂ fetch window** ("average *yesterday*" inside a 3-day
  fetch): legal and expected — the recipe's absolute bounds tell the
  reference computer which slice; the model already computed those bounds to
  slice the dataframe. Window extending *outside* the delivered span →
  unverifiable (caveat), never guessed-at clipping.
- **Ranges / multi-valued results**: one scalar claim per endpoint (metric
  `daily_min` + `daily_max`); per-entity enumerations verify the claimed
  aggregate judgment; the number check handles individual numerals.
- **Comparator ambiguity** ("moderately correlated"): multi-band rules make
  the model declare its own banding; the check enforces consistency with the
  declared bands, not an external definition of "moderate."
- **Directional claims** ("warmer", "rising"): `basis: "value"` with a
  0-threshold two-band rule over a delta/slope metric, window declared.
- **Units**: the record is unit-blind by construction — `value`, `params`,
  the reference, and the bands all live in input-data units; display
  conversion stays in the sentence and is the number check's tolerance
  problem.

### Alternatives considered and rejected

- **Integration-side NLP over `answer_text`** (verdict lexicon + polarity):
  unbounded phrasings, negation traps, false positives that burn repair
  attempts — "deterministic" in mechanism but not in effect. Kept only as
  the narrow sentence-initial yes/no tripwire.
- **Structural decomposition** (number+label fields assembled
  integration-side): rejected by D3; not relitigated.
- **Closed event-vocabulary for anchors** (enumerated event types): same
  closed-vocabulary rigidity D3 rejected for labels; instead the anchor is
  free-parametric (any entity/attribute/value strings) with *reproducibility
  criteria* (§1a) deciding verifiability — unrecognized shapes degrade to a
  caveat, never to an inexpressible analysis.
- **AST provenance lint**: needs a verdict-word lexicon and proves only that
  *a* conditional ran — cannot tie the verdict to the reference value. Could
  return as a cheap advisory; not the mechanism.
- **Second-model judge pass over the answer**: not deterministic; collides
  with D3's never-a-second-free-text-pass posture. (The multimodal visual
  validator remains the *probabilistic* complement, per D8.)

## D3 reconciliation (the crux, answered)

The claims ledger is **compatible with D3**. D3 rejected a design with two
properties: (i) the integration assembles the sentence from fields, (ii) the
label fields impose a closed vocabulary. The ledger has neither. Assembly:
the sentence is authored, formatted, and assembled in-sandbox by model code;
no display path reads a claim; delete the ledger and the user-visible output
is byte-identical. Vocabulary: labels, metrics, params, and anchor values are
free strings; an unrecognized metric or irreproducible anchor degrades to a
caveat, never to an inexpressible sentence. The ledger's relationship to the
answer is the PNG's relationship to the visual validator — an auditable
artifact *reviewed*, not *composed*. And it is not over-investment against
sub-baseline incompetence: D8a explicitly mandates verifying the qualitative
verdict, the false-verdict failure was observed at the capability floor (the
`r=nan` confabulation), and — since free text is not deterministically
parseable and integration assembly is rejected — a model-emitted audit record
is the only remaining point in the design space where a deterministic
backstop can exist. The record is the minimum structure that makes the check
D3 itself promises possible.

## Recommendation: spec, not supersession

This is **contract-touching but not contract-changing**: it resolves an item
ADR-0031 explicitly left Open, inside the frame D3 fixed. Nothing in ADR-0031
or the accepted model-authored-analysis spec becomes false. But it adds
schema fields (`render_metadata.claims` with nested recipe,
`chart.answer_verification`), a prompt-contract extension, and a check
algorithm with a fail-soft policy — too much surface for a research note to
carry as the durable reference.

**Promote this note to a small standalone spec —
`docs/specs/answer-grounding-check.md` + paired BDD — depending on ADR-0031
and model-authored-analysis.md, superseding neither.** Its proof requirements
should include: the seeded adversarial case (honest number, hard-coded false
"Yes") caught end-to-end; a seeded **parametric** case (`hours_above` with
window + threshold independently recomputed — the recipe actually exercised,
not just the parameter-free flattering case); a seeded **fabricated-anchor**
case (narrated event with no matching transition → `anchor_unfound` →
withheld answer); the two-tier guarantee text present verbatim in spec and
caveat card copy; claim-emission rate at the capability floor (gemma4:e4b)
via the answer-family benchmark; the boundary-tolerance non-flap case; and
the fail-soft table exercised (withheld answer, unverified caveat,
borderline pass). No superseding ADR is needed; if review judges the claims
channel a material change to the D3 contract, the escalation is a short
amending ADR that narrows D3's "not structurally" phrasing to "not
structurally *for assembly*" — but the reading defended above makes that
unnecessary.

## Open sub-questions

- Tolerance policy per metric family (relative vs absolute; shared with the
  number check and the prescribed-alignment open item).
- Anchor re-detection identity tolerance: exact timestamp equality on the
  normalized raw-state timeline vs one-sample slack (normalization may shift
  a boundary sample) — decide when the alignment prescription lands.
- Initial registry membership: proposed above as the tranche-1 transform set
  (§6); confirm against the answer-family eval corpus at landing.
- Whether `claims` should also surface (redacted) in the artifact metadata
  for inspectability, or diagnostics-only suffices.

## Resolution

Promoted to spec. Human ratified the direction (incl. the hardening pass)
2026-07-03; distilled into `docs/specs/answer-grounding-check.md` + paired BDD
(accepted). This note remains the design rationale of record.
