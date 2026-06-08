# Integration BDD

This folder contains paired markdown BDD and evidence files for Home Assistant
custom integration implementation slices.

## Scenarios

- **Home Assistant integration scaffold anchor** - the first production
  `custom_components/isolinear` package exists, exposes local-first
  configuration shapes, accepts known versioned command stubs, and rejects
  unknown, leaky, or mutating command payloads before orchestration.
- **Home Assistant config flow/options anchor** - the integration exposes a
  Home Assistant config-flow and options-flow surface that persists validated
  local-first setup data while rejecting invalid or secret-bearing input before
  orchestration.
- **Home Assistant dashboard resource registration anchor** - the integration
  serves and registers the existing `isolinear-card` bundle as a dashboard
  module resource while preserving idempotence and orchestration boundaries.

## Validation

- `evals/home_assistant_integration_scaffold.py` - scaffold manifest,
  configuration shape, command-boundary acceptance/rejection, and
  non-orchestration proof.
- `evals/home_assistant_config_flow_options.py` - config-flow activation,
  config-entry data normalization, options normalization, invalid-input
  rejection, and non-orchestration proof.
- `evals/home_assistant_dashboard_resource_registration.py` - static path
  registration, Lovelace resource metadata creation/reuse, idempotence,
  missing-bundle rejection, and non-orchestration proof.
