# Custom Card Anchor BDD

The dashboard-card anchor proves the chosen Home Assistant custom-card
technology with a real browser-loadable card shell before the full custom
integration exists.

Evidence file:
`bdd/dashboard-card/custom-card-anchor-evidence.md`

Related artifacts:

- Source feature: `docs/bdd/dashboard-card.feature`
- Spec: `docs/specs/dashboard-card-spec.md`
- ADR: `docs/decisions/0011-dashboard-card-implementation-technology.md`

## Scenario: Dashboard loads the Isolinear custom card

Given the compiled Isolinear card module is loaded as a JavaScript module
resource
And a dashboard card is configured as `type: custom:isolinear-card`
When the browser imports the module
Then `customElements.get("isolinear-card")` should be defined
And `window.customCards` should include an `isolinear-card` entry
And the card should render prompt entry and idle job state with a minimal valid
config
And the prompt area should be the primary initial surface
And the card should expose a graphical configuration surface

## Scenario: User submits prompt and sees progress

Given the card is rendered with a fake Home Assistant object
And the fake Isolinear API adapter returns a `planning` job snapshot
When the user submits `Compare upstairs and downstairs temperatures`
Then the card should render the planning state
And the submit control should be disabled for the active job
And the fake Home Assistant connection should record one versioned Isolinear
WebSocket request

## Scenario: User answers clarification

Given the card is rendered with a `clarification_needed` job snapshot
And the clarification offers `Use once` and `Use and remember`
When the user chooses `Use once`
Then the fake Home Assistant connection should record a clarification answer
request
And the request should include intent to continue without saving semantic
memory
And the browser should not write semantic memory to local storage

## Scenario: User views chart result

Given the card is rendered with a `complete` job snapshot
When the card displays the result
Then the chart image should be visible
And the chart should use most of the card's available content area
And the card should show which entities and aliases were used
And the card should show validation status
And a compact prompt area should remain available at the bottom for a new
request

## Scenario: User sees failure details

Given the card is rendered with a `failed` job snapshot
When the card displays the failure
Then the card should show the failure stage
And the card should offer retry or prompt revision when appropriate

## Scenario: Card keeps orchestration inside the integration

Given the card is rendered with fake Home Assistant context
When the browser test exercises prompt submission, clarification, retry, and
snapshot rendering
Then all Isolinear operations should go through the fake Home Assistant
WebSocket adapter
And no direct worker URL, model-provider URL, Home Assistant history API,
mutation service call, semantic-memory file access, or browser local storage
operation should be observed for Isolinear state

## Proof Requirements

The evidence must include:

- A recent run timestamp.
- The exact browser or frontend test command and raw output.
- The exact fixture job snapshots used for idle, planning,
  `clarification_needed`, `complete`, and `failed`.
- The observed custom-element registration and card picker metadata.
- The observed valid-config and invalid-config behavior.
- Layout evidence showing a prompt-first idle state and chart-first complete
  state with a compact bottom prompt composer.
- The recorded fake Home Assistant WebSocket messages for prompt submission and
  clarification answers.
- Static or runtime boundary-check output proving the card does not directly
  call worker/model endpoints, Home Assistant history APIs, mutation services,
  semantic-memory storage, or browser local storage for Isolinear state.
