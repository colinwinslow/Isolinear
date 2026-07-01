# Codegen generation path — BDD evidence (ADR-0029 packet 4)

Raw outputs for the scenarios in
[codegen-generation-path-bdd.md](codegen-generation-path-bdd.md). Proven
**locally** (no CT103 / remote host): unit tests exercise the full integration
orchestration against an in-process sandbox worker; the eval boots the real
packet-2 `isolinear_worker.http_server` on an ephemeral port and drives the
generate → dispatch → repair loop over the actual HTTP boundary.

Environment note: the `-I` sandbox cannot import matplotlib on the dev box
(documented packet-1 limitation), so the matplotlib-over-wire variant is
`skipUnless`-gated; the safe (non-matplotlib) generated body carries the
real-PNG proof everywhere.

## Unit suite — raw `pytest -v`

```
$ python3 -m pytest tests/test_codegen_generation_path.py -v
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.4.2, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/claude/repos/isolinear
plugins: anyio-4.14.1
collecting ... collected 26 items

tests/test_codegen_generation_path.py::CodegenConfigSurfaceTests::test_codegen_enabled_defaults_false PASSED [  3%]
tests/test_codegen_generation_path.py::CodegenConfigSurfaceTests::test_codegen_enabled_is_an_options_field PASSED [  7%]
tests/test_codegen_generation_path.py::CodegenConfigSurfaceTests::test_codegen_helper_reads_toggle PASSED [ 11%]
tests/test_codegen_generation_path.py::CodegenConfigSurfaceTests::test_codegen_model_defaults_to_planner_when_unset PASSED [ 15%]
tests/test_codegen_generation_path.py::CodegenConfigSurfaceTests::test_codegen_model_honored_when_set PASSED [ 19%]
tests/test_codegen_generation_path.py::CodegenConfigSurfaceTests::test_non_boolean_codegen_enabled_rejected PASSED [ 23%]
tests/test_codegen_generation_path.py::CodegenConfigSurfaceTests::test_options_form_normalizes_string_boolean PASSED [ 26%]
tests/test_codegen_generation_path.py::CodegenConfigSurfaceTests::test_valid_options_accept_codegen_enabled_true PASSED [ 30%]
tests/test_codegen_generation_path.py::CodegenSetupTests::test_disabled_installs_no_codegen_client PASSED [ 34%]
tests/test_codegen_generation_path.py::CodegenSetupTests::test_enabled_honors_separate_codegen_model PASSED [ 38%]
tests/test_codegen_generation_path.py::CodegenSetupTests::test_enabled_installs_codegen_client_defaulting_to_planner PASSED [ 42%]
tests/test_codegen_generation_path.py::CodegenModelProviderTests::test_data_boundary_no_secret_in_codegen_prompt PASSED [ 46%]
tests/test_codegen_generation_path.py::CodegenModelProviderTests::test_generate_chart_code_returns_stripped_freeform_code PASSED [ 50%]
tests/test_codegen_generation_path.py::CodegenModelProviderTests::test_generate_chart_code_uses_model_override PASSED [ 53%]
tests/test_codegen_generation_path.py::CodegenModelProviderTests::test_generate_empty_response_is_retry_safe_failure PASSED [ 57%]
tests/test_codegen_generation_path.py::CodegenModelProviderTests::test_generate_transport_error_is_provider_failure PASSED [ 61%]
tests/test_codegen_generation_path.py::CodegenModelProviderTests::test_repair_chart_code_feeds_previous_code_and_error PASSED [ 65%]
tests/test_codegen_generation_path.py::CodegenOrchestrationTests::test_codegen_model_default_and_override_are_threaded_to_client PASSED [ 69%]
tests/test_codegen_generation_path.py::CodegenOrchestrationTests::test_disabled_leaves_trusted_path_untouched PASSED [ 73%]
tests/test_codegen_generation_path.py::CodegenOrchestrationTests::test_enabled_happy_path_generates_renders_and_serves_png PASSED [ 76%]
tests/test_codegen_generation_path.py::CodegenOrchestrationTests::test_generation_failure_fails_closed_without_dispatch PASSED [ 80%]
tests/test_codegen_generation_path.py::CodegenOrchestrationTests::test_repair_exhausted_fails_closed PASSED [ 84%]
tests/test_codegen_generation_path.py::CodegenOrchestrationTests::test_retryable_failure_repairs_to_success PASSED [ 88%]
tests/test_codegen_generation_path.py::CodegenOrchestrationTests::test_unsafe_code_fails_closed_immediately_without_repair PASSED [ 92%]
tests/test_codegen_generation_path.py::CodegenLocalWorkerWireTests::test_generated_matplotlib_renders_over_local_worker SKIPPED [ 96%]
tests/test_codegen_generation_path.py::CodegenLocalWorkerWireTests::test_safe_generated_body_renders_over_local_worker PASSED [100%]

======================== 25 passed, 1 skipped in 1.19s =========================
```

The skip is the matplotlib-over-`-I`-sandbox dev-box limitation (runs on the
worker container). Full suite: `620 passed, 4 skipped` (595 prior + 25 new; 3
prior skips + 1 new matplotlib skip).

## Scenario A — enabled codegen generates code, worker renders a PNG over HTTP

Raw eval case (fake model emits code → real packet-2 worker on an ephemeral
port renders `render_mode: "codegen"` to a real PNG; authorization redacted):

```
CASE generation_happy_path_renders_png_over_http
{
  "case_id": "generation_happy_path_renders_png_over_http",
  "given": {
    "endpoint_url": "http://127.0.0.1:46699",
    "generate_calls": 1,
    "request": {
      "body": {
        "operation": "render_chart",
        "render_request": {
          "codegen": {
            "max_repair_attempts": 2,
            "python_code": "def render_chart(data, output_path):\n    png_bytes = bytes.fromhex(\"89504e...\")\n    with open(output_path, \"wb\") as image_file:\n        image_file.write(png_bytes)\n    return { ... }"
          },
          "render_mode": "codegen",
          "request_id": "codegen-sandbox-anchor",
          ...
        },
        "request_id": "codegen-eval-1",
        "version": 1
      },
      "headers": {
        "authorization": "Bearer <redacted>",
        "content_type": "application/json",
        "x_isolinear_worker_api_version": "1"
      },
      "method": "POST",
      "path": "/v1/render",
      "protocol_version": 1
    },
    "run_timestamp": "2026-07-01T21:23:32+00:00"
  },
  "then": {
    "authorization_sent": "Bearer <redacted>",
    "image_signature_hex": "89504e470d0a1a0a",
    "render_status": "success",
    "repair_calls": []
  },
  "when": { "operation": "generate -> POST /v1/render (render_mode=codegen)" }
}
PASS generation_happy_path_renders_png_over_http
```

`image_signature_hex == 89504e470d0a1a0a` is the PNG magic number: a real PNG
was written to disk by the worker sandbox. Unit
`test_enabled_happy_path_generates_renders_and_serves_png` additionally proves
the integration serves that PNG through the existing artifact path (snapshot
status `complete`, `image_url` ending `.png`, PNG on disk in the artifact dir).

## Scenario B — retryable failure repairs to success

```
CASE retryable_failure_repairs_to_success
{
  "case_id": "retryable_failure_repairs_to_success",
  "given": { "initial_error_code": "runtime_error", "max_repair_attempts": 1 },
  "then": {
    "dispatch_count": 2,
    "final_render_status": "success",
    "image_signature_hex": "89504e470d0a1a0a",
    "repair_error_codes_fed": ["runtime_error"]
  },
  "when": { "operation": "generate -> render(fail) -> repair -> render(success)" }
}
PASS retryable_failure_repairs_to_success
```

Two dispatches (initial + repaired); the integration fed the retryable
`runtime_error` to `repair_chart_code`; the second render produced a real PNG.
Unit `test_retryable_failure_repairs_to_success` proves the same through the full
orchestration with the served artifact.

## Scenario C — exhausted repair fails closed (no silent fallback)

Unit `test_repair_exhausted_fails_closed`: with `max_codegen_repair_attempts=2`
and every attempt failing at runtime, the job snapshot is `failed` with
`failure.code == "codegen_render_failed"`; exactly 3 dispatches (initial + 2
repairs) and 2 repair calls; the trusted renderer never produced this card (no
`in_process` in the failure payload). Full suite green.

## Scenario D — `unsafe_code` fails closed immediately, no repair

Raw eval case:

```
CASE unsafe_code_is_terminal_no_repair
{
  "case_id": "unsafe_code_is_terminal_no_repair",
  "given": { "generated_code": "import requests (forbidden import)" },
  "then": {
    "final_render_status": "failed",
    "final_error_code": "unsafe_code",
    "dispatch_count": 1,
    "repair_calls": []
  },
  "when": { "operation": "generate -> render(unsafe_code)" }
}
PASS unsafe_code_is_terminal_no_repair
```

Exactly one dispatch, zero repair calls: `unsafe_code` is terminal. Unit
`test_unsafe_code_fails_closed_immediately_without_repair` proves the same
through the full orchestration (snapshot `failed`, `codegen_render_failed`, no
`repair_chart_code` call despite repair budget available).

## Scenario E — disabled leaves the trusted path unchanged

Unit `test_disabled_leaves_trusted_path_untouched`: with `codegen_enabled:
false` (no codegen client installed) the worker receives `render_mode: "safe"`,
no `generate_chart_code` call is made, and the job completes through the trusted
path.

## Scenario F — codegen model selection

Unit `test_codegen_model_defaults_to_planner_when_unset` /
`test_codegen_model_honored_when_set` (helper) and
`test_codegen_model_default_and_override_are_threaded_to_client` (orchestration):
when `codegen_model` is unset the planner model is threaded to
`generate_chart_code`; when set to `qwen2.5-coder` that model is used and the
planner model is unchanged. `CodegenSetupTests` prove the setup installs the
client with the correct model and reports `codegen_model_defaulted_to_planner`.

## Scenario G — data boundary: no secret crosses into the codegen prompt

Unit `test_data_boundary_no_secret_in_codegen_prompt`: a request carrying a
(deliberately injected) `worker_token` / `authorization` / `request_id` produces
a generation prompt whose raw body contains none of that material — only the
validated `chart_spec` + normalized render data are projected in
(`_codegen_request_view`).
