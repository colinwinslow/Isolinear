---
description: End a session cleanly — run tests/evals, review passes, update STATUS.md + HANDOFF.md, commit. Don't push without asking.
---

End a work session. Leave the repo clean and understandable for the next
session. **Don't push without asking.**

## Steps

1. **Run relevant tests.** `python3 -m pytest tests/ -q` (and any single-file
   runs the session's work touched).

2. **Run relevant evals** if they exist (`python3 evals/<eval>.py`).

3. **Confirm what changed this session.** `git status` and `git diff --stat`.
   Read back the changed files. If files changed that don't fit the session
   narrative, surface to the user before committing.

4. **Check for drift** against relevant ADRs, specs, BDDs, and schemas.

5. **BDD-evidence review pass** — if a feature with BDD scenarios was
   implemented. Spawn the `bdd-evidence-reviewer` subagent (or run the review
   inline per `codex/review-bdd-evidence.md`) and confirm each scenario was
   honestly hit with raw evidence — not just claimed-as-passing.

6. **Architecture review pass** — if non-trivial implementation was done. Spawn
   the `arch-reviewer` subagent with fresh context (protocol:
   `codex/review-architecture.md`). Do not self-exempt a closeout as "bounded" —
   run the fresh-context pass at non-trivial closeouts.

7. **Update `STATUS.md`:**
   - Update the `Last updated:` date + the new session entry (packet name, 1–3
     sentences on what closed/changed) at the top of the rolling session log.
   - **Keep the rolling log to the last 5 sessions.** Trim the oldest `_(prior)_`
     entry when the section exceeds 5 — old sessions live in git history.
   - Tick/adjust the current bounded packet + `Next` if it changed.

8. **Update `HANDOFF.md`** with the current phase, what changed, and what
   remains (the "Next" list).

9. **Continuity budget** (when `continuity_tracking` is enabled in
   `claude/workflow-config.json`). If this session's `/startup` surfaced a
   `CONTINUITY BLOAT:` warning — or to check now — run
   `python3 scripts/continuity_budget.py --check`. For each file it flags, trim
   it back under budget as part of this closeout: enforce `STATUS.md`'s
   rolling-5, and prune stale `HANDOFF.md` / `ROADMAP.md` entries (old detail
   lives in git history). Re-run `--check` and confirm it is quiet before
   committing. This is the discipline the guard exists to keep honest.

10. **Sync doc indexes** if any status changed this session:
    - ADR `draft` → `accepted`: update `docs/decisions/README.md` per its
      index-label convention.
    - New spec/research note: confirm it's listed in the relevant README.

11. **Version bump.** For every completed implementation packet, increment the
    patch component in BOTH `custom_components/isolinear/manifest.json` and
    `custom_components/isolinear/const.py`, unless the user says not to.

12. **Stage and commit.** Stage specific files. Use a HEREDOC for the message.
    Conventions per `CLAUDE.md`: `[ADR-NNNN]` for ADR commits, `[spec:<feature>]`
    for spec commits; describe **why**, not just what.

13. **Confirm `git status` is clean** after the commit (modulo the known
    untracked scratch/private artifacts).

14. **Ask before pushing.** Default is commit-only. If the user confirms,
    `git push origin <branch>` (branch-agnostic — never hardcode `main`).

15. **Optional spend footer.** When `spend_tracking` is enabled in
    `claude/workflow-config.json`, close with a spend line per
    `claude/spend-tracking.md`.

## Slice-closing completion report (in the commit body)

When a slice closes, the commit body includes:

- **Completed slice** — name/number
- **What it does** — goal + sub-steps in plain language
- **Tests run** — exact commands
- **What each test proves** — one line per test/group
- **BDD verification** — scenario, input, expected, observed
- **Artifact verification** — files the user can inspect on disk
- **Open gaps** — any mismatch between implementation, tests, and BDD
- **Next slice** — the next bounded step

Brief commits (doc tweaks, dependency bumps) skip the report.

## Rules

- Never `--no-verify` or skip hooks unless the user explicitly asks.
- Never amend a commit; create a new one if follow-up is needed.
- If a pre-commit hook fails, fix the underlying issue and create a new commit.
- **Do not run `git add -A` or `git add .` blindly. Stage specific files.**
- A slice is not complete until the real artifact has been verified on disk.
