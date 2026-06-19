# Model Provider Spec

## Purpose

The model provider converts structured prompts into structured outputs for planning, optional code generation, optional repair, and optional visual validation.

## Provider roles

### Planner

Input:

- User prompt.
- Relevant semantic memory.
- Approved entity catalog.
- Clarification history.

Output:

- Planner result containing chart spec or clarifying question.

### Codegen

Input:

- Validated chart spec.
- Render data contract.
- Code safety rules.

Output:

- Python code implementing the fixed render entry point.

### Repair

Input:

- Chart spec.
- Generated code.
- Stack trace.
- Safety rules.

Output:

- Minimal corrected Python code.

### Visual validator

Input:

- User prompt.
- Chart spec.
- Render metadata.
- Image.

Output:

- Structured visual validation result.

## Model endpoint

The first provider should support an Ollama-compatible endpoint. The model may run on another machine.

## Structured output

Where possible, model responses should be constrained by JSON schemas. Free-form prose should be reserved for user-facing explanations and failure messages.

The chart-spec `source.entity_id` in the planner's structured-output schema is
pinned to an `enum` of exactly the entities the integration disclosed for the
job (`load_planner_result_schema(family, entity_ids=...)`). Constrained decoding
therefore cannot emit an off-allowlist entity, so a hallucinated entity is a
structural impossibility rather than a post-plan
`model_provider_referenced_unapproved_entity` failure (ADR-0022, allowlist
invariant). When no entities are disclosed the field falls back to a free string.
The deterministic post-plan entity-validation gate is retained as defence in
depth.

## Observability

The Ollama planner client logs the outgoing request body and the raw provider
response at `DEBUG` on the `custom_components.isolinear.model_provider` logger,
so new chart families can be diagnosed without a packet capture. These logs are
off by default and contain the user prompt, disclosed entity IDs, and the model's
chart-spec output; no tokens or secrets travel the planner path (local Ollama, no
auth). Transport errors are also logged at `DEBUG` before the sanitized failure
is returned.

## Failure behavior

Provider failures must be reported with:

- Provider role.
- Endpoint/model used.
- Error type.
- Whether retry is safe.
