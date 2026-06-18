# Architecture Review Pass

Reviews a diff against this project's load-bearing invariants. Run **before
completing any non-trivial implementation**.

## How to run it (Claude Code)

For an honest, un-anchored read, spawn a fresh Agent subagent so the reviewer
starts with clean context instead of the rationalizations built up while
implementing:

```
Agent({
  description: "Architecture review",
  subagent_type: "code-reviewer",
  prompt: "You are an architecture reviewer for the Isolinear project.
Read CLAUDE.md and codex/review-architecture.md in this repo, then review
the current branch diff (git diff main...HEAD) against the project invariants.
Output the verdict format from the protocol (Verdict / Invariant violations /
Scope flags / ADR-relevance / Recommendations). Under 400 words."
})
```

(If spawning an agent is impractical, do it inline as a deliberate, skeptical
pass — but a fresh subagent is the recommended form.)

## What you check

The **invariants listed in `AGENTS.md`**. For each one, ask: does this diff
violate it? Match the change against the rule, don't just restate the rule.

Also flag:

- **Scope creep** — does the change add capability beyond what the current
  bounded packet needs? Unrequested abstractions, speculative generality,
  features built for hypothetical futures.
- **Anchor-artifact discipline** — is supporting infrastructure being built
  before the visible thing exists? The simplest concrete observable artifact
  should ship first.
- **BDD-tree pattern** — does a new spec inline its BDD scenarios instead of
  putting them in `bdd/<feature>/<slug>-bdd.md`?
- **Decision-worthiness** — did this change make a decision that should be
  recorded as an ADR but wasn't?

## Inputs to gather

- The diff or changed files (`git diff <ref>` or specific paths)
- `AGENTS.md` (the invariants)
- The relevant spec(s) under `docs/specs/` and the ADRs they cite
- The paired BDD under `bdd/<feature>/` if a spec is involved

## Output format

Brief (under 400 words):

```
## Verdict
[OK / CONCERNS / VIOLATIONS]

## Invariant violations
[Per-invariant. None if clean.]

## Scope / discipline flags
[Scope creep, anchor-artifact, BDD-tree concerns. None if clean.]

## ADR-relevance
[Did this change make a decision that should be ADR-recorded? Propose a slug.]

## Recommendations
[Concrete, file-and-line where possible. None if clean.]
```

## Rules

- Don't rewrite the diff. Report findings; let the caller decide.
- If the diff is small and clearly inside the invariants, say "OK" tersely.
  Don't pad.
- Be specific: cite the invariant by name and the file/line that conflicts.
