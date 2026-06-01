# Rendering BDD

Scenarios for chart rendering (trusted renderer), dashboard card display, and render metadata.

## Scenarios

- **Chart spec rendering** — Trusted renderer converts valid chart specs to PNG with render metadata.
- **Shaded interval rendering** — Trusted renderer draws interval overlays (e.g., "dishwasher running") as shaded bands.
- **Dashboard card display** — Rendered chart is displayed in the Home Assistant dashboard card.

## Related docs

- Spec: [docs/specs/chart-spec-rendering-spec.md](../../docs/specs/chart-spec-rendering-spec.md)
- Spec: [docs/specs/dashboard-card-spec.md](../../docs/specs/dashboard-card-spec.md)
- ADR: [docs/decisions/0004-chart-spec-first-rendering-with-codegen-option.md](../../docs/decisions/0004-chart-spec-first-rendering-with-codegen-option.md)
- Source scenarios: [docs/bdd/chart-spec-rendering.feature](../../docs/bdd/chart-spec-rendering.feature)
- Source scenarios: [docs/bdd/dashboard-card.feature](../../docs/bdd/dashboard-card.feature)

## Validation

Evidence for these scenarios is produced by:

- `evals/prompt_to_chart_basic.py` — Full flow including trusted renderer (PNG output + metadata)
- `evals/shaded_interval_rendering.py` — Shaded interval band rendering and overlay IDs in metadata
- `tests/test_fake_vertical_slice.py` — Renderer and metadata validation

## Note on evidence format

Isolinear uses executable Python evals and unit tests rather than markdown evidence files. Each produces deterministic proof that the scenario was hit and the expected behavior occurred.
