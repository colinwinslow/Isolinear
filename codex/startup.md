# Codex startup protocol

Use this protocol at the start of every Codex session.

## Steps

1. Inspect repository status.
2. Read `AGENTS.md`.
3. Read `STATUS.md`.
4. Read `HANDOFF.md`.
5. Identify the relevant ADRs, specs, BDDs, schemas, and eval outlines for the requested task.
6. Read those artifacts before editing code.
7. Summarize:
   - Current repo state.
   - Requested task.
   - Relevant contracts.
   - Expected files to change.
   - Expected tests/evals to run.
8. Do not code until the work packet is clear.

## Default verification question

Before editing, answer:

> What behavior will prove this task is complete?
