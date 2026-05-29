# Codex closeout protocol

Use this protocol before ending every Codex session.

## Steps

1. Run relevant tests.
2. Run relevant evals if they exist.
3. Check for drift against relevant ADRs, specs, BDDs, and schemas.
4. Update `HANDOFF.md` with what changed and what remains.
5. Report files changed.
6. Report tests and evals run.
7. Report skipped verification, if any.
8. Propose a commit message that matches the task subject.

## Closeout template

```text
Summary:
- ...

Files changed:
- ...

Verification:
- ...

Skipped checks:
- ...

Spec drift:
- None / Needs update: ...

Recommended commit message:
- ...
```
