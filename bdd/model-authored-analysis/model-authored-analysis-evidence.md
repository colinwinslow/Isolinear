# Model-authored analysis — BDD evidence

Paired with [../../docs/specs/model-authored-analysis.md](../../docs/specs/model-authored-analysis.md)
and [model-authored-analysis-bdd.md](model-authored-analysis-bdd.md).

Raw outputs, not summaries. Appended per implementation packet.

## Packet 1 — the answer channel (2026-07-03)

**Scope proven here:** Scenario A (grounded answer ships with the supporting
chart) end to end, plus the chart-only-carries-no-answer variant. The number is
the computation, not a literal (ADR-0031 D3 grounding), proven both at the
sandbox boundary (known data → exact string) and over the HTTP wire. Scenarios
C–J (timestamp normalization, the deterministic grounding check, the visual
validator + progressive-verification UX, the capability gate, scipy/seaborn,
the Pillow-fallback answer omission, modality) are later packets — not claimed
here.

### Local end-to-end eval — `evals/model_authored_analysis.py`

Boots the real packet-2 `isolinear_worker.http_server` on an ephemeral port and
drives a `render_mode: codegen` render across the HTTP boundary. The generated
body computes `mean = sum(values)/len(values)` over the sample history
(71.2, 71.8) and f-strings it into `answer_text`. Result: the worker returns a
real PNG **and** `render_metadata.answer_text == "The average reading is 71.50
degF."` — i.e. the mean of 71.2 and 71.8, computed in the sandbox. A chart-only
body returns a PNG with **no** `answer_text`.

```
CASE grounded_answer_rides_render_metadata_over_http
  given.history_values: [71.2, 71.8]
  given.request.body.render_request.codegen.python_code:
    def render_chart(data, output_path):
        png_bytes = bytes.fromhex("89504e47...")
        with open(output_path, "wb") as image_file:
            image_file.write(png_bytes)
        values = [point["value"] for point in data["history_series"][0]["points"]]
        mean = sum(values) / len(values)
        return {
            "title": data["chart_spec"]["title"],
            "series_plotted": [series["series_id"] for series in data["chart_spec"]["series"]],
            "overlays_plotted": [],
            "x_min": data["history_series"][0]["points"][0]["ts"],
            "x_max": data["history_series"][0]["points"][-1]["ts"],
            "warnings": [],
            "answer_text": f"The average reading is {mean:.2f} degF.",
        }
  when.operation: generate(compute-mean body) -> POST /v1/render (render_mode=codegen)
  then:
    "render_status": "success",
    "image_signature_hex": "89504e470d0a1a0a",
    "answer_text": "The average reading is 71.50 degF.",
    "grounded": true,
    "authorization_sent": "Bearer <redacted>"
PASS grounded_answer_rides_render_metadata_over_http

CASE chart_only_render_carries_no_answer
  given.generated_code: safe body, no answer_text returned
  when.operation: generate -> POST /v1/render (render_mode=codegen)
  then:
    "render_status": "success",
    "image_signature_hex": "89504e470d0a1a0a",
    "answer_text_present": false
PASS chart_only_render_carries_no_answer

PASS model_authored_analysis
```

(The bearer token is redacted in the transport; the full request envelope —
chart_spec, history_series, output — is captured verbatim in the eval's raw
JSON. Timestamps here are still ISO strings: epoch-ms normalization is packet 2,
scenario C.)

### Unit tests — `tests/test_model_authored_analysis.py`

```
tests/test_model_authored_analysis.py::SandboxAnswerPassthroughTests::test_blank_answer_text_is_dropped PASSED
tests/test_model_authored_analysis.py::SandboxAnswerPassthroughTests::test_chart_only_render_carries_no_answer_text PASSED
tests/test_model_authored_analysis.py::SandboxAnswerPassthroughTests::test_grounded_answer_text_is_computed_and_passed_through PASSED
tests/test_model_authored_analysis.py::AnswerChannelEndToEndTests::test_answer_text_reaches_the_complete_snapshot_and_artifact PASSED
tests/test_model_authored_analysis.py::AnswerChannelEndToEndTests::test_chart_only_snapshot_has_no_answer_line PASSED
tests/test_model_authored_analysis.py::AnswerChannelSchemaTests::test_answer_text_optional_on_all_three_schemas PASSED
tests/test_model_authored_analysis.py::AnswerChannelSchemaTests::test_schema_copies_are_byte_identical PASSED
tests/test_model_authored_analysis.py::CodegenPromptGroundingTests::test_prompt_rules_carry_the_grounding_instruction PASSED
8 passed
```

- `test_grounded_answer_text_is_computed_and_passed_through` — the sandbox
  render_metadata carries exactly `"The average reading is 71.50 degF."` over
  the known sample data, and the render-result stays schema-valid.
- `test_answer_text_reaches_the_complete_snapshot_and_artifact` — end to end
  through the integration: `chart.answer_text` and `artifact.answer_text` match
  (the number reflects THIS job's real history — grounding, not the fixture's
  71.50), a real PNG is still served.
- `..._carries_no_answer_text` / `..._has_no_answer_line` — chart-only renders
  carry no answer at the sandbox and the snapshot.
- `test_blank_answer_text_is_dropped` — a whitespace-only answer is not an answer.
- `test_answer_text_optional_on_all_three_schemas` +
  `test_schema_copies_are_byte_identical` — additive/optional on render-result,
  artifact-metadata, job-snapshot; docs / packaged / worker copies byte-identical.
- `test_prompt_rules_carry_the_grounding_instruction` — the codegen prompt
  instructs COMPUTE-and-format with derived verdicts (mentions `answer_text`,
  `f-string`, `verdict`).

### Card — `frontend/src/isolinear-card-answer.test.ts`

```
Test Files  1 passed (1)
      Tests  3 passed (3)
```

- renders `[data-testid="analysis-answer"]` under the caption when
  `chart.answer_text` is present (caption still shows the summary);
- no answer element for a chart-only render;
- no answer element when `answer_text` is blank.

### Suite posture

- `python3 -m pytest tests/` → **320 passed, 4 skipped** (312 baseline + 8 new;
  skips are the documented matplotlib-in-`-I` dev-box limitation).
- `frontend` Vitest → **26 passed** (23 baseline + 3 new).
- `evals/model_authored_analysis.py` → PASS; `evals/codegen_generation_path.py`
  → PASS (no regression).
- Schema byte-parity green across docs / packaged / worker copies; frontend
  bundle rebuilt and synced to `custom_components/isolinear/frontend/dist/`.

## Packet 2 — data-boundary timestamp normalization, Scenario C (2026-07-03)

**Scope proven here:** Scenario C — the codegen path hands the model epoch-ms
integers, never raw HA ISO timestamps. `ts_epoch_ms` (an additive optional
integer on history points) is precomputed at the integration boundary; the
prompt projection strips raw `ts` so the model literally never sees an ISO
string; the raw `ts` stays on the render-request for the existing contract; the
safe / Pillow paths are untouched.

### Unit + regression tests — `tests/test_model_authored_analysis.py`

```
TimestampNormalizationTests::test_conversion_is_idempotent_and_fails_soft PASSED
TimestampNormalizationTests::test_dispatched_codegen_data_carries_epoch_ms PASSED
TimestampNormalizationTests::test_history_series_gains_integer_epoch_ms_keeping_raw_ts PASSED
TimestampNormalizationTests::test_naive_iso_is_treated_as_utc PASSED
TimestampNormalizationTests::test_parses_on_the_second_and_microsecond_iso PASSED
TimestampNormalizationTests::test_prompt_projection_strips_raw_ts_keeps_epoch_ms PASSED
CodegenPromptGroundingTests::test_prompt_rules_direct_the_model_to_epoch_ms PASSED
7 passed
```

- `test_parses_on_the_second_and_microsecond_iso` — the exact HA mixed-precision
  case that broke `to_datetime`: `...:00Z` and `...:00.123456+00:00` both parse
  (the second is `ref`, the first `ref + 123` ms), cross-checked against an
  independently-constructed reference datetime.
- `test_naive_iso_is_treated_as_utc`, `test_conversion_is_idempotent_and_fails_soft`
  — naive → UTC; already-int passthrough; unparseable → `None` (fail-soft, no
  epoch-ms field).
- `test_history_series_gains_integer_epoch_ms_keeping_raw_ts` — each point gains
  an integer `ts_epoch_ms`; raw `ts` is retained; the source is not mutated.
- `test_prompt_projection_strips_raw_ts_keeps_epoch_ms` — `_codegen_request_view`
  drops `ts` and keeps `ts_epoch_ms`: the model never sees a raw ISO string.
- `test_dispatched_codegen_data_carries_epoch_ms` — **regression guard through
  the REAL integration path**: the render_request the sandbox executes against
  carries integer `ts_epoch_ms` on every point.

### Suite posture (packet 2)

- `python3 -m pytest tests/` → **327 passed, 4 skipped** (320 + 7 new).
- `evals/model_authored_analysis.py`, `codegen_generation_path.py`,
  `codegen_sandbox.py` → PASS (no regression).
- history-series schema byte-parity green across docs / packaged / worker copies.
