# Answer grounding check: deterministic verdict verification — BDD

## Status

Accepted. Paired with [docs/specs/answer-grounding-check.md](../../docs/specs/answer-grounding-check.md).
Resolves ADR-0031 D8a's open verdict half via the claims ledger (design rationale:
[docs/research/answer-verdict-grounding-check.md](../../docs/research/answer-verdict-grounding-check.md)).

## Why this BDD exists

An honest number can ride a false qualitative verdict (`"Yes — they're correlated
(r=0.04)"`). These scenarios pin down that the integration deterministically
catches contradicted verdicts by independently recomputing the metric from
allowlisted data via the claim's own recipe, honestly caveats what it cannot
reproduce (never contradicting on inability to check), and never edits the model's
prose — it shows as-is, caveats via a separate element, or withholds the sentence.

## Scenarios

### Scenario A — honest number, false verdict: contradicted → repair → withheld

**Given** a codegen answer whose sentence hard-codes `"Yes — they're correlated
(r=0.04)."` and whose claim records `metric: pearson_r`, `value: 0.04`, `verdict:
"Yes"` under `rule.bands: [[0.3, "Yes"], [None, "Not really"]]`
**When** the grounding check runs
**Then** the integration recomputes `pearson_r` over the two delivered series
(≈0.04), applies the rule (expected `"Not really"`), finds it contradicts the
claimed `"Yes"` (`grounding_verdict_contradicted`), routes the failure into the
shared codegen repair loop, and — on repair exhaustion — **withholds
`answer_text`**, serving the chart with `answer_verification: "unverified"` and a
"couldn't produce a verifiable answer" note (never a fabricated one).

### Scenario B — grounded verdict passes (the good path)

**Given** an answer whose code computed `verdict = "Yes" if abs(corr) > 0.3 else
"Not really"` and the recompute agrees (`corr ≈ 0.62`, verdict `"Yes"`)
**When** the check runs
**Then** all six steps pass with a registry recompute, `answer_verification:
"verified"`, and the answer is shown as-is under the caption.

### Scenario C — parametric metric: window + threshold independently recomputed

**Given** "how many hours was the nursery above 75°F yesterday?" with a claim
`metric: hours_above`, `window: {start, end}` (yesterday, absolute epoch-ms),
`params: {threshold: 75.0}`, `value: 4.6`, `verdict: "quite a while"`
**When** the check runs
**Then** the integration recomputes `hours_above` over the claim's window and
threshold, matches `value` within tolerance, confirms the verdict follows the
rule, and marks it **verified** — the recipe is actually exercised, not just the
parameter-free correlation case.

### Scenario D — fabricated event: anchor_unfound → withheld

**Given** an answer narrating "the family room cooled 2°F in the 30 min after the
AC shut off" with an anchored window whose anchor names an `off` transition of
`climate.family_room` that **does not exist** in the delivered raw-state timeline
**When** the check re-detects the transition per the §1a criteria
**Then** no matching transition is found → `grounding_anchor_unfound`
(contradicted class), repair runs, and on exhaustion the answer is withheld — a
fabricated-event class a token-scan could never catch.

### Scenario E — unknown metric: unverified caveat, never contradicted

**Given** an answer whose claim uses a `metric` outside the registry (e.g. a
`curve_fit` thermal time constant) with internally-consistent value/verdict/rule
**When** the check runs
**Then** the metric is unverifiable — steps 5–6 still confirm internal
consistency (verdict follows rule at the recorded value) — the result is
**unverified-caveat**, the answer is shown with the "not independently
reproduced" caveat, and it is **never** marked contradicted (inability to check
is not evidence of a false verdict).

### Scenario F — borderline: no flap over sub-tolerance differences

**Given** a claim `value: 0.31` and a rule threshold `0.30`, where the
independent reference computes `0.29`
**When** the check evaluates the bands at the reference ± tolerance
**Then** because the band labels differ across that span the claim passes as
**borderline** (a diagnostics note), not a `verdict_contradicted` flap-fail.

### Scenario G — unbacked yes/no: tripwire → repair → caveat

**Given** an `answer_text` beginning `"Yes,"` with **no** claim carrying a
`verdict`
**When** the check runs
**Then** the sentence-initial tripwire fires (`grounding_verdict_unbacked`), one
repair asks for a well-formed claim, and on exhaustion the answer is shown with
the "unverified" caveat (no broader NLP lexicon is attempted).

### Scenario H — chart-only / pure-number answer: no verdict machinery

**Given** a chart-only render (no `answer_text`) or a pure-number answer with no
verdict and a green number check
**When** the check runs
**Then** it passes with no claim required — the ledger is optional, and its
absence is not a failure.

### Scenario I — never edits the prose

**Given** any check outcome
**When** the integration surfaces the result
**Then** it only ever shows `answer_text` as-is, renders a caveat as a **separate
UI element** (never spliced into `answer_text`), or withholds the whole sentence —
it never strips, rewrites, or splices the model's prose.

### Scenario J — the two-tier guarantee is stated, not implied

**Given** the shipped spec, the card caveat copy, and the diagnostics record
**Then** the two-tier guarantee text ("inside the boundary: value↔data; outside:
internal consistency only — the caveat means *not independently reproduced*, not
*probably fine*") appears verbatim in all three (asserted by test).

## Evidence

The implementing sub-packets (4a–4d) produce an evidence file at
`bdd/answer-grounding-check/answer-grounding-check-evidence.md` with raw outputs:
the recompute references and contradiction records for A/C/D; the verified/
unverified/contradicted state per scenario; the borderline non-flap; and the
capability-floor claim-emission rate from the extended answer-family benchmark.
