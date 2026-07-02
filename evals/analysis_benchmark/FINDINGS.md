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
