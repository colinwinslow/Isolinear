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

## Failure behavior

Provider failures must be reported with:

- Provider role.
- Endpoint/model used.
- Error type.
- Whether retry is safe.
