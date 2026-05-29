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

## Non-goals

- Full gallery of previous charts.
- Voice input.
- Multi-user conversation history.
- Editing Home Assistant entities from the chart.
