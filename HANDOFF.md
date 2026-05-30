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

Fake-provider vertical slice implemented as a local Python module with schema-backed contract validation and a pre-render plan validation gate. No Home Assistant integration has been built yet.

## Next recommended packet

Add render metadata validation for expected overlays:

1. Extend deterministic validation to fail when a chart spec expects overlays that render metadata does not list.
2. Add BDD-derived coverage for the validation-loop "Missing overlay fails validation" scenario.
3. Keep trusted rendering of shaded intervals deferred unless the test requires only validation behavior.
4. Keep the Home Assistant integration deferred until the fake planning/rendering contracts are stable.

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
