# Integration Spec

## Purpose

The Home Assistant custom integration owns configuration, entity visibility, prompt orchestration, model-provider calls, semantic memory, history retrieval, and communication with the worker.

## Responsibilities

- Provide configuration flow for model endpoint, worker endpoint, render mode, and defaults.
- Provide options flow for entity allowlist and advanced settings.
- Build the allowlisted entity catalog.
- Store user-confirmed semantic aliases and derived rules.
- Send structured prompts to the model provider.
- Validate model outputs against schemas.
- Retrieve Home Assistant history for selected entities.
- Normalize history into chart-ready contracts.
- Submit render requests to the worker.
- Store chart artifacts or references returned by the worker.
- Serve dashboard-card state and results.

## Non-responsibilities

- Running generated matplotlib code directly.
- Allowing generated code to call Home Assistant APIs.
- Performing heavy model inference locally unless the user has configured that host.
- Mutating Home Assistant devices, automations, scenes, or services.

## Configuration

The MVP configuration should include:

- Model provider type: initially `ollama_compatible`.
- Model endpoint URL.
- Planner model name.
- Optional codegen model name.
- Optional visual validator model name.
- Worker endpoint URL.
- Default render mode: `safe`, `codegen`, or `auto`.
- Max codegen repair attempts.
- Entity allowlist.

## State model

The integration should expose job state to the dashboard card:

- `idle`
- `planning`
- `clarification_needed`
- `fetching_history`
- `rendering`
- `validating`
- `complete`
- `failed`

## Failure behavior

Failures should be user-readable and should include:

- Stage that failed.
- Whether retry is possible.
- Whether clarification is needed.
- Whether the failure was caused by model output, missing data, unsafe code, render failure, or validation mismatch.
