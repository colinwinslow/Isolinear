# Security Spec

## Security goals

- Do not expose unapproved Home Assistant entities to the model.
- Do not expose Home Assistant secrets or tokens to the worker sandbox.
- Do not let generated code access the network.
- Do not let generated code read arbitrary files.
- Do not let generated code mutate Home Assistant state.
- Keep semantic memory user-confirmed and auditable.

## Data minimization

The model should receive only:

- User prompt.
- Approved entity metadata relevant to the prompt.
- Relevant semantic aliases.
- Clarification history.
- Summaries of data when needed.

The model should not receive:

- Secrets.
- Tokens.
- Full Home Assistant state dump.
- Hidden or unapproved entities.
- Raw history for unrelated entities.

## Generated code restrictions

Generated code must not:

- Import networking libraries.
- Spawn subprocesses.
- Read arbitrary paths.
- Write outside the output directory.
- Call Home Assistant APIs.
- Use environment variables to discover secrets.

## Audit logging

Each chart job should record:

- Prompt.
- Clarification answers.
- Entity mappings used.
- Chart spec.
- Render mode.
- Validation result.
- Warnings.
- Generated code hash, if codegen was used.

Do not store full generated images or prompts indefinitely without a retention policy.
