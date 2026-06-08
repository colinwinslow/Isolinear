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
- **Home Assistant WebSocket command registration anchor** - the integration
  registers the accepted `isolinear/v1/` card-facing command set through Home
  Assistant's WebSocket API while preserving config-entry scope, idempotence,
  scaffold snapshots, and non-orchestration boundaries.
- **Home Assistant job state scaffold anchor** - the integration owns a
  deterministic in-memory job snapshot store behind the registered WebSocket
  commands while preserving config-entry isolation, unknown-job rejection,
  unload cleanup, and non-orchestration boundaries.
- **Home Assistant approved history retrieval scaffold anchor** - the
  integration owns a config-entry-scoped approved history store that reads fake
  Home Assistant history only after the approved catalog gate passes and stores
  schema-valid `HistorySeries` records.
- **Home Assistant job orchestration scaffold anchor** - the integration owns a
  config-entry-scoped `job/start` scaffold that composes job state, the approved
  entity catalog, and approved fake history while preserving model, worker,
  rendering, mutation, memory, token, artifact, durable-storage, and real
  orchestration boundaries.
- **Home Assistant job orchestration retry continuation scaffold anchor** - the
  integration owns a config-entry-scoped `job/retry` scaffold that resumes a
  retryable failed job through approved catalog and approved fake history while
  preserving model, worker, rendering, mutation, memory, token, artifact,
  durable-storage, streaming, automatic-retry, worker-retry, and production
  orchestration boundaries.
- **Home Assistant job orchestration artifact storage scaffold anchor** - the
  integration owns a config-entry-scoped `job/snapshot` scaffold that records
  placeholder artifact metadata for scaffold-ready jobs while preserving
  model, worker, rendering, mutation, memory, token, real artifact file,
  durable-storage, streaming, retry, and production orchestration boundaries.

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
- `evals/home_assistant_websocket_command_registration.py` - WebSocket command
  registration, setup-entry storage, accepted scaffold snapshot responses,
  fail-closed invalid commands, missing config-entry scope, idempotence, and
  non-orchestration proof.
- `evals/home_assistant_job_state_scaffold.py` - deterministic job and
  snapshot IDs, start/snapshot/retry/clarification/subscribe behavior,
  per-config-entry isolation, unknown-job rejection, unload cleanup, and
  non-orchestration proof.
- `evals/home_assistant_approved_history_retrieval_scaffold.py` - approved
  catalog enforcement, schema-valid history retrieval, per-config-entry
  isolation, malformed-history rejection, stale-store clearing, and
  non-orchestration proof.
- `evals/home_assistant_job_orchestration_scaffold.py` - deterministic
  `job/start` state transitions, approved catalog/history composition,
  catalog-gate failure, missing approved history failure, per-config-entry
  isolation, schema-valid snapshots, and bounded side-effect proof.
- `evals/home_assistant_job_orchestration_retry_continuation_scaffold.py` -
  deterministic `job/retry` continuation transitions for retryable failed jobs,
  unknown-job and non-retryable rejection, per-config-entry isolation,
  schema-valid snapshots, and bounded side-effect proof.
- `evals/home_assistant_job_orchestration_artifact_storage_scaffold.py` -
  deterministic placeholder artifact metadata creation for scaffold-ready jobs,
  idempotent snapshot retrieval, unknown-job and cross-entry rejection,
  per-config-entry isolation, schema-valid snapshots/artifact metadata, and
  bounded side-effect proof.
