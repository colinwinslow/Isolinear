---
status: draft
date: 2026-06-13
depends-on-adrs:
  - 0003
  - 0005
  - 0008
  - 0011
  - 0012
  - 0017
  - 0018
---

# Home Assistant Dashboard Card: Long-Running Prompt Smoke

## Status

Draft. Defines the automated dashboard-card long-running prompt smoke per
ADR-0011, ADR-0012, ADR-0017, and ADR-0018.

## Related docs

- [bdd/dashboard-card/home-assistant-dashboard-card-long-running-smoke-bdd.md](../../bdd/dashboard-card/home-assistant-dashboard-card-long-running-smoke-bdd.md) - observable behavior
- [docs/specs/dashboard-card-spec.md](dashboard-card-spec.md) - dashboard card contract
- [docs/specs/home-assistant-first-real-vertical-slice.md](home-assistant-first-real-vertical-slice.md) - registered real-slice prompt-to-chart route
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The accepted first real vertical slice proves the registered
`isolinear/v1/job/start` and `isolinear/v1/job/snapshot` handler path can return
a real PNG from approved history, a planner result, and trusted in-process
matplotlib rendering. ADR-0018 hardens delivery so the dashboard card receives
a served artifact URL rather than a WebSocket data URL. The dashboard card,
however, only submitted `job/start`; if that command returned an active
snapshot, the card could remain in planning until an external caller refreshed
it.

This packet hardens the card-facing workflow by proving that a delayed active
job can move from prompt submission to a chart result through repeated
integration-owned WebSocket snapshots.

## Behavior contract

The dashboard card must:

- Submit prompts through `isolinear/v1/job/start` with the configured
  `config_entry_id` and WebSocket API version.
- Treat `planning`, `fetching_history`, `rendering`, and `validating` snapshots
  as active jobs.
- Disable duplicate prompt submission while an active job is visible.
- Poll `isolinear/v1/job/snapshot` through the same Home Assistant connection
  when an active snapshot includes a `job_id`.
- Retry bounded transient snapshot poll failures such as Home Assistant
  frontend timeouts while the same job remains active.
- Continue to surface terminal Isolinear snapshot rejections such as
  `unknown_job` as visible failed dashboard snapshots.
- Stop polling when the job reaches `complete`, `failed`, or
  `clarification_needed`.
- Cancel outstanding polling timers when the card disconnects, when a new prompt
  starts, or when retry begins.
- Render the returned complete snapshot in the existing chart-first card layout
  with the PNG chart image and validation status visible.
- Preserve the dashboard-card boundary: no direct worker, model-provider,
  Home Assistant history, mutation service, semantic-memory, local-storage, or
  token access from the browser.

The registered-command proof must also verify that the same start and snapshot
command shapes accepted by the card are accepted by the production registered
WebSocket handler path and return a served PNG artifact URL for the
first-real-slice route. It must also prove overlapping snapshot requests while
planner/render work is already in progress do not start duplicate planner
calls.

## Anchor artifact

The anchor artifact is a mounted Lit-card Vitest smoke using `happy-dom` plus a
focused Python pytest for the registered WebSocket handler sequence. Together
they prove the browser-facing card behavior and the integration-owned command
path without adding a parallel verifier framework.

## Implementation order

1. Add active-job snapshot polling to the Lit card.
2. Add a mounted card smoke that submits a prompt, observes the active state,
   waits for automatic `job/snapshot` polling, and verifies the complete PNG
   result.
3. Add a focused registered-command pytest that sends matching `job/start` and
   `job/snapshot` messages through `handle_registered_ws_command`.
4. Capture raw frontend and Python evidence in the paired evidence file.

## Proof requirements

1. Frontend smoke proves `job/start` is followed by automatic `job/snapshot`.
2. Frontend smoke proves duplicate submit is disabled while the job is active.
3. Frontend smoke proves the final card state is `complete`, uses chart-first
   layout, and shows a served PNG artifact URL.
4. Python smoke proves the same registered command sequence returns a complete
   first-real-slice snapshot with a PNG signature.
5. Python smoke proves the planner is called once with only the allowlisted
   entity and the worker is not called.
6. Frontend smoke proves a transient snapshot timeout is retried and the later
   complete snapshot renders, while a terminal Isolinear rejection still
   renders a visible failure.
7. Python smoke proves a concurrent snapshot poll during planner work returns
   the active snapshot, rechecks completed artifacts after acquiring the
   per-job lock, and the planner is still called only once.
8. The checked-in card bundle is rebuilt after the polling change.

## Non-goals

- Real Home Assistant browser automation against a live dashboard URL.
- New worker/add-on rendering behavior.
- Durable job or artifact persistence.
- Automatic job/provider retry behavior or subscription streaming changes
  beyond the bounded snapshot transport retry needed for this card poll
  regression.

## References

- [docs/decisions/0011-dashboard-card-implementation-technology.md](../decisions/0011-dashboard-card-implementation-technology.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/decisions/0017-first-real-vertical-slice.md](../decisions/0017-first-real-vertical-slice.md)
- [docs/decisions/0018-production-artifact-serving.md](../decisions/0018-production-artifact-serving.md)
- [frontend/src/isolinear-card.ts](../../frontend/src/isolinear-card.ts)
- [frontend/src/isolinear-card.long-running-smoke.test.ts](../../frontend/src/isolinear-card.long-running-smoke.test.ts)
- [tests/test_dashboard_card_long_running_smoke.py](../../tests/test_dashboard_card_long_running_smoke.py)
