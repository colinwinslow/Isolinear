# Worker and Sandbox Spec

## Purpose

The worker renders charts and runs sandboxed generated code. It is isolated from Home Assistant credentials and should run on modest hardware such as a Raspberry Pi.

## Worker modes

- Trusted renderer mode.
- Codegen sandbox mode.

## Concrete sandbox strategy

The MVP worker sandbox strategy for generated Python is:

1. Validate the `RenderRequest`, `ChartSpec`, `HistorySeries`, and
   `CodegenSandboxPolicy` schemas before any generated code runs.
2. Run static AST safety checks before execution. Generated code must define
   exactly one `render_chart(data, output_path)` function. Top-level execution
   is limited to imports and function definitions.
3. Allow only the configured import allowlist. The first codegen release allows
   small standard-library helpers plus matplotlib modules that are expected to
   be installed in the worker image. Imports such as `os`, `pathlib`, `socket`,
   `subprocess`, `requests`, `urllib`, `http`, `ssl`, and `importlib` are
   forbidden.
4. Execute generated code in an isolated Python subprocess using `-I`, a
   stripped environment, a temporary working directory, and no Home Assistant
   token or worker bearer token.
5. Install a runtime audit hook in the child process. It denies socket,
   subprocess, OS mutation, and filesystem events outside the sandbox policy.
6. Provide generated code only the normalized render data and the fixed
   `output_path`. The only allowed generated-code file write is opening that
   exact path for writing.
7. Enforce timeout in the parent process. On Linux/Raspberry Pi, request CPU
   and address-space limits through Python's standard `resource` module when
   available; on development platforms without `resource`, timeout remains the
   fail-closed guard and the result records that platform limitation.
8. Enforce `max_output_bytes` after execution and fail as `output_too_large`
   if the file exceeds policy.

This strategy does not require GPU support. Matplotlib must use a noninteractive
backend such as `Agg`. The repo-local anchor is standard-library-only so it can
run in the current development environment even when matplotlib is not
installed; production worker packaging is responsible for providing matplotlib
inside the isolated worker runtime.

## Worker API responsibilities

- Accept a `RenderRequest`.
- Validate request shape.
- Render a chart image.
- Return a `RenderResult` with image reference and render metadata.
- Return structured errors for failed requests.

## Sandbox requirements for generated code

Generated code must run with:

- No Home Assistant token or worker bearer token in environment or input data.
- No local network or internet access.
- No arbitrary filesystem read access outside worker runtime roots.
- No arbitrary filesystem write access.
- Limited output directory.
- Fixed output path.
- Timeout.
- Memory limit on Linux/Raspberry Pi where available.
- CPU limit on Linux/Raspberry Pi where available.
- Import allowlist.
- Max output image size.

## Code entry point

Generated Python must implement:

```python
def render_chart(data: dict, output_path: str) -> dict:
    """Render a chart and return metadata."""
```

The returned metadata must include plotted series, plotted overlays, title, time range, and warnings.

## Error handling

The worker should return structured errors:

- `invalid_request`
- `unsupported_chart_spec`
- `unsafe_code`
- `runtime_error`
- `timeout`
- `output_missing`
- `output_too_large`
- `validation_failed`

## Raspberry Pi compatibility

The worker must avoid assuming GPU availability. It should use standard Python and matplotlib for rendering. Heavy model inference is expected to run elsewhere.

The sandbox anchor is implemented in
`src/Isolinear/codegen_sandbox_anchor.py` and is validated by:

- `docs/schemas/codegen-sandbox-policy.schema.json`
- `tests/test_codegen_sandbox_anchor.py`
- `evals/codegen_sandbox.py`
- `bdd/sandbox-codegen/sandbox-codegen-bdd.md`
