# Live Planner Reasoning Streaming — BDD Evidence

**Run timestamp:** 2026-06-22 (re-run at closeout; think/format mutual-exclusivity fix in 0.1.35)

**BDD file:** `bdd/dashboard-card/live-planner-reasoning-streaming-bdd.md`

---

## Server unit + integration tests (Scenarios A–G)

```
python3 -m pytest tests/test_live_planner_reasoning_streaming.py -v
```

```
collected 30 items

SanitizeReasoningTests::test_cap_is_2000 PASSED
SanitizeReasoningTests::test_empty_in_empty_out PASSED
SanitizeReasoningTests::test_keeps_approved_entity_id PASSED
SanitizeReasoningTests::test_redacts_bare_jwt PASSED
SanitizeReasoningTests::test_redacts_bearer_token PASSED
SanitizeReasoningTests::test_redacts_https_endpoint PASSED
SanitizeReasoningTests::test_redacts_long_lived_access_token_keyword PASSED
SanitizeReasoningTests::test_redacts_named_secret_with_value PASSED
SanitizeReasoningTests::test_redacts_openai_style_api_key PASSED
SanitizeReasoningTests::test_redacts_unix_path PASSED
SanitizeReasoningTests::test_redacts_windows_path PASSED
SanitizeReasoningTests::test_redacts_worker_url PASSED
SanitizeReasoningTests::test_rolling_tail_caps_to_2000_with_leading_ellipsis PASSED
SanitizeReasoningTests::test_short_clean_text_passes_through PASSED
StreamingPlannerTransportTests::test_non_streaming_default_unchanged PASSED
StreamingPlannerTransportTests::test_non_streaming_select_entity_omits_think PASSED
StreamingPlannerTransportTests::test_streaming_accumulates_thinking_and_invokes_callback PASSED
StreamingPlannerTransportTests::test_streaming_non_reasoning_model_never_calls_back PASSED
StreamingPlannerTransportTests::test_streaming_request_sets_think_true PASSED
StreamingPlannerTransportTests::test_streaming_select_entity_also_streams PASSED
StreamingPlannerTransportTests::test_streaming_select_entity_request_sets_think_true PASSED
StreamingPlannerTransportTests::test_streaming_transport_error_returns_failure PASSED
ApplyLiveReasoningTests::test_empty_text_omits_reasoning PASSED
ApplyLiveReasoningTests::test_injects_reasoning_and_stage_and_revalidates PASSED
ApplyLiveReasoningTests::test_no_slot_returns_snapshot_unchanged PASSED
ApplyLiveReasoningTests::test_phase_labels_defined PASSED
ApplyLiveReasoningTests::test_reasoning_at_cap_is_schema_valid PASSED
ApplyLiveReasoningTests::test_reasoning_is_capped_in_schema PASSED
EndToEndLiveReasoningTests::test_in_progress_poll_surfaces_reasoning_then_png_clears_it PASSED
EndToEndLiveReasoningTests::test_non_streaming_planner_shows_no_reasoning PASSED

30 passed in 0.28s
```

> **0.1.35 fix — `think`/`format` mutual exclusivity (ADR-0025 D1 correction).**
> Ollama silently suppresses thinking tokens when the structured-output `format`
> parameter is also set, so a thinking-capable model emitted no reasoning while
> `format` governed decoding. Fix: the streaming (reasoning) payload now sends
> `think: true` and omits `format`; the non-streaming fallback keeps `format`.
> Markdown code fences a thinking-mode model wraps around its JSON output are
> stripped by `_strip_markdown_json` before parsing. New raw coverage:
> `test_streaming_request_sets_think_true`,
> `test_streaming_select_entity_request_sets_think_true`,
> `test_non_streaming_select_entity_omits_think` (asserting `think` is absent and
> `format` retained on the non-streaming path).

Scenario mapping:

- **A** (per-delta accumulation, `stream: true`) — `test_streaming_accumulates_thinking_and_invokes_callback`
- **B** (both calls, phase labels) — `test_streaming_select_entity_also_streams`,
  `test_phase_labels_defined`, `test_injects_reasoning_and_stage_and_revalidates`
- **C** (in-progress poll surfaces reasoning, re-validates, no mutation) —
  `test_in_progress_poll_surfaces_reasoning_then_png_clears_it`,
  `test_injects_reasoning_and_stage_and_revalidates`
- **D** (PNG replaces reasoning on completion; slot cleared) —
  `test_in_progress_poll_surfaces_reasoning_then_png_clears_it`
- **E** (mid-stream transport error → failure code; no partial persistence) —
  `test_streaming_transport_error_returns_failure`
- **F** (sanitization + 2000-char rolling-tail cap; entity IDs retained) —
  the `SanitizeReasoningTests` group + schema `test_reasoning_is_capped_in_schema`.
  Hardened in 0.1.34 (closeout architecture-review finding): `sanitize_reasoning`
  now also redacts the named secret vocabulary used by
  `FORBIDDEN_WORKER_PROGRESS_TEXT` (`access_token`, `*_token`, `ollama_api_key`,
  `api_key`) plus bare `sk-…` keys and JWTs, so the reasoning surface can't drift
  from the other card-facing fields. New cases: `test_redacts_named_secret_with_value`,
  `test_redacts_long_lived_access_token_keyword`, `test_redacts_openai_style_api_key`,
  `test_redacts_bare_jwt`.
- **G** (non-streaming fallback, no reasoning) —
  `test_non_streaming_default_unchanged`,
  `test_streaming_non_reasoning_model_never_calls_back`,
  `test_non_streaming_planner_shows_no_reasoning`

---

## Card mounted smoke (Scenario H)

```
cd frontend && npx vitest run isolinear-card.long-running-smoke --reporter=verbose
```

```
stdout | ... > renders live planner reasoning in the chart slot during planning and the PNG on completion
CARD_REASONING_EVIDENCE {
  "heading": "Planning chart…",
  "reasoning_present": true,
  "reasoning_text": "Reading sensor.upstairs_temperature history\nChoosing a time_series line…"
}
 ✓ src/isolinear-card.long-running-smoke.test.ts > Isolinear mounted card long-running smoke > renders live planner reasoning in the chart slot during planning and the PNG on completion 7ms

 Test Files  1 passed (1)
      Tests  9 passed (9)
```

The mounted card showed a `data-testid="planning-reasoning"` block in the chart
slot with the coarse phase "Planning chart…" as the heading during planning, and
after the snapshot transitioned to `complete` the reasoning block was gone and
the chart `<img>` `src` was the served PNG URL.

---

## Schema (length cap, synced copies byte-identical)

```
python3 -m pytest tests/test_hacs_install_packaging.py::test_runtime_schema_paths_are_packaged_and_in_sync \
  tests/test_hacs_install_packaging.py::test_dashboard_card_bundle_is_packaged -q
```

```
..                                                                       [100%]
2 passed
```

`progress.reasoning` (`type: string`, `maxLength: 2000`) is present in both
`custom_components/isolinear/schemas/integration-job-snapshot.schema.json` and
`docs/schemas/integration-job-snapshot.schema.json`; the two files are
byte-identical (md5 `e5cfb48780191cc126ce2cd8a90f9e32`). The card bundle is
byte-identical between `frontend/dist/` and
`custom_components/isolinear/frontend/dist/` (md5 `d961b3dcc34a2d623e26480978edad02`).

---

## Full suite

```
python3 -m pytest tests/ -q
```

```
3 failed, 451 passed in 15.09s
```

The 3 failures are the pre-existing codegen-sandbox subprocess flake
(`tests/test_codegen_sandbox_anchor.py`), identical on the clean baseline and
unrelated to this change.

## Evals

```
python3 evals/prompt_to_chart_basic.py                                              -> PASS
python3 evals/home_assistant_job_orchestration_model_provider_planning_scaffold.py  -> PASS
python3 evals/dashboard_card_anchor.py                                              -> PASS
```
