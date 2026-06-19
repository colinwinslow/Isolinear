# CLAUDE.md — Isolinear Agent Contract

> This file is the working contract for Claude Code operating in this repo. Claude Code reads `CLAUDE.md` automatically on session start. Keep it short — it is loaded every session.

## Identity

**Isolinear** is a local-first Home Assistant visualization assistant. The product turns natural-language questions into validated charts using approved Home Assistant entity history.

Isolinear runs as a Home Assistant custom integration (ADR-0001) paired with an isolated worker service (ADR-0001). It uses schema-first design (ADR-0005), deterministic validation (ADR-0006), and semantic memory (ADR-0009) to deliver safe, reproducible visualizations. The MVP is read-only and sandboxed (ADR-0008).

This project is developed **agentically**. The human provides direction and oversight; the agent does the implementation. Work is reviewed by reading commits, decision records (ADRs), specs, and the inspectable evidence that tests produce.

## Session start

On session start, run `/startup`. The required read set is **`STATUS.md` + `HANDOFF.md`**. `STATUS.md` is the single source for the current bounded packet and rolling session log. `HANDOFF.md` carries the current project phase, architectural direction, implementation status, and unresolved design details.

Do not load other docs unless the work requires them. The doc map below tells you when to load what.

## Doc map

| Question | Read |
|---|---|
| What's the current state of the project? | `STATUS.md` |
| What is Isolinear, architecturally? | `HANDOFF.md` + relevant ADRs in `docs/decisions/` |
| Why did we decide X? | `docs/decisions/NNNN-*.md` (one ADR per decision) |
| What does feature Y do? | `docs/specs/<feature>.md` (one spec per shippable feature) |
| What are the scenarios for feature Y? | `docs/bdd/<feature>/` or `docs/bdd/<feature>.feature` |
| Is Z still an open question? | `docs/research/<topic>.md` |
| What are the JSON Schema contracts? | `docs/schemas/*.json` |
| What's the implementation plan for slice N? | Current `STATUS.md` active work + the spec's "Proof requirements" |
| How does the project build/test? | This file, "Build & test" |
| What session commands exist? | `.claude/commands/` (startup, closeout, adr, spec, research, review passes) |

If the question doesn't fit the table, ask. Don't guess.

## Invariants (load-bearing; do not violate)

These are the non-negotiable rules of Isolinear. Every diff is checked against them; review passes verify compliance. Cite the ADR for the reasoning.

1. **Entity allowlist enforcement** — Plans and generated code reference only approved entities from the configured allowlist. Ambiguous entity prompts trigger clarification, never silent guesses. (ADR-0003, ADR-0008)

2. **No Home Assistant mutation** — The MVP does not mutate Home Assistant state, devices, automations, scenes, or configuration. Read-only operations only. (ADR-0008)

3. **Sandboxed execution** — All generated Python (matplotlib codegen, etc.) runs in a sandboxed subprocess with no access to HA tokens, secrets, arbitrary files, local network resources, or internet. (ADR-0008)

4. **Schema validation first** — All major data (ChartSpec, HistorySeries, ClarificationQuestion, SemanticAlias, etc.) must validate against JSON Schema (docs/schemas/) before rendering or storage. (ADR-0005)

5. **Deterministic plan validation** — Plans pass a validation gate (pre-render) that checks schema validity and entity allowlist membership. Invalid or hidden-entity plans return a clear failure, not a render attempt. (ADR-0006)

6. **Chart-spec-first rendering** — Prefer rendering through the trusted chart-spec renderer. Sandboxed codegen is an opt-in advanced path, not the default. Generated code must implement a validated ChartSpec, use a fixed entry point and output path, pass static safety checks, and cap retry loops. (ADR-0004, ADR-0008)

7. **Semantic memory is deterministic** — Saved aliases (SemanticAlias records) are deterministic and reusable. Invalidated aliases (entity unavailable, no longer allowlisted) do not silently reuse; they trigger clarification or a `cannot_resolve` result. (ADR-0009)

8. **No silent architecture decisions** — New external services, databases, queues, frameworks, or storage mechanisms require an ADR before implementation. No speculative generality. (ADR-0008)

9. **Deterministic render-family routing** — The integration selects the chart family (`time_series` / `timeline`) from each resolved entity's series kind *before* planning; the model never chooses `chart_type`. Binary/categorical entities render as raw-states step tracks and cannot be charted beyond recorder retention. (ADR-0022)

## Workflow

### BDD before implementation

Every implementation slice begins with a small, inspectable BDD that defines the artifact proving success. Tests derive from the BDD; code makes the tests pass. Scaffold a spec + paired BDD with `/spec <slug>`.

The engineering sequence is:

1. **ADR** — Decide the architecture (if a decision is needed).
2. **Spec** — Define the contract surface and observable behavior.
3. **BDD** — Write scenarios that pin down "done"; create the evidence file scaffold.
4. **Red-Green-Refactor TDD** — Anchor artifact first; supporting code second; tests drive correctness.
5. **Eval** — Run evaluation scripts to validate deterministic behavior against specifications.

Do not skip directly to implementation when an ADR, spec, BDD, schema, or eval is missing for the requested behavior.

### Three layers of correctness proof

| Layer | Owns | When | Format |
|---|---|---|---|
| **Unit tests (red/green TDD)** | Failure paths, edge cases, regression net | Every code change; failing tests block commit | Test runner output |
| **BDD evidence** | User-facing happy path + catastrophic/irreversible failures | After feature work; human reviews | Markdown evidence file referenced from the BDD |
| **Anchor artifact** | The simplest concrete observable version of the thing | Built first, before supporting code | Whatever the feature *is* (a CLI output, a file, a JSON row) |

### Verify on disk

A slice is not done until the real artifact has been verified on disk (read the changed files back; confirm the expected content is present). "Tests pass" is necessary but not sufficient.

### Anchor-artifact discipline

Build the simplest concrete observable version of the thing **first**, before supporting infrastructure. If you're building plumbing before anything visible exists, stop and reorder.

## Session commands

These are native Claude Code slash commands. When the user types `/startup`, Claude Code reads `.claude/commands/startup.md` and follows the protocol there.

| Command | Protocol file | Purpose |
|---|---|---|
| `/startup` | `.claude/commands/startup.md` | Drift-check + read STATUS/HANDOFF + identify next bounded packet + confirm proof |
| `/closeout` | `.claude/commands/closeout.md` | Update STATUS rolling log + sync doc indexes + run review passes + commit |
| `/adr <slug>` | `.claude/commands/adr.md` | Scaffold a new ADR with auto-numbering |
| `/spec <slug>` | `.claude/commands/spec.md` | Scaffold a new spec + paired BDD |
| `/research <slug>` | `.claude/commands/research.md` | Scaffold a new research note |

## Review passes

| Review | Protocol file | When | How to run |
|---|---|---|---|
| Architecture review | `codex/review-architecture.md` | Before completing a non-trivial implementation | Spawn an Agent subagent with fresh context (see protocol file) |
| BDD-evidence review | `codex/review-bdd-evidence.md` | After a test run on a feature with BDD scenarios | Inline pass at `/closeout` (it verifies evidence you just produced) |

## Build & test

```bash
python3 -m pytest tests/           # run unit tests
python3 evals/<eval>.py            # run a single eval script
```

**Current test posture:** All unit tests and evals passing (see `STATUS.md` for latest session log and current verification status, and `HANDOFF.md` for current implementation status).

## Commit norms

- One commit per coherent change. Messages describe **why**, not just what.
- ADR commits: `[ADR-NNNN]` prefix. Spec commits: `[spec:<feature>]` prefix.
- For every completed implementation packet, increment the patch component of
  the visible integration package version in both
  `custom_components/isolinear/manifest.json` and
  `custom_components/isolinear/const.py` unless the human explicitly says not
  to.
- Never skip hooks (`--no-verify`) unless the user explicitly asks. If a hook fails, fix the underlying issue and create a NEW commit; do not amend.
- Stage specific files. Never blanket `git add -A` / `git add .`.
- At `/closeout`, include a completion report in the commit body (see `.claude/commands/closeout.md` for format).
- Ask before pushing. Default is commit-only.

## What is out of scope (now)

- Home Assistant custom integration implementation (deferred until MVP design phase closes)
- Persistent semantic-memory storage-helper implementation, migrations, and repair UI beyond the completed envelope contract
- Exact dashboard card implementation technology
- Exact worker API transport and authentication
- Exact sandbox implementation details for Raspberry Pi compatibility
- Which chart primitives are included in the first trusted renderer release

## When in doubt

Ask the human. Direction is the human's call; implementation details are yours. If a spec is ambiguous, surface the ambiguity in chat and write the resolution into the spec before coding.
