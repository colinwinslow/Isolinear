# Card-level legend for the codegen render path (+ computed kind) — Evidence

Paired with [docs/specs/card-level-legend-codegen.md](../../docs/specs/card-level-legend-codegen.md)
and [card-level-legend-codegen-bdd.md](card-level-legend-codegen-bdd.md). Raw
outputs, captured 2026-07-17 at version 0.2.42.

Status: all four scenarios proven. B, C, D on the real sandbox + orchestration +
frontend; **Scenario A CONFIRMED LIVE 2026-07-17** after the CT106 worker rebuild +
Colin's HACS 0.2.42 redownload (the legend passthrough is a WORKER-side change in
`_normalize_render_metadata` — it went live once the worker was rebuilt on CT106,
not CT103, which is GPU-only now).

## Scenario A — a computed-average chart shows a three-row legend with a computed row (LIVE)

**Confirmed on the real card + the live e2e harness (run `20260717T060726Z`, prompt
e2e-11 "What is the average of the kitchen and basement temperatures over the last
day?"), live-version 0.2.42.** `render_path: codegen`, no fallback. The served
snapshot's `chart.legend` carried three entries — two solid `series` sensors + one
dashed `computed` average:

```json
[
  { "kind": "series",   "label": "Basement Temperature", "color": "#1f77b4" },
  { "kind": "series",   "label": "Kitchen Temperature",  "color": "#ff7f0e" },
  { "kind": "computed", "label": "Average Temperature",  "color": "#d62728" }
]
```

The served PNG (`e2e-11.png`, eyes-on) shows two solid sensor lines (blue Basement,
orange Kitchen) and a **red dashed** computed Average between them, with **no
in-image `ax.legend()`**. Colin's card screenshot independently confirmed the
`COMPUTED`-tagged legend row and the grounded answer ("…was 72.94 °F"). The
underlying sandbox passthrough is also unit-proven — `invoke_codegen_sandbox` on a
`render_chart` returning `legend: [{…kind:"series"…},{…kind:"computed"…}]` preserves
it (previously `_normalize_render_metadata` dropped it), `validate_contract(
"render-result")` passes (`CodegenLegendSandboxTests`).

## Scenario B — legend + summary thread to the complete snapshot and artifact

Full codegen path (real sandbox worker + orchestration), `render_path: codegen`:

```json
{
  "summary": "Kitchen and basement with their average.",
  "legend": [
    { "label": "Kitchen", "entity_id": "sensor.a", "color": "#1f77b4", "kind": "series" },
    { "label": "Average", "entity_id": "sensor.a", "color": "#2ca02c", "kind": "computed" }
  ]
}
```

`artifact.legend == chart.legend`: **True** — the `_build_worker_artifact_metadata`
parity gap (it copied only `answer_text`) is closed; `snapshot_assembly` threads
both fields renderer-agnostically as before.

## Scenario C — computed vs overlay are distinct in the UI

Frontend Vitest (`isolinear-card-legend.test.ts`,
"gives a computed row a dashed swatch and a computed tag, no state children"):
a `kind: "computed"` row renders a `computed` tag (not `overlay`), a line-sample
swatch (`.swatch-line`) whose inline style is `border-top-style:dashed` in the row
color (`#2ca02c`), and zero `.legend-states li` children; a `series` row renders a
`border-top-style:solid` line sample and no tag. (0.2.43: the swatch is a short
horizontal line in the stroke style — a matplotlib-style legend handle — not a
bordered box; Colin's request after the 0.2.42 eyes-on.) The overlay row keeps its
split box swatch + per-state children. `npm test` → 37 passed.

## Scenario D — a missing legend never breaks the render (cosmetic-only)

- Sandbox: a chart-only render (`safe_generated_python`, no legend) →
  `"legend" not in render_metadata` is **True**; the render still `status: success`.
- A malformed row is dropped, not failed — a computed row with a non-hex color
  (`"tab:green"`) is removed and the render stays valid:

```json
{ "legend": [ { "label": "Kitchen", "entity_id": "sensor.a", "color": "#1f77b4", "kind": "series" } ] }
```

- Frontend: `renders no Legend section when the legend is absent` (existing test) —
  the card shows no legend section and does not error.

## Test coverage

- Python: `tests/test_model_authored_analysis.py` — `CodegenLegendSandboxTests` (3),
  `CodegenLegendEndToEndTests` (1), `CodegenLegendPromptRuleTests` (1),
  `CodegenLegendSchemaTests` (1). Full suite **565 passed**.
- Frontend: `frontend/src/isolinear-card-legend.test.ts` — **37 passed**; `npm run build` type-checks clean.
