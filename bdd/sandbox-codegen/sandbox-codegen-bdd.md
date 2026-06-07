# Sandbox Codegen Anchor - BDD

## Status

Accepted. Paired with
[docs/specs/worker-sandbox-spec.md](../../docs/specs/worker-sandbox-spec.md).

Evidence file:

- `bdd/sandbox-codegen/sandbox-codegen-evidence.md`

## Why This BDD Exists

This BDD pins down the optional generated-code path. The trusted renderer stays
the default, but when codegen is enabled, generated Python must run through a
small, inspectable sandbox contract that is compatible with Raspberry Pi worker
hardware and fails closed for secrets, filesystem, network, and runaway output.

## Scenarios

### Scenario A - sandbox policy is Raspberry Pi compatible

**Given** codegen mode is enabled for the worker
**When** the worker loads the default sandbox policy
**Then** the policy should use an isolated Python subprocess
**And** the policy should require a noninteractive rendering backend
**And** the policy should enforce timeout, fixed output path, import allowlist,
and output size limits
**And** Linux workers should request CPU and memory limits where the platform
supports them

### Scenario B - generated code renders through the fixed entry point

**Given** a valid chart spec and normalized history payload
**And** generated Python defines `render_chart(data, output_path)`
**When** the worker runs codegen mode
**Then** the code should run in the sandbox
**And** the output image should be written only to the fixed output path
**And** the render result should include metadata returned by the function

### Scenario C - allowlisted matplotlib pyplot renders with Agg backend

**Given** generated Python imports `matplotlib.pyplot`
**When** the worker runs codegen mode
**Then** the code should render a PNG through the sandbox
**And** the render metadata should report the `Agg` backend
**And** the output image should be written only to the fixed output path

### Scenario D - unsafe generated code is rejected before execution

**Given** generated Python attempts to import a forbidden module such as
`requests`
**When** the worker performs static safety checks
**Then** the worker should reject the code as `unsafe_code`
**And** the code should not execute

### Scenario E - secret, filesystem, and network access fail closed

**Given** generated Python attempts to read secrets, inspect environment
variables, open a local network socket, or route arbitrary file reads through
an allowlisted rendering library
**When** the worker performs static sandbox checks or runtime audit checks
**Then** the worker should reject or deny the attempt with a structured failure
**And** the target resource should not be read
**And** the code should not produce a successful render artifact

### Scenario F - oversized output fails after execution

**Given** generated Python writes an output larger than the sandbox policy
allows
**When** the worker runs codegen mode
**Then** the worker should return `output_too_large`
**And** the render result should not expose the oversized image as a successful
artifact

### Scenario G - runtime error triggers capped repair loop

**Given** generated Python raises a matplotlib/runtime exception
**When** codegen repair is enabled with max attempts 2
**Then** the system should send the stack trace to the repair model
**And** it should retry no more than 2 times
**And** it should rerun static safety checks for every repaired code attempt
**And** it should return a failure if all attempts fail

## Evidence

The implementing slice produces raw outputs from
`tests/test_codegen_sandbox_anchor.py` and `evals/codegen_sandbox.py`.
