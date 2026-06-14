# Dashboard Card Spec

## Purpose

The dashboard card is the first user interface. It lets the user submit prompts, answer clarifying questions, and view generated charts.

## Required UI elements

- Prompt input.
- Submit button.
- Current job state.
- Clarifying question panel.
- Candidate entity choices when clarification is needed.
- Option to use a clarification answer once or save it as semantic memory.
- Generated chart image.
- Entity and alias disclosure.
- Validation status.
- Warnings and failure details.
- Retry or revise prompt action.

## Layout intent

The card should behave as a stable Home Assistant dashboard card, not as a
full-page application. Its footprint may adapt to dashboard layout and user
resizing, but the internal layout should avoid large jumps between states.

The initial loaded state should be prompt-first:

- The primary visible control is a text prompt area.
- The submit action is adjacent to the prompt.
- Empty-state content is minimal and should not compete with the prompt.

When a chart is available, the card should become chart-first:

- Most available vertical space is used for the generated plot or chart.
- Entity, alias, warning, and validation details remain visible or inspectable
  as supporting metadata.
- A compact text entry area remains anchored at the bottom so the user can
  submit a new request without reloading or reconfiguring the card.

During active jobs, the card should preserve the bottom composer area but
disable duplicate submission for the active job. Clarification states may use
the main body for choices, with the bottom composer remaining secondary until
the clarification is resolved.

## Implementation technology

Architecture decision: `docs/decisions/0011-dashboard-card-implementation-technology.md`.

The MVP dashboard card is a TypeScript Lit custom element named
`isolinear-card`, loaded in dashboards as `type: custom:isolinear-card`.
The card is bundled as an ES module and loaded as a Home Assistant dashboard
resource.

The card must use documented Home Assistant custom-card hooks:

- `setConfig(config)` for dashboard configuration.
- A graphical configuration hook for selecting the Isolinear config entry and
  display defaults.
- Card sizing hooks for masonry and sections dashboards.
- Card picker metadata in `window.customCards`.

The card should avoid private Home Assistant frontend internals. It may use
web standards, Lit, Home Assistant theme variables, and documented custom-card
APIs.

## Integration boundary

The card is a thin client. It may submit user gestures and render integration
job snapshots, but it does not own durable Isolinear state.

The card must not directly:

- Call the worker service.
- Call the model provider.
- Read Home Assistant history.
- Read or write the semantic-memory store.
- Read or write entity allowlist configuration.
- Store job state, semantic aliases, raw history, generated images, or generated
  code in browser local storage.
- Call Home Assistant device, automation, scene, or entity mutation services.

Prompt submission, clarification answers, retry, snapshot retrieval, and future
job subscriptions go through integration-owned, versioned Home Assistant
WebSocket commands. Exact command schemas belong to the integration API slice.

## Card configuration

The card configuration may include:

- Isolinear config entry ID or selector value.
- Default card title.
- Display density or detail level.
- Optional render preference if the integration exposes it as a safe display
  default.

The card configuration must not include:

- Home Assistant tokens or secrets.
- Worker endpoint credentials.
- Model endpoint credentials.
- Entity allowlist contents.
- Raw history.
- Generated chart images.
- Generated code.
- Semantic alias records.

## Conversation model

The card supports one active chart-generation conversation at a time. A conversation can contain:

- Initial prompt.
- Zero or more clarifying questions.
- User clarification answers.
- Final chart result or failure.

## Clarification examples

If the prompt says `upstairs temperature` and three approved temperature sensors match, the card should ask:

> I found three upstairs temperature sensors. Should I average them and call that "upstairs temperature"?

If the prompt says `air conditioning running` and the catalog contains a binary sensor and a current sensor, the card should ask:

> I found multiple ways to represent air conditioning running. Which should I use?

## Display of result

A complete result should show:

- Chart title.
- Chart image.
- Time range.
- Series plotted.
- Overlays plotted.
- Data quality warnings.
- Validation outcome.

## Anchor artifact

The first implementation slice should produce the smallest real card artifact:

- A browser-loadable `isolinear-card` custom element module.
- A fake Home Assistant object that supplies the minimal card context and
  records Isolinear WebSocket calls.
- A fixture job snapshot for `idle`, `planning`, `clarification_needed`,
  `complete`, and `failed` states.
- A local browser harness or automated browser test that imports the module and
  renders the states without a running Home Assistant instance.

The anchor artifact proves the frontend technology choice before the custom
integration, worker transport, and production chart artifact hosting exist.

## Proof requirements

The first card implementation evidence must show:

- The module registers `isolinear-card` and card picker metadata.
- `setConfig` accepts the minimal valid config and rejects invalid config.
- The initial loaded state is prompt-first.
- The card renders prompt entry, active progress, clarification controls, chart
  result metadata, validation status, and failure details from fixture
  snapshots.
- The complete state is chart-first and keeps a compact prompt composer visible
  at the bottom for a new request.
- Submitting a prompt records a versioned Isolinear WebSocket request through
  the fake Home Assistant connection.
- Choosing `Use once` and `Use and remember` records the expected clarification
  intent without writing semantic memory in the browser.
- Static or runtime checks show the card does not use direct worker/model calls,
  direct Home Assistant history calls, mutation service calls, semantic-memory
  file access, or browser local storage for Isolinear state.

## Non-goals

- Full gallery of previous charts.
- Voice input.
- Multi-user conversation history.
- Editing Home Assistant entities from the chart.
