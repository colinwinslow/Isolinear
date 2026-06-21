# Rendering BDD

Scenarios for chart rendering (trusted renderer), dashboard card display, and render metadata.

## Scenarios

- **Chart spec rendering** — Trusted renderer converts valid chart specs to PNG with render metadata.
- **Shaded interval rendering** — Trusted renderer draws interval overlays (e.g., "dishwasher running") as shaded bands.
- **State interval timeline** — Trusted renderer draws binary/categorical state intervals as timeline tracks.
- **Aggregate bar chart** — Trusted renderer draws one aggregate numeric value per source entity as bars.
- **Calendar hour heatmap** — Trusted renderer groups numeric entity history into weekday-by-hour cells.
- **Event markers** — Trusted renderer draws point-in-time markers over a numeric time-series chart.
- **Distribution histogram** — Trusted renderer bins numeric entity history into value-frequency bars.
- **Scatter/correlation** — Trusted renderer plots paired numeric entity values by exact matching timestamps.
- **Render family capability envelope** — Integration computes the deterministic set of families the data shape supports; the model picks within it from intent; out-of-envelope choices fail closed; sparse data renders fail-soft (ADR-0023, draft).
- **Dashboard card display** — Rendered chart is displayed in the Home Assistant dashboard card.

## Related docs

- Spec: [docs/specs/chart-spec-rendering-spec.md](../../docs/specs/chart-spec-rendering-spec.md)
- Spec: [docs/specs/dashboard-card-spec.md](../../docs/specs/dashboard-card-spec.md)
- ADR: [docs/decisions/0004-chart-spec-first-rendering-with-codegen-option.md](../../docs/decisions/0004-chart-spec-first-rendering-with-codegen-option.md)
- Source scenarios: [docs/bdd/chart-spec-rendering.feature](../../docs/bdd/chart-spec-rendering.feature)
- Source scenarios: [docs/bdd/dashboard-card.feature](../../docs/bdd/dashboard-card.feature)
- Paired BDD: [trusted-rendering-bdd.md](trusted-rendering-bdd.md)
- Evidence: [trusted-rendering-evidence.md](trusted-rendering-evidence.md)
- Spec: [docs/specs/render-family-capability-envelope.md](../../docs/specs/render-family-capability-envelope.md)
- ADR: [docs/decisions/0023-model-proposed-render-family-within-capability-envelope.md](../../docs/decisions/0023-model-proposed-render-family-within-capability-envelope.md)
- Paired BDD: [render-family-capability-envelope-bdd.md](render-family-capability-envelope-bdd.md)

## Validation

Evidence for these scenarios is produced by:

- `evals/trusted_renderer_primitives.py` — Trusted renderer primitive scope and unsupported safe-mode rejection without codegen
- `evals/state_interval_timeline.py` — Selected follow-up timeline family renders state interval tracks without codegen
- `evals/aggregate_bar_chart.py` — Selected follow-up aggregate bar family renders numeric entity aggregates without codegen
- `evals/calendar_hour_heatmap.py` — Selected follow-up heatmap family renders weekday-by-hour numeric entity cells without codegen
- `evals/event_markers.py` — Selected follow-up marker family renders event annotations without codegen
- `evals/distribution_histogram.py` — Selected follow-up histogram family renders numeric value distributions without codegen
- `evals/scatter_correlation.py` — Selected follow-up scatter family renders paired numeric values without codegen
- `evals/prompt_to_chart_basic.py` — Full flow including trusted renderer (PNG output + metadata)
- `evals/shaded_interval_rendering.py` — Shaded interval band rendering and overlay IDs in metadata
- `tests/test_fake_vertical_slice.py` — Renderer and metadata validation

## Evidence format

Executable evals and unit tests provide deterministic behavior checks. Paired markdown evidence captures the raw commands, outputs, fixtures, and observed results for review.
