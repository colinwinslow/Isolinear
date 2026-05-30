# Product Spec

## Product name

Isolinear

## Problem

Home Assistant stores rich entity history, but ad hoc analysis is hard. Users often need temporary charts that answer specific natural-language questions about their home, such as comparing temperatures, marking device-running intervals, or summarizing sensor behavior over time.

## Target users

- Home Assistant users who understand their entities but do not want to manually build every chart.
- Local-first users who prefer Ollama or other locally hosted models.
- Advanced users who want optional sandboxed code generation for custom plots.

## MVP user story

As a Home Assistant user, I want to type a question into a dashboard card and receive a generated chart based only on entities I have made visible to the agent.

## Core flow

1. User configures model endpoint and worker endpoint.
2. User selects entities visible to the agent.
3. User opens the dashboard card.
4. User enters a natural-language prompt.
5. System resolves entities, aliases, time ranges, chart intent, and data transformations.
6. System asks clarifying questions if needed.
7. System fetches and normalizes Home Assistant history.
8. System creates a chart spec.
9. System renders a chart through trusted rendering or sandboxed codegen.
10. System validates the result.
11. System displays chart, warnings, and validation status.

## MVP success criteria

- A user can generate a time-series comparison chart from approved entities.
- A user can resolve an ambiguous entity request through a clarifying question.
- A user can save a confirmed semantic alias for later use.
- The worker can render a PNG chart from normalized history.
- The system can reject or fail safely when generated code is unsafe or broken.
- The dashboard card shows enough detail for the user to understand what data was used.

## Non-goals

- Voice-first interaction.
- Automatic access to all Home Assistant entities.
- Device control or Home Assistant service calls.
- Full statistical analysis platform.
- Perfect entity inference without clarification.
- General-purpose Python execution environment.
