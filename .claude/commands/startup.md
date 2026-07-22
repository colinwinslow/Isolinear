---
description: Ground the session — drift-check git, read STATUS.md + HANDOFF.md, name the next bounded packet and its proof.
---

Start a work session. Ground the session before changing anything: drift-check
the repo, read current state, identify the next bounded packet and the proof
required to close it.

**Run steps 1–6 quietly.** Do not narrate step transitions ("Now reading
STATUS", "Now the gate check"). Execute the steps and surface text ONLY when a
step needs a user decision (a dirty tree in step 1, a STATUS/HANDOFF
discrepancy in step 5) or hits a blocker. Everything else stays silent until the
step-6 report-back.

## Steps

1. **Drift check** (run from the repo root, branch-agnostic):

   ```bash
   git fetch origin --quiet
   git status --porcelain
   git rev-list --count HEAD..@{u}    # commits behind the tracked upstream
   ```

   - If the working tree is **non-empty** (uncommitted changes): surface to the
     user and do **not** proceed without their decision — stash, leave in place,
     or commit (user picks). Stash command:
     `git stash push --include-untracked --message "auto-stash from /startup <DATE>"`.
   - If the branch is **behind** upstream: `git pull --ff-only` and surface the
     new commits.
   - Re-run `git status --porcelain` to confirm clean.

   > NOTE: isolinear has legitimate untracked working-tree churn (private e2e
   > run dirs, repro scripts, eval result JSON). A non-empty `git status` is
   > normal here — judge whether the churn is TRACKED changes vs. gitignored/
   > scratch artifacts before treating it as drift.

2. **Read the required set: `STATUS.md` + `HANDOFF.md`.** `STATUS.md` is the
   single source for the current bounded packet and rolling session log;
   `HANDOFF.md` carries the current phase, architectural direction, and
   unresolved design detail. Do not load other docs unless the work requires
   them — the doc map in `CLAUDE.md` says when to load what.

3. **Read repo-local strategy, if present.** `ROADMAP.md` (strategic direction),
   if the project keeps one. Skip if absent — isolinear leans on `STATUS.md` +
   `HANDOFF.md` today; `ROADMAP.md` is optional and loaded only when present.

4. **Continuity budget check** (when `continuity_tracking` is enabled in
   `claude/workflow-config.json`). Run the fail-open guard over the
   always-loaded continuity files (`CLAUDE.md`, `STATUS.md`, `HANDOFF.md`,
   `ROADMAP.md`):

   ```bash
   python3 scripts/continuity_budget.py --check --snapshot
   ```

   `--check` is silent when everything is within budget. If it prints any
   `CONTINUITY BLOAT:` line, surface those lines verbatim — they are the signal
   to **trim that file at the next `/closeout`** (keep `STATUS.md`'s rolling-5,
   prune stale `HANDOFF`/`ROADMAP` entries; old detail lives in git history).
   `--snapshot` quietly appends one continuity-size row to the shared cross-repo
   ledger so a size trend accumulates. Read-only, always exits 0 — never blocks.
   If `continuity_tracking` is disabled, skip this step.

5. **Identify the next bounded packet** from `STATUS.md` "Active work" / the
   current packet, informed by `HANDOFF.md`'s "Next" list and `ROADMAP.md` if
   present. A *bounded packet* is one coherent, shippable unit of work with a
   clear proof — not an open-ended phase. If `STATUS.md`, `HANDOFF.md`, and
   `ROADMAP.md` disagree on what's next, surface the discrepancy; do not silently
   pick one.

6. **Report back.** A short, high-signal summary — not a 50-line prose dump:
   - drift-check result (clean / fast-forwarded / stash created / pending user)
   - the next bounded packet and what kind of work it is (implementation,
     research, BDD authoring, ADR drafting, or a mix)
   - the **proof required to close it** (which unit tests? which BDD scenarios?
     what real artifact verified on disk?) — confirm this *before any code
     changes begin*
   - any blockers or doc conflicts (stop and surface rather than normalize away)

   **Optional spend footer.** When `spend_tracking` is enabled in
   `claude/workflow-config.json`, close with a spend line per `claude/spend-tracking.md`.

## Default verification question

Before editing, answer:

> What behavior will prove this task is complete?

## Rules

- Do not invent project direction. It comes from `STATUS.md` / `HANDOFF.md` and
  the user.
- Do not begin implementation until the next packet is clear and the proof is
  confirmed.
- If docs conflict, report the conflict and wait for resolution.
- Keep the read set minimal: `STATUS.md` + `HANDOFF.md`. Other docs load only
  when the work requires them (see the doc map in `CLAUDE.md`).
- Never start grounding while the checkout has drifted (TRACKED) state without an
  explicit user decision.
