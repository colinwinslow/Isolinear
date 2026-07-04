# Evidence: deployment-worker-token

Raw outputs for
[deployment-worker-token-bdd.md](deployment-worker-token-bdd.md) (ADR-0032).
Captured 2026-07-04. Token material redacted throughout; the deployment token
lives only in the homelab SOPS store and the integration-owned HA Store.

## Scenarios A/B/C — options field, storage, echo-free (unit level)

```
$ python3 -m pytest tests/test_deployment_worker_token.py -q
................                                                         [100%]
16 passed in 0.72s
```

Load-bearing assertions, by scenario:

- **A** — `test_valid_token_saves_and_is_stripped_from_options`: the action
  splits to `{"kind": "save", "token": <token>}` and the remaining options
  payload does not contain the token (`assertNotIn(VALID_TOKEN,
  json.dumps(remaining))`) — `config_schema.py`'s secret-vocabulary fail-closed
  check is untouched. `test_endpoint_plus_stored_token_enables_client`: renderer
  setup builds a real `HttpJsonWorkerRenderClient` carrying the stored token.
- **B** — `test_summary_never_carries_token_values`: the storage summary is
  presence-only. The form field defaults to `""` regardless of stored state
  (`build_options_flow_schema` never reads the store).
- **C** — keep on absent/empty/whitespace; `clear` (case-insensitive) clears;
  1–23 chars → `{"kind": "too_short"}` → form error `worker_token_too_short`,
  nothing stored (`test_short_token_is_rejected_never_stored`).

## Scenario D — on-demand health against a real server

Unit level (`CheckHealthAgainstRealServerTests`, real packet-2
`WorkerHTTPServer` on an ephemeral port): correct token → accepted envelope;
wrong token → `worker_health_http_error` fault dict with no token material;
connection refused → `worker_health_connection_error`, no exception.

**Live CT103** (`evals/deployment_worker_token.py`, token via
`ISOLINEAR_EVAL_WORKER_TOKEN` from SOPS — raw output, 2026-07-04):

```
request: { ... "authorization": "Bearer <redacted>" ... }
result: {
  "accepted": true,
  "code": "worker_health_result_received",
  "worker": {"type": "http_json_worker", "role": "renderer",
             "endpoint_url": "http://10.0.1.39:8080", "api_version": 1},
  "health_result": {
    "accepted": true, "status": "ready", "code": "worker_ready",
    "message": "Worker is ready to render.",
    "checks": [{"name": "sandbox_policy", "status": "ok"},
               {"name": "matplotlib_import", "status": "ok"}],
    "capabilities": {"rendering": true}
  }
}
wrong-token result code: worker_health_http_error
PASS deployment_worker_token
```

The endpoint is the compose-managed worker deployed by homelab spec
`isolinear-worker-service` — the REAL integration client speaking to the REAL
deployed worker with the REAL deployment token for the first time.

## Scenario E — machinery deleted, setup chain intact

Eight modules deleted (`worker_token_lifecycle`, `worker_readiness`,
`worker_health`, `worker_health_polling{,_constants,_contract,_state,_storage}`)
plus five schemas from BOTH copies (docs + packaged):
`integration-worker-token-lifecycle-state`,
`integration-worker-health-polling-state`, `integration-worker-health`,
`integration-worker-readiness`, `worker-health-request`.

`MachineryDeletionGuardTests` pins both facts permanently (no integration
module imports the retired names; the files/schemas do not exist).
`__init__.py` loses the lifecycle await + abort path, readiness/health/polling
setup steps, and the polling unload hook; the options-update listener now
rebuilds the renderer client so a pasted token takes effect without a restart.

```
$ python3 -m pytest tests/ -q
389 passed, 4 skipped in 7.55s
```

(373 before the packet; +16 new. The deletion itself broke ONLY the packaging
test's schema-path imports — the 2026-07-02 purge had already removed every
behavioral test of the machinery, confirming it ran uncovered.)

## Scenario F — missing token stays fail-soft

`test_missing_token_disables` / `test_missing_endpoint_disables_even_with_token`:
renderer setup returns the existing disabled
`worker_renderer_token_missing`; with `render_path: auto` orchestration keys on
client-absence exactly as before (ADR-0030 surfaced Pillow fallback — no new
failure mode, asserted by the untouched codegen-path suite staying green).
