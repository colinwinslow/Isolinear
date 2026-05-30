# HANDOFF.md

## Current project phase

Seed phase. The repo is being prepared with ADRs, specs, BDD scenarios, schemas, eval outlines, and Codex working rules before production implementation.

## Product summary

Isolinear lets a user ask natural-language questions about approved Home Assistant entities and receive generated data visualizations based on entity history.

## Current architecture direction

- Home Assistant custom integration.
- Custom dashboard card as the first UI.
- Optional Home Assistant add-on worker for rendering and sandbox execution.
- Standalone worker mode should remain possible for Home Assistant installs that cannot use add-ons.
- Model provider should be Ollama-compatible, with local-first defaults and optional stronger providers later.
- Trusted chart-spec renderer is the default path.
- Sandboxed matplotlib codegen is an advanced path.

## Open implementation status

Fake-provider vertical slice implemented as a local Python module with schema-backed contract validation, a pre-render plan validation gate, deterministic render metadata validation, trusted safe-mode rendering for shaded interval overlays, and fake binary-state interval extraction. No Home Assistant integration has been built yet.

## Next recommended packet

Add deterministic threshold-derived interval extraction for confirmed numeric rules:

1. Add fake normalized dishwasher power history for `sensor.dishwasher_power`.
2. Add a confirmed threshold rule path, such as `value > 5 W`.
3. Convert continuous numeric history into schema-valid `DerivedInterval` payloads for ranges where the rule is true.
4. Add BDD-derived coverage for the confirmed threshold interval scenario.
5. Keep planner threshold clarification and the Home Assistant integration deferred until the deterministic interval extraction contract is stable.

## Known unresolved design details

- Exact Home Assistant integration storage mechanism for semantic memory.
- Exact dashboard card implementation technology.
- Exact worker API transport and authentication.
- Exact sandbox implementation details for Raspberry Pi compatibility.
- Which chart primitives are included in the first trusted renderer release.

## Session notes

- 2026-05-29: Renamed product references across the repo to Isolinear.
- 2026-05-29: Reversed the temporary PowerShell implementation decision after confirming Python 3.14.5 at `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe`.
- 2026-05-29: Added `src/Isolinear/fake_slice.py` with a fake approved entity catalog, fake normalized 24-hour history, deterministic planner stub, trusted PNG renderer, render metadata, and deterministic validation.
- 2026-05-29: Added `tests/test_fake_vertical_slice.py` and `evals/prompt_to_chart_basic.py`.
- Tests run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe tests\test_fake_vertical_slice.py`.
- Evals run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\prompt_to_chart_basic.py`.
- Note: The Windows Store `python.exe` launcher still appears first on PATH and fails; use the direct Python path above until PATH is adjusted.
- 2026-05-29: Added `src/Isolinear/contracts.py` with dependency-free validation for the JSON Schema subset used by the current contracts.
- 2026-05-29: Updated fake slice tests and the executable prompt-to-chart eval to validate catalog items, history series, planner result, nested chart spec, render request, render result, validation result, and unsupported safe-mode render failure against schemas.
- Tests run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe tests\test_fake_vertical_slice.py`.
- Evals run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\prompt_to_chart_basic.py`.
- 2026-05-29: Added a pre-render plan validation gate for chart spec schema validity and allowlisted source entities.
- 2026-05-29: Added `docs/evals/plan_validation_rejects_hidden_entity.yaml` and `evals/plan_validation_rejects_hidden_entity.py` for the BDD-derived hidden-entity failure path.
- 2026-05-29: Plan validation now returns a schema-valid deterministic failure and does not create render requests, render results, or image artifacts when chart specs are schema-invalid or reference non-allowlisted entities.
- Tests run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe tests\test_fake_vertical_slice.py`.
- Evals run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\prompt_to_chart_basic.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\plan_validation_rejects_hidden_entity.py`.
- 2026-05-30: Added deterministic validation for expected overlays in render metadata.
- 2026-05-30: Added `docs/evals/missing_overlay_validation.yaml` and `evals/missing_overlay_validation.py` for the BDD-derived missing-overlay validation path.
- 2026-05-30: Validation now fails with a `rendered_overlays` check and `missing_overlay_ids` details when a chart spec expects overlays missing from `render_metadata.overlays_plotted`.
- Tests run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe tests\test_fake_vertical_slice.py`.
- Evals run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\prompt_to_chart_basic.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\plan_validation_rejects_hidden_entity.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\missing_overlay_validation.py`.
- 2026-05-30: Added trusted safe-mode renderer support for `shaded_intervals` overlays backed by matching `DerivedInterval` payloads.
- 2026-05-30: Added `docs/evals/shaded_interval_rendering.yaml` and `evals/shaded_interval_rendering.py` for the BDD-derived positive shaded-interval render path.
- 2026-05-30: Renderer now draws shaded interval bands before plotting series and includes plotted overlay IDs in `render_metadata.overlays_plotted`.
- Tests run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe tests\test_fake_vertical_slice.py`.
- Evals run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\prompt_to_chart_basic.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\plan_validation_rejects_hidden_entity.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\missing_overlay_validation.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\shaded_interval_rendering.py`.
- 2026-05-30: Added fake `binary_sensor.dishwasher` catalog metadata and deterministic binary-state history.
- 2026-05-30: Added `extract_state_intervals` to convert active `"on"` state changes into schema-valid `DerivedInterval` payloads.
- 2026-05-30: Added `docs/evals/binary_state_interval_extraction.yaml` and `evals/binary_state_interval_extraction.py` for the BDD-derived binary interval extraction path.
- Tests run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe tests\test_fake_vertical_slice.py`.
- Evals run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\prompt_to_chart_basic.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\plan_validation_rejects_hidden_entity.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\missing_overlay_validation.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\shaded_interval_rendering.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\binary_state_interval_extraction.py`.
- 2026-05-30: Added fake raw numeric temperature history records containing numeric strings, `unknown`, and `unavailable` states.
- 2026-05-30: Added deterministic numeric history normalization that converts numeric strings to floats, converts `unknown` and `unavailable` states to null values with matching point quality, preserves `raw_state`, and emits series-level data-quality warnings.
- 2026-05-30: Added `docs/evals/numeric_history_normalization.yaml` and `evals/numeric_history_normalization.py` for the BDD-derived numeric string and missing-value normalization path.
- Tests run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe tests\test_fake_vertical_slice.py`.
- Evals run: `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\prompt_to_chart_basic.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\plan_validation_rejects_hidden_entity.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\missing_overlay_validation.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\shaded_interval_rendering.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\binary_state_interval_extraction.py`; `C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals\numeric_history_normalization.py`.
