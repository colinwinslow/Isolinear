# Home Assistant Dataviz Agent

Home Assistant Dataviz Agent is a local-first visualization assistant for Home Assistant. A user asks a natural-language question about their home, the system resolves approved Home Assistant entities, retrieves and normalizes entity history, produces a visualization plan, renders a chart, validates the result, and displays the image in a dashboard card.

This repository is intentionally seeded with ADRs, specs, BDD scenarios, schemas, and eval outlines before production code. The project follows an agentic engineering workflow: design decisions first, behavior contracts second, tests third, implementation fourth, evals last.

## MVP goal

A user can open a Home Assistant dashboard card, enter a prompt such as:

> Compare upstairs and downstairs temperatures over the last 24 hours and mark when the air conditioning was running.

The system will:

1. Use only entities the user has explicitly made visible to the agent.
2. Resolve the prompt against entity names, domains, device classes, units, areas, labels, and saved semantic aliases.
3. Ask a clarifying question when multiple plausible interpretations exist.
4. Fetch and normalize Home Assistant history.
5. Generate a chart specification.
6. Render the chart using a trusted renderer by default, or sandboxed matplotlib code generation in advanced mode.
7. Validate the result using deterministic checks and optional visual validation.
8. Show the generated chart in the dashboard card.

## Non-goals for the first MVP

- Voice-first interaction.
- Editing Home Assistant devices, automations, scenes, or configuration.
- Exposing all Home Assistant entities to the model by default.
- Letting generated Python access Home Assistant secrets, tokens, local files, or the network.
- Fully automatic long-term memory without user confirmation.
- Perfect entity understanding without clarification.

## Draft artifact map

- `AGENTS.md` tells Codex and other coding agents how to work in this repo.
- `HANDOFF.md` keeps continuity across agentic engineering sessions.
- `codex/startup.md` and `codex/closeout.md` define session rituals.
- `docs/adr/` records load-bearing architecture decisions.
- `docs/specs/` defines expected behavior in prose.
- `docs/bdd/` defines concrete Gherkin scenarios.
- `docs/schemas/` defines machine-checkable internal contracts.
- `docs/evals/` sketches BDD-derived evaluation cases.

## Engineering rule of thumb

The model may infer, propose, and explain. The product constrains, validates, logs, and asks for user confirmation when ambiguity matters.
