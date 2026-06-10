# Home Assistant Worker Health/Readiness Endpoint Scaffold Evidence

Run timestamp: 2026-06-09T23:58:07+00:00

BDD file:
`bdd/integration/home-assistant-worker-health-readiness-endpoint-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: ready worker health probe records redacted metadata -> `CASE ready_worker_health_probe_records_redacted_metadata`
- Scenario B: not-ready response records internal health state -> `CASE not_ready_health_response_records_internal_state`
- Scenario C: transport failure records unavailable health -> `CASE transport_failure_records_unavailable_health`
- Scenario D: malformed accepted response fails before storage -> `CASE malformed_accepted_health_response_fails_before_storage`
- Scenario E: no-token entry is rejected before worker call -> `CASE no_token_entry_rejected_before_worker_call`
- Scenario F: unknown config entry is rejected before worker call -> `CASE unknown_config_entry_rejected_before_worker_call`
- Scenario G: health state stays config-entry scoped -> `CASE worker_health_stays_config_entry_scoped`
- Scenario H: health details do not leak to the card -> `CASE worker_health_details_do_not_leak_to_card`
- Scenario I: health checks remain bounded -> `CASE worker_health_checks_remain_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_worker_health_readiness_endpoint_scaffold.py
```

Raw output excerpt:

```text
CASE ready_worker_health_probe_records_redacted_metadata
  ready.health.status = ready
  ready.health.type = isolinear_worker_health
  ready.health.request.method = GET
  ready.health.request.path = /v1/health
  ready.health.request.headers.authorization = Bearer <redacted>
  ready.health.worker.health_path = /v1/health
  ready.health.response.status = ready
  ready.health.response.capabilities.rendering = true
  ready.health_validation.accepted = true
  ready.request_validation.accepted = true
  ready.raw_request_authorization_present = true
  ready.raw_request_uses_worker_token = true
  ready.health_call_count = 1
  ready.render_call_count = 0
PASS ready_worker_health_probe_records_redacted_metadata

CASE not_ready_health_response_records_internal_state
  not_ready.result.accepted = true
  not_ready.result.code = worker_health_not_ready
  not_ready.health.status = not_ready
  not_ready.health.response.capabilities.rendering = false
  not_ready.health_validation.accepted = true
  not_ready.renderer_client_unchanged = true
  not_ready.health_call_count = 1
  not_ready.render_call_count = 0
PASS not_ready_health_response_records_internal_state

CASE transport_failure_records_unavailable_health
  unavailable.result.accepted = true
  unavailable.result.code = worker_connection_error
  unavailable.health.status = unavailable
  unavailable.health.response.accepted = false
  unavailable.health.response.code = worker_connection_error
  unavailable.health_validation.accepted = true
  unavailable.retry_or_scheduler_side_effects.retry_behavior_called = false
  unavailable.retry_or_scheduler_side_effects.scheduler_called = false
  unavailable.retry_or_scheduler_side_effects.automatic_retry_called = false
  unavailable.retry_or_scheduler_side_effects.durable_retry_storage_written = false
PASS transport_failure_records_unavailable_health

CASE malformed_accepted_health_response_fails_before_storage
  malformed.result.accepted = false
  malformed.result.code = invalid_worker_health_response
  malformed.health_call_count = 1
  malformed.render_call_count = 0
  malformed.health_written = false
PASS malformed_accepted_health_response_fails_before_storage

CASE no_token_entry_rejected_before_worker_call
  no_token.result.accepted = false
  no_token.result.code = worker_health_not_ready
  no_token.worker_client_present = false
  no_token.health_written = false
  no_token.result.orchestration.worker_health_check_called = false
PASS no_token_entry_rejected_before_worker_call

CASE unknown_config_entry_rejected_before_worker_call
  unknown.result.accepted = false
  unknown.result.code = unknown_config_entry
  unknown.entry_created = false
  unknown.health_written = false
  unknown.result.orchestration.worker_health_check_called = false
PASS unknown_config_entry_rejected_before_worker_call

CASE worker_health_stays_config_entry_scoped
  isolation.entry_a.health.config_entry_id = worker-health-isolation-entry-a
  isolation.entry_a.health.status = ready
  isolation.entry_a.health_validation.accepted = true
  isolation.entry_a.health_call_count = 1
  isolation.entry_a.raw_request_authorization_present = true
  isolation.entry_a.raw_request_uses_own_token = true
  isolation.entry_a.other_token_absent_from_request = true
  isolation.entry_b.health.config_entry_id = worker-health-isolation-entry-b
  isolation.entry_b.health.status = not_ready
  isolation.entry_b.health_validation.accepted = true
  isolation.entry_b.health_call_count = 1
  isolation.entry_b.raw_request_authorization_present = true
  isolation.entry_b.raw_request_uses_own_token = true
  isolation.entry_b.other_token_absent_from_request = true
PASS worker_health_stays_config_entry_scoped

CASE worker_health_details_do_not_leak_to_card
  leakage.health_validation.accepted = true
  leakage.stored_authorization = Bearer <redacted>
  leakage.raw_worker_authorization_received = true
  leakage.health_message = Worker health endpoint response was sanitized.
  leakage.token_absent_from_health = true
  leakage.token_absent_from_setup = true
  leakage.token_absent_from_evidence_payload = true
  leakage.token_absent_from_dashboard_card_metadata = true
  leakage.token_absent_from_model_provider_metadata = true
  leakage.endpoint_absent_from_dashboard_payload = true
  leakage.request_absent_from_dashboard_payload = true
  leakage.health_absent_from_dashboard_payload = true
PASS worker_health_details_do_not_leak_to_card

CASE worker_health_checks_remain_bounded
  side_effects.allowed_aggregate.worker_health_check_called = true
  side_effects.allowed_aggregate.worker_health_bookkeeping_written = true
  side_effects.allowed_aggregate.worker_health_request_validated = true
  side_effects.allowed_aggregate.worker_health_response_validated = true
  side_effects.forbidden_aggregate.home_assistant_history_read = false
  side_effects.forbidden_aggregate.semantic_memory_called = false
  side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called = false
  side_effects.forbidden_aggregate.token_generated = false
  side_effects.forbidden_aggregate.token_rotation_called = false
  side_effects.forbidden_aggregate.worker_render_called = false
  side_effects.forbidden_aggregate.chart_rendering_called = false
  side_effects.forbidden_aggregate.chart_artifact_written = false
  side_effects.forbidden_aggregate.durable_storage_written = false
  side_effects.forbidden_aggregate.durable_retry_storage_written = false
  side_effects.forbidden_aggregate.retry_behavior_called = false
  side_effects.forbidden_aggregate.scheduler_called = false
  side_effects.forbidden_aggregate.automatic_retry_called = false
  side_effects.forbidden_aggregate.automatic_progress_task_called = false
  side_effects.forbidden_aggregate.new_worker_transport_added = false
PASS worker_health_checks_remain_bounded
PASS home_assistant_worker_health_readiness_endpoint_scaffold
```

Token scan:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_worker_health_readiness_endpoint_scaffold.py | Select-String -Pattern "test-worker-readiness-token"
```

Raw output:

```text
```

## Additional Verification

```text
.\.venv\Scripts\python.exe -m pytest tests/test_worker_health_readiness_endpoint_anchor.py
10 passed

.\.venv\Scripts\python.exe -m pytest tests/test_worker_token_provisioning_readiness_anchor.py tests/test_job_orchestration_worker_dispatch_rendering_anchor.py tests/test_worker_progress_streaming_anchor.py
33 passed

.\.venv\Scripts\python.exe -m pytest tests/test_worker_retry_backoff_policy_anchor.py tests/test_worker_transport_failure_classification_anchor.py tests/test_worker_failure_snapshot_manual_retry_anchor.py
30 passed

.\.venv\Scripts\python.exe -m pytest tests\
243 passed

.\.venv\Scripts\python.exe evals\home_assistant_worker_health_readiness_endpoint_scaffold.py
PASS home_assistant_worker_health_readiness_endpoint_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_token_provisioning_readiness_scaffold.py
PASS home_assistant_worker_token_provisioning_readiness_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.py
PASS home_assistant_job_orchestration_worker_dispatch_rendering_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_progress_streaming_scaffold.py
PASS home_assistant_worker_progress_streaming_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_retry_backoff_policy_scaffold.py
PASS home_assistant_worker_retry_backoff_policy_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_transport_failure_retry_classification_scaffold.py
PASS home_assistant_worker_transport_failure_retry_classification_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold.py
PASS home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold
```

## Review Passes

Architecture review:

```text
codex exec "You are an architecture reviewer. Read codex/review-architecture.md and AGENTS.md in this repo, then review the diff in .codex-review-diff.txt against the project invariants. Output the verdict format from the protocol."

## Verdict
OK

## Invariant violations
None.

## Scope / discipline flags
None. The slice matches the current bounded packet: explicit worker health/readiness probe, schema-backed internal metadata, no scheduler/retry/durable storage/token rotation/card exposure. BDD is in bdd/integration/..., not inlined in the spec.

## ADR-relevance
No missing ADR. The /v1/health endpoint decision is recorded in docs/decisions/0014-worker-health-readiness-endpoint.md; it reuses ADR-0012 transport/auth.

## Recommendations
None.
```

BDD-evidence review:

```text
## Verdict
OK

## Per-scenario findings
- Scenario A "ready worker health probe records redacted metadata": PASS - evidence includes CASE ready_worker_health_probe_records_redacted_metadata and PASS line.
- Scenario B "not-ready response records internal health state": PASS - evidence includes CASE not_ready_health_response_records_internal_state and PASS line.
- Scenario C "transport failure records unavailable health": PASS - evidence includes CASE transport_failure_records_unavailable_health and PASS line.
- Scenario D "malformed accepted response fails before storage": PASS - evidence includes CASE malformed_accepted_health_response_fails_before_storage and PASS line.
- Scenario E "no-token entry is rejected before worker call": PASS - evidence includes CASE no_token_entry_rejected_before_worker_call and PASS line.
- Scenario F "unknown config entry is rejected before worker call": PASS - evidence includes CASE unknown_config_entry_rejected_before_worker_call and PASS line.
- Scenario G "health state stays config-entry scoped": PASS - evidence includes CASE worker_health_stays_config_entry_scoped and PASS line.
- Scenario H "health details do not leak to the card": PASS - evidence includes CASE worker_health_details_do_not_leak_to_card and PASS line.
- Scenario I "health checks remain bounded": PASS - evidence includes CASE worker_health_checks_remain_bounded and PASS line.

## Drift / hygiene flags
None. The BDD scenario list and evidence CASE list match, raw eval output is present, the run timestamp is present, and the token scan output is empty.

## Recommendations
None.
```
