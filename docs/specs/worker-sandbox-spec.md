# Worker and Sandbox Spec

## Purpose

The worker renders charts and runs sandboxed generated code. It is isolated from Home Assistant credentials and should run on modest hardware such as a Raspberry Pi.

## Worker modes

- Trusted renderer mode.
- Codegen sandbox mode.

## Worker API responsibilities

- Accept a `RenderRequest`.
- Validate request shape.
- Render a chart image.
- Return a `RenderResult` with image reference and render metadata.
- Return structured errors for failed requests.

## Sandbox requirements for generated code

Generated code must run with:

- No Home Assistant token.
- No network access.
- No arbitrary filesystem read access.
- Limited output directory.
- Fixed output path.
- Timeout.
- Memory limit.
- CPU limit where available.
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
