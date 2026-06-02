# Custom Card Anchor Evidence

Paired BDD:
`bdd/dashboard-card/custom-card-anchor-bdd.md`

Status: pending implementation.

No scenario is marked passed in this scaffold. The first dashboard-card
implementation slice must replace this file with raw browser or frontend test
output, fixture snapshots, recorded fake Home Assistant WebSocket messages, and
static or runtime boundary-check output.

## Expected Evidence Sections

- Run timestamp.
- Frontend or browser test command.
- Raw frontend or browser test output.
- Fixture job snapshots for idle, planning, `clarification_needed`, `complete`,
  and `failed`.
- Custom-element registration and card picker metadata output.
- Valid-config and invalid-config output.
- Layout evidence for prompt-first idle state and chart-first complete state
  with a compact bottom prompt composer.
- Recorded fake Home Assistant WebSocket messages.
- Boundary-check output for no direct worker/model calls, no direct Home
  Assistant history calls, no mutation service calls, no semantic-memory file
  access, and no browser local storage for Isolinear state.
