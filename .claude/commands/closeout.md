# Closeout protocol

Use this protocol before ending every session.

## Steps

1. Run relevant tests (`python3 -m pytest tests/ -q`).
2. Run relevant evals if they exist (`python3 evals/<eval>.py`).
3. Check for drift against relevant ADRs, specs, BDDs, and schemas.
4. Run the BDD-evidence review pass (inline — read `codex/review-bdd-evidence.md` and follow it).
5. Run the architecture review pass if non-trivial implementation was done (see `codex/review-architecture.md`).
6. Update `HANDOFF.md` with what changed and what remains.
7. Report files changed.
8. Report tests and evals run.
9. Report skipped verification, if any.
10. Propose a commit message that matches the task subject.

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
