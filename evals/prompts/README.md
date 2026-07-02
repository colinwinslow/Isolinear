# Benchmark prompts

`benchmark_prompts.json` is a curated corpus of **real** natural-language prompts
that have actually been used against Isolinear during development — harvested
from BDD evidence files, evals, tests, `STATUS.md`/`HANDOFF.md`, and the full git
history (assembled 2026-07-01). It exists so testing and **model benchmarking**
draw from one stable, shared set instead of ad-hoc one-offs.

## What it's for

- **Planner / entity-selection / render-family routing** — feed each `prompt`
  and score the resolved plan against `expect.render_family` /
  `expect.behavior`.
- **ADR-0029 codegen benchmarking** — for a resolved ChartSpec + normalized
  history, run `generate_chart_code` → worker sandbox and tally
  accept / reject / repair per model (gemma4:e4b, qwen2.5-coder:7b, …). This is
  the data the keep/remove decision (ADR-0029) rests on.

## Shape

Each entry:

| field | meaning |
|---|---|
| `id` | stable short id (`ts-01`, `ov-02`, …) |
| `prompt` | the verbatim user prompt |
| `category` | capability group (single_numeric, numeric_binary_overlay, timeline, distribution_histogram, aggregate_bar, explicit_entity_id, ambiguous_clarification, semantic_alias, out_of_scope_refuse, unsupported) |
| `expect` | intended/observed behavior — `render_family`, `window`, `series`, `group_by`/`op`, or `behavior` |
| `edge` | present + `true` for non-happy-path cases (fuzzy windows, ambiguity, refusals) |
| `notes` | provenance/history where a prompt exercised a specific bug or ADR |

`render_families` and `categories` are documented inline in the JSON.

## Caveats

- `expect` reflects the **intended** behavior; actual routing depends on the
  configured entity allowlist (many prompts assume the household sensors these
  were captured against — upstairs/downstairs/family-room/attic/bathroom temps,
  the kitchen ecobee + kitchen door, the dishwasher/AC).
- Prompts are captured strings; light near-duplicates were merged.
- Add new real prompts here (with an `id` + `expect`) as they come up, rather
  than scattering them across new tests.
