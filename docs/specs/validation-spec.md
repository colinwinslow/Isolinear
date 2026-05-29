# Validation Spec

## Purpose

Validation determines whether the system produced a safe, useful chart that matches the prompt, clarifications, chart spec, and available data.

## Validation layers

### 1. Plan validation

Before rendering:

- All source entities exist in the allowlist.
- Time range is valid.
- Requested series types are compatible with chart roles.
- Aggregations are defined.
- Required thresholds or state rules are confirmed.
- The chart spec validates against schema.

### 2. Code safety validation

For codegen mode:

- Imports are allowlisted.
- Network calls are forbidden.
- Arbitrary file reads are forbidden.
- Home Assistant API access is forbidden.
- Entry point signature exists.
- Output path is fixed.

### 3. Runtime validation

After execution:

- Code exits successfully.
- Image file exists.
- Image is non-empty.
- Image size is within limits.
- Renderer returned metadata.

### 4. Render metadata validation

Check:

- Expected series were plotted.
- Expected overlays were plotted.
- Time range matches request.
- Units are consistent or warnings are emitted.
- Data gaps are reported.

### 5. Visual validation

Optional multimodal validation may inspect the image and return structured findings. Visual validation is advisory and should not override deterministic failures.

## Repair loop

In codegen mode, runtime errors may trigger a repair loop:

1. Capture code, chart spec, request data summary, and stack trace.
2. Ask the model for a minimal fix.
3. Re-run static checks.
4. Re-run sandbox.
5. Stop after configured max attempts.

## Validation result

Every chart job should produce a `ValidationResult` with:

- Overall status.
- Passed checks.
- Failed checks.
- Warnings.
- Repair attempts.
- Whether visual validation was run.
