# AGENTS.md

## Project identity

You are working on Isolinear, a local-first Home Assistant visualization assistant. The product turns natural-language questions into validated charts using approved Home Assistant entity history.

## Engineering workflow

This repo follows this sequence:

1. ADR
2. Spec
3. BDD
4. Red-Green TDD
5. Eval

Do not skip directly to implementation when an ADR, spec, BDD, schema, or eval is missing for the requested behavior.

## Required startup behavior

At the start of each coding session:

1. Read this file.
2. Read `HANDOFF.md`.
3. Read relevant ADRs in `docs/adr/`.
4. Read relevant specs in `docs/specs/`.
5. Read relevant BDDs in `docs/bdd/`.
6. Read relevant schemas in `docs/schemas/`.
7. Read relevant eval outlines in `docs/evals/`.
8. Summarize the current task and expected verification before editing files.

## Safety rules

- Do not expose all Home Assistant entities to the model. Use only the configured allowlist.
- Do not let generated Python access Home Assistant tokens, secrets, arbitrary files, local network resources, or the internet.
- Do not allow generated Python to call Home Assistant services.
- Do not mutate Home Assistant state, devices, automations, scenes, or configuration in the MVP.
- Do not save semantic memory unless the user explicitly confirms saving it.
- Do not silently choose among multiple plausible entity mappings when the choice changes meaning.
- Do not add a new external service, database, queue, or framework without an ADR.

## Rendering rules

- Prefer chart-spec rendering through the trusted renderer.
- Use sandboxed codegen only through the defined render contract.
- Generated code must implement a validated `ChartSpec`.
- Generated code must use a fixed entry point and a fixed output path.
- Generated code must pass static safety checks before execution.
- Codegen retry loops must be capped.

## Testing rules

- Use Red-Green-Refactor for behavior changes.
- Add or update tests for every behavior change.
- Add regression tests for every bug fix.
- Run the smallest relevant test set before broad test runs.
- Do not mark work complete if tests or evals are skipped without saying exactly why.

## Closeout report format

Every completed task should report:

1. Files changed.
2. Behavior implemented.
3. Tests run.
4. Evals run.
5. Any skipped checks.
6. Any assumptions or open questions.
7. Whether specs, ADRs, BDDs, schemas, or evals need updates.
