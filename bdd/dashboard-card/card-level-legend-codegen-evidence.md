# Card-level legend for the codegen render path (+ computed kind) — Evidence

Paired with [docs/specs/card-level-legend-codegen.md](../../docs/specs/card-level-legend-codegen.md)
and [card-level-legend-codegen-bdd.md](card-level-legend-codegen-bdd.md). Raw
outputs, captured 2026-07-17 at version 0.2.42.

Status: the Python/schema/frontend scenarios (B, C, D) are proven here on the real
sandbox + orchestration + frontend. **Scenario A's live card eyes-on is pending a
worker rebuild + HACS 0.2.42 redownload** — the legend passthrough is a WORKER-side
change (`_normalize_render_metadata`), so it does not go live until the worker
image is rebuilt on CT103.

## Scenario A (partial) — the sandbox preserves the self-reported legend manifest

`invoke_codegen_sandbox` on a `render_chart` that returns a two-row legend (a solid
raw sensor + a dashed computed average), executed for real:

```json
{
  "status": "success",
  "legend": [
    { "label": "Kitchen", "entity_id": "sensor.a", "color": "#1f77b4", "kind": "series" },
    { "label": "Average", "entity_id": "sensor.a", "color": "#2ca02c", "kind": "computed" }
  ],
  "summary": "Kitchen and basement with their average."
}
```

Before this packet, `_normalize_render_metadata` rebuilt the metadata from a fixed
key set and dropped both `legend` and `summary`. The render-result contract
validates with the additive `computed` kind (`validate_contract("render-result")`
passes in `CodegenLegendSandboxTests`). The remaining half of Scenario A — the
dashed line in the PNG and the `computed` row on the live card — is the deploy-time
eyes-on.

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
a `kind: "computed"` row renders a `computed` tag (not `overlay`), a swatch whose
inline style contains `dashed` and the row color (`#2ca02c`), and zero
`.legend-states li` children; the plain `series` rows carry no tag. The overlay row
(existing test) keeps its split swatch + per-state children. `npm test` → 37 passed.

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
