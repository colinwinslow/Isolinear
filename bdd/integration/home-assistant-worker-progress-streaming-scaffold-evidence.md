# Home Assistant Worker Progress Streaming Scaffold Evidence

Run timestamp: 2026-06-09T20:13:39+00:00

BDD file:
`bdd/integration/home-assistant-worker-progress-streaming-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: subscribed worker job records progress snapshots -> `CASE subscribed_worker_job_records_progress_snapshots`
- Scenario B: worker progress links to card subscriptions -> `CASE worker_progress_links_to_card_subscriptions`
- Scenario C: worker progress contracts validate before storage -> `CASE worker_progress_contracts_validate_before_storage`
- Scenario D: worker authorization is redacted -> `CASE worker_progress_authorization_is_redacted`
- Scenario E: repeated snapshot requests reuse progress -> `CASE repeated_snapshot_requests_reuse_worker_progress`
- Scenario F: invalid worker progress, including HTTP non-list progress, fails before storage -> `CASE invalid_worker_progress_rejected_before_storage`
- Scenario G: unknown job fails before worker progress -> `CASE unknown_job_rejected_before_worker_progress`
- Scenario H: config entries cannot stream progress for each other's jobs -> `CASE cross_config_entry_rejected_before_worker_progress`
- Scenario I: valid worker progress stays config-entry scoped -> `CASE valid_worker_progress_stays_config_entry_scoped`
- Scenario J: worker progress remains bounded -> `CASE worker_progress_remains_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_worker_progress_streaming_scaffold.py
```

Raw output excerpt:

```text
CASE subscribed_worker_job_records_progress_snapshots
  accepted.snapshot_dispatch.accepted = true
  accepted.worker_call_count = 1
  accepted.rendering_snapshots[0].snapshot_id = worker-progress-entry-job-001-snapshot-004
  accepted.rendering_snapshots[0].status = rendering
  accepted.rendering_snapshots[0].progress.stage = worker_render_started
  accepted.rendering_snapshots[1].snapshot_id = worker-progress-entry-job-001-snapshot-005
  accepted.rendering_snapshots[1].status = rendering
  accepted.rendering_snapshots[1].progress.stage = worker_render_finished
  accepted.complete_snapshot.snapshot_id = worker-progress-entry-job-001-snapshot-006
  accepted.complete_snapshot.status = complete
  accepted.worker_progress_events[0].event_id = worker-progress-entry-worker-progress-001
  accepted.worker_progress_events[0].type = isolinear_worker_progress
  accepted.worker_progress_events[0].snapshot_id = worker-progress-entry-job-001-snapshot-004
  accepted.worker_progress_events[0].worker.authorization = Bearer <redacted>
  accepted.worker_progress_events[1].event_id = worker-progress-entry-worker-progress-002
  accepted.worker_progress_events[1].snapshot_id = worker-progress-entry-job-001-snapshot-005
  accepted.worker_progress_validation[0].accepted = true
  accepted.worker_progress_snapshot_validation[0].accepted = true
PASS subscribed_worker_job_records_progress_snapshots

CASE worker_progress_links_to_card_subscriptions
  subscription_linkage.subscription_ids = ["worker-progress-entry-job-001-subscription-001"]
  subscription_linkage.worker_progress_subscription_ids = [["worker-progress-entry-job-001-subscription-001"], ["worker-progress-entry-job-001-subscription-001"]]
  subscription_linkage.all_progress_events_link_subscription = true
PASS worker_progress_links_to_card_subscriptions

CASE worker_progress_contracts_validate_before_storage
  validation.accepted.worker_progress_valid = true
  validation.accepted.worker_progress_snapshot_valid = true
  validation.accepted.worker_dispatch_valid = true
  validation.accepted.worker_transport_valid = true
  validation.accepted.render_request_valid = true
  validation.accepted.render_result_valid = true
  validation.accepted.render_plan_valid = true
  validation.accepted.chart_spec_valid = true
  validation.accepted.history_series_valid = true
  validation.idempotent.worker_progress_valid = true
  validation.isolation_entry_a.worker_progress_valid = true
  validation.isolation_entry_b.worker_progress_valid = true
PASS worker_progress_contracts_validate_before_storage

CASE worker_progress_authorization_is_redacted
  redaction.raw_worker_authorization_received = true
  redaction.stored_authorizations = ["Bearer <redacted>", "Bearer <redacted>"]
  redaction.stored_authorization_redacted = true
  redaction.worker_token_absent_from_evidence = true
  redaction.secret_text.error_codes = ["invalid_integration_worker_progress"]
  redaction.secret_text.worker_progress_events = []
  redaction.secret_text.worker_dispatches = []
  redaction.secret_text.token_absent_from_result = true
PASS worker_progress_authorization_is_redacted

CASE repeated_snapshot_requests_reuse_worker_progress
  idempotent.first.accepted = true
  idempotent.second.accepted = true
  idempotent.worker_call_count = 1
  idempotent.same_snapshot_returned = true
  idempotent.worker_progress_count = 2
  idempotent.worker_dispatch_count = 1
  idempotent.render_plan_count = 1
  idempotent.artifact_count = 1
  idempotent.complete_snapshot_count = 1
PASS repeated_snapshot_requests_reuse_worker_progress

CASE invalid_worker_progress_rejected_before_storage
  invalid.error_codes = ["invalid_integration_worker_progress"]
  invalid.worker_call_count = 1
  invalid.worker_progress_events = []
  invalid.worker_dispatches = []
  invalid.render_plans = []
  invalid.artifacts = []
  invalid.complete_snapshots = []
  http_non_list.error_codes = ["invalid_integration_worker_progress"]
  http_non_list.worker_http_call_count = 1
  http_non_list.forwarded_progress_type = dict
  http_non_list.worker_progress_events = []
  http_non_list.worker_dispatches = []
  http_non_list.render_plans = []
  http_non_list.artifacts = []
  http_non_list.complete_snapshots = []
  http_non_list.token_absent_from_result = true
PASS invalid_worker_progress_rejected_before_storage

CASE unknown_job_rejected_before_worker_progress
  unknown_job.error_codes = ["unknown_job"]
  unknown_job.worker_call_count = 0
  unknown_job.worker_progress_events = []
  unknown_job.worker_dispatches = []
PASS unknown_job_rejected_before_worker_progress

CASE cross_config_entry_rejected_before_worker_progress
  cross_entry.error_codes = ["unknown_job"]
  cross_entry.entry_a_worker_call_count = 0
  cross_entry.entry_b_worker_call_count = 0
  cross_entry.entry_b_worker_progress_events = []
  cross_entry.entry_b_worker_dispatches = []
  cross_entry.entry_b_render_plans = []
  cross_entry.entry_b_artifacts = []
  cross_entry.entry_b_complete_snapshots = []
PASS cross_config_entry_rejected_before_worker_progress

CASE valid_worker_progress_stays_config_entry_scoped
  isolation.entry_a.worker_call_count = 1
  isolation.entry_b.worker_call_count = 1
  isolation.entry_a.worker_progress_events[0].job_id = worker-progress-isolation-entry-a-job-001
  isolation.entry_a.worker_progress_events[0].subscription_ids = ["worker-progress-isolation-entry-a-job-001-subscription-001"]
  isolation.entry_b.worker_progress_events[0].job_id = worker-progress-isolation-entry-b-job-001
  isolation.entry_b.worker_progress_events[0].subscription_ids = ["worker-progress-isolation-entry-b-job-001-subscription-001"]
PASS valid_worker_progress_stays_config_entry_scoped

CASE worker_progress_remains_bounded
  side_effects.allowed_aggregate.worker_called = true
  side_effects.allowed_aggregate.chart_rendering_called = true
  side_effects.allowed_aggregate.worker_progress_streaming_called = true
  side_effects.allowed_aggregate.worker_progress_bookkeeping_written = true
  side_effects.allowed_aggregate.worker_dispatch_bookkeeping_written = true
  side_effects.allowed_aggregate.render_plan_bookkeeping_written = true
  side_effects.allowed_aggregate.artifact_metadata_bookkeeping_written = true
  side_effects.allowed_aggregate.subscription_bookkeeping_written = true
  side_effects.allowed_aggregate.subscription_progress_streaming_called = true
  side_effects.allowed_aggregate.job_state_scaffold_written = true
  side_effects.allowed_aggregate.job_orchestration_scaffold_written = true
  side_effects.allowed_aggregate.websocket_command_registered = true
  side_effects.forbidden_aggregate.home_assistant_history_read = false
  side_effects.forbidden_aggregate.semantic_memory_called = false
  side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called = false
  side_effects.forbidden_aggregate.token_generated = false
  side_effects.forbidden_aggregate.chart_artifact_written = false
  side_effects.forbidden_aggregate.durable_storage_written = false
  side_effects.forbidden_aggregate.retry_behavior_called = false
  side_effects.forbidden_aggregate.automatic_progress_task_called = false
  side_effects.forbidden_aggregate.job_orchestration_called = false
  side_effects.observed includes http_non_list_worker_progress with worker_progress_bookkeeping_written = false
PASS worker_progress_remains_bounded
PASS home_assistant_worker_progress_streaming_scaffold
```

## Additional Verification

```text
.\.venv\Scripts\python.exe -m pytest tests\test_worker_progress_streaming_anchor.py
13 passed

.\.venv\Scripts\python.exe -m pytest tests\test_job_orchestration_worker_dispatch_rendering_anchor.py
10 passed

.\.venv\Scripts\python.exe -m pytest tests\test_job_orchestration_subscription_progress_anchor.py
7 passed

.\.venv\Scripts\python.exe -m pytest tests\test_worker_token_provisioning_readiness_anchor.py
10 passed

.\.venv\Scripts\python.exe evals\home_assistant_worker_progress_streaming_scaffold.py
PASS home_assistant_worker_progress_streaming_scaffold
```
