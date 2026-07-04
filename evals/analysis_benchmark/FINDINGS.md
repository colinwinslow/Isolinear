# Benchmark findings — claim-emission rate, 2026-07-03

Grounding-check spec **proof req #4**: does the capability floor (`gemma4:e4b`)
reliably emit a well-formed claim recipe (`{metric, inputs, window?, params?,
value, verdict?, rule?}`) alongside `answer_text`? Measured over the 18-prompt
corpus (the original 17 + `anchor-01`, the registry-verifiable anchored case),
9 flagged `claim: true` (verdict/comparison expected), 2 of those anchored.
Emitted claims scored by the REAL production checker
(`custom_components.isolinear.answer_grounding`) against the same live fixture
(fresh 7-day extract, 16 entities, 16,318 points). Three runs, one variable at
a time:

| Run | Prompt variant | strict / repair (18) | claims emitted (9 expected) | well-formed | registry-verified | anchored (2 expected) |
|---|---|:--:|:--:|:--:|:--:|:--:|
| 1 | original "value formatted into the sentence", num_predict 3000 | 7 / 12 | 6/9 | 6/6 | 0/6 | 0/2 |
| 2 | + "value is a raw JSON number" hardening, 3000 | 3 / 5 | 3/9 | 2/3 | 0/3 | 0/2 |
| 3 | same wording, num_predict 6000 | 3 / 8 | 5/9 | 4/5 | 0/5 | 0/2 |

## Headline: emission is reliable; the strong tier is not yet reached

- **When the generated code executes, the claims channel fires essentially
  every time**: run 1 — 6/6 claim-expected prompts that ran emitted claims;
  run 3 — 5/5. Every miss in the "emitted" column is a prompt whose code never
  executed at all (SyntaxError / runtime error), not a prompt that ran and
  skipped the ledger. The floor model **does** follow the claims instruction.
- **Structure is mostly right** (dict shape, metric string, inputs are real
  entity_ids, bands lists) — 6/6 and 4/5 pass the checker's structure step.
- **Registry-verified: 0 in every run.** No claim earned the strong value↔data
  tier live. Three distinct causes, all now measured (below). Everything landed
  in exactly the box the three-state boundary designed for it — **no false
  "verified" was ever produced**, and every contradicted case was a genuine
  defect the check caught before display.

## What the wording of one prompt line did (run 1 → 2)

Run 1's instruction said `'value' (the same variable formatted into the
sentence)` — and gemma read "formatted" literally: **13/13 emitted claims
carried a stringified value** (`'3.0°F'`, `'1189.7 minutes'`, `'nan'`), every
one flagged `grounding_nonfinite_value`. One sentence of prompt hardening
("raw JSON number — never a pre-formatted string; units belong in the
sentence") fixed the type on **every** subsequent claim (runs 2–3: all values
numeric). The production `_CODEGEN_PROMPT_RULES` now carries the hardened
wording. Two corollary findings:

- The 3000-token benchmark cap started truncating generations mid-string once
  the claims scaffolding made the code longer (the run-2 execution collapse is
  `unterminated string literal`, not analysis failures); production codegen
  does not cap `num_predict`, so the benchmark now runs 6000.
- Floor-model codegen is **highly prompt-sensitive** at temperature 0: a
  three-line prompt delta swung execution success 12/18 → 8/18 with a disjoint
  failure set. Per-prompt success is not a stable property; corpus-level rates
  are the only meaningful signal.

## Why nothing verified (the three causes, with examples)

1. **Free metric naming (works as designed, costs verification).**
   `mean_difference`, `percentage_running`, `max_daily_swing`, `spike_count`,
   `slope_rate` — honest names for what the code computed, none in the
   tranche-1 registry → `unverified_no_reference` caveat. Correct per D3
   (registry decides *verifiability*, never *expressibility*) — and renaming
   them would be wrong (`mean_difference` over aligned series is NOT the
   registry `delta` = last−first; a forced rename would produce false
   `value_mismatch`). Registry growth is the demand-driven fix.
2. **Recompute-fidelity on `pearson_r` (the spec's "prescribe the alignment"
   open item, confirmed live).** Run 3's sp-stats-01 emitted a textbook claim
   (`pearson_r`, both entity ids, numeric `r=0.183`, banded rule, matching
   verdict) — and the registry recompute returned no reference because
   `_compute_pearson_r` intersects **exact** timestamps and real HA series
   rarely share any. The registry needs the integration-prescribed alignment
   (e.g. resample-to-grid) before correlation claims can ever verify on real
   data.
3. **Rule-structure defects the checker catches** (repairable, and the repair
   loop exists in production but not in this first-attempt measurement):
   ascending bands (`[[-1.0, 'Rapid'], [-0.1, 'Moderate'], …]` →
   `grounding_claim_malformed`); no null catch-all; substring-violating labels
   (`'Significantly Warmer'` / `'Not significantly warmer'` with sentence word
   "warmer" → `grounding_verdict_absent`); a genuine
   `grounding_verdict_contradicted` (pd-05: verdict `'hottest'` vs the claim's
   own rule at its own value — the exact false-verdict class the check exists
   for, caught).

## Anchored windows: never emitted (0/2 every run)

Both event-scoped prompts produced event logic in code (transition scans,
`cooling_starts[-1]`) but recorded **absolute** window bounds, not the §1a
anchor record — even with the anchored form documented with an example. The
absolute form is still verifiable (value↔data holds; only event *identity*
goes unconfirmed), so this is acceptable for tranche 1, but 4d's re-detection
path will not exercise in production until either the prompt pushes harder or
a capability above the floor emits it. Recorded as an open item, not a defect.

## What this decides

- **Proof req #4 is answered**: the floor model reliably *emits* (100% of
  executing answer-family generations) and mostly *forms* the recipe; it does
  not yet reach the verified tier. The fail-soft three-state boundary — not
  the strong guarantee — is what carries floor-model UX, exactly as §3b's
  two-tier framing anticipated.
- The `value`-as-number prompt hardening ships in production
  (`_CODEGEN_PROMPT_RULES`).
- Registry follow-ups (demand-driven, not this packet): prescribed alignment
  for `pearson_r`; candidate registry additions actually requested by the
  corpus (`mean_difference`-style aligned delta, time-in-state fraction).

Raw per-run artifacts (gitignored): `runs/run1_stringvalue.log`,
`runs/results_run1.json`, `runs/run2_numericvalue_3000cap.log`,
`runs/results_run2.json`, `results.json` (run 3).

---

# Benchmark findings — 2026-07-02

16 prompts × `gemma4:e4b` + `qwen2.5-coder:7b`, generated `render_chart` code
executed against 7 days of real HA history (16 entities: indoor/outdoor temps,
humidity, AC power, thermostat `hvac_action`, a door). Three runs; the numbers
below are the clean-contract run (timestamps as epoch-ms). These results back
ADR-0031 decisions 6, 8, and 9.

## Headline

| Model | strict (1st attempt) | with 1 repair |
|---|:--:|:--:|
| gemma4:e4b | 12/16 | 13/16 |
| qwen2.5-coder:7b | 7/16 | 11/16 |

On a **raw mixed-precision ISO-timestamp** contract both models scored ≈2/16 —
so the boundary, not the analysis, was the wall.

## 1. The data boundary dominates (→ decision 9)

≈19 of ~28 failures in the raw-string runs were the identical error:
`pandas.to_datetime` infers one format from the *first* element. HA writes the
initial state on-the-second (`…:43+00:00`) and the rest with microseconds, so it
locks onto `%Y-%m-%dT%H:%M:%S%z` and dies on row 2. Proven in isolation:

```
bare to_datetime(list)            -> FAIL
to_datetime(list, utc=True)       -> FAIL   (a natural "fix" that doesn't work)
to_datetime(list, format='ISO8601') -> OK
```

The models wrote idiomatic, correct code; the boundary mugged them. Handing the
model epoch-ms integers erased the whole class (gemma 2/16 → 12/16).
**Requirement:** the integration normalizes timestamps at the data boundary; the
model never parses raw HA timestamp strings.

## 2. Execution success ≠ correct (→ decision 8)

Charts that ran and returned confident answers while being wrong:

- **Flat-zero seasonal decomposition** — `seasonal_decompose` on a
  non-resampled series produced a flat-zero "Seasonal" panel, while the answer
  described "a predictable repeating 24-hour cycle." Chart flatly contradicts
  the answer.
- **Single-point "regression"** — a sparse/stale sensor aligned to one surviving
  row; the scatter had one dot, no trend line, and the answer said
  `r=nan` … "power tends to remain stable" (a verdict confabulated from a NaN).
- **`0.00 °F/hr` cooling rate** — a degenerate `curve_fit`, reported as fact.
- **Cross-model disagreement on the same question** — correlation 0.34 vs 0.66;
  duty cycle 3.1% vs 0.15% — different resample/alignment choices. At least one
  is wrong each time (→ "prescribe the alignment" open item).

A pure "did it run" signal ships all of these.

## 3. Two validators, demonstrated (→ decision 8)

- **Deterministic answer-grounding check** catches broken numbers
  (`nan`/`inf`/`0.00`, verdict-vs-number inconsistency) cheaply and reliably.
- **Visual validator** — multimodal `gemma4:e4b` reviewing its own PNG
  (`/api/show` reports `vision`; `qwen2.5-coder` does not → capability-gated,
  default on when supported). It flagged the flat-zero decomposition that
  execution + answer-text both missed. A **vague prompt missed** the single-point
  scatter; a **structured checklist prompt** (data-sufficiency / read every text
  element for nan-inf-contradictions / does-it-answer-the-question) caught it —
  with no false positive on a genuinely good heatmap.
- **Visual-repair loop** (reuses the codegen repair machinery, image+critique as
  the signal) closed end-to-end: gemma flagged its flat decomposition →
  diagnosed the missing uniform resample → rewrote the code → re-rendered a
  correct decomposition with a real daily cycle.

## Caveat

Generated code executed under pandas 3.x here; the worker pins pandas 2.x. Some
failures (`'H'`/`'M'` offset aliases) are pandas-3-only and would pass on the
worker — but they are a preview of a future bump and evidence the models emit
stale idioms (a repairable tax).
