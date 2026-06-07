# Integration BDD

This folder contains paired markdown BDD and evidence files for Home Assistant
custom integration implementation slices.

## Scenarios

- **Home Assistant integration scaffold anchor** - the first production
  `custom_components/isolinear` package exists, exposes local-first
  configuration shapes, accepts known versioned command stubs, and rejects
  unknown, leaky, or mutating command payloads before orchestration.

## Validation

- `evals/home_assistant_integration_scaffold.py` - scaffold manifest,
  configuration shape, command-boundary acceptance/rejection, and
  non-orchestration proof.
