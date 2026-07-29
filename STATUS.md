# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file, `HANDOFF.md`
> and `ROADMAP.md`. `/closeout` updates it. Keep it current; keep it short.
>
> Companions: **`ROADMAP.md`** = everything not yet started or finished.
> **`HANDOFF.md`** = current phase + unresolved design details.
> **`docs/ARCHITECTURE.md`** = the current-state architecture map.
> **`docs/gotchas.md`** = durable debugging knowledge.

**Last updated:** 2026-07-29 (`continuity trim — STATUS/HANDOFF restructured to the kit's rolling-5 shape; ROADMAP.md + docs/gotchas.md + docs/ONBOARDING.md added. No product change.`)
**Phase:** `Answer-channel hardening on the codegen path (ADR-0031/0034) — the channel now covers mean, delta, deviation, distribution, rolling, correlation, comparison and state-duration. LiteLLM/OpenAI-compatible provider (ADR-0037) is the default and live-validated. ADR-0035 demolition steps 2–4 outstanding.`
**Next bounded packet:** `Live eyes-on confirming the 0.2.47 cross-sensor smoothed-average serves on the card (0.2.47 is deployed, but that confirmation was never recorded). Then pull from ROADMAP.md — (gg) the LiteLLM context-overflow safety net, (t) the >2-day tiering-wall ADR, or (F) cosmetics.`
**Current readiness:** `READY-FOR-NEXT-PACKET — main == origin/main at 0.2.47, live-deployed (verified 2026-07-28 via WS manifest/get), suite 591 passed / 4 skipped.`

> **⚠️ Direction (2026-07-02, ADR-0030):** matplotlib codegen via the sandboxed
> worker is the PRIMARY render path; Pillow is the surfaced fallback; the model
> is empowered to transform data in generated code. The 2026-06-12 reality
> pivot completed — the simulated scaffold is deleted (`f8f7760`) and pytest is
> the single source of behavioral truth (`docs/reality-pivot-review.md` is
> historical context).

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older
> sessions live in git history.

- **2026-07-28/29 (35th session)** — `Continuity restructure — the always-loaded docs go from 215k to 18k tokens` —
  No product change; version stays 0.2.47, suite 591/4. `STATUS.md` (66k
  real-tok, 6.9× over budget) and `HANDOFF.md` (144k, 7.5× over) were rebuilt:
  STATUS to the kit template with a true rolling-5, HANDOFF to the current
  phase plus the tail sections. Forward-looking work moved to a new
  **`ROADMAP.md`**; operational knowledge that existed only in deleted session
  history was rescued into **`docs/gotchas.md`**; **`docs/ONBOARDING.md`** was
  written for new engineers. Total cold-start continuity load: **214,764 →
  17,755 real-tok**, all four files under budget.
  **Corrections found while verifying claims:** 0.2.47 is pushed *and*
  live-deployed (STATUS said commit-only — confirmed via `git` and WS
  `manifest/get`); the worker runs on **CT106**, not CT103, from the GHCR
  image; HANDOFF's "Current architecture direction" still called Pillow the
  default path and codegen "advanced", contradicting invariant #6, and was
  deleted rather than preserved.
  **Arch-review subagent RUN (fresh context, via `general-purpose`) —
  CONCERNS→RESOLVED.** It caught: the Codex layer (`AGENTS.md`, `codex/*`) was
  never updated, so a Codex `/startup` would have seen zero forward-looking
  work; `ONBOARDING.md` §10 was written pre-verification and contradicted the
  corrected deploy state; **ADR-0035 has five demolition steps, not four** (step
  5 = archive the ADRs each step obsoletes + sync ARCHITECTURE at each
  closeout). All fixed, plus five items that had vanished with no home
  (card-legend spec promotion, legend-manifest family extension, (x) closure,
  the delta sign-off, the e2e-14 card verification) and six additions to
  gotchas — chief among them the **BDD carve-out** (a prompt-rule or bug-fix
  packet on an accepted contract ships an eval gate + unit tests *instead of* a
  BDD), which ~6 recent packets applied but nothing wrote down. Rejected one
  finding: the OpenBLAS sandbox reason is already a code comment, so it fails
  the file's not-recoverable-from-code bar.
  Also: stale `WORKER_URL` defaults in three eval scripts repointed .39→.46.

- **2026-07-23 (34th session)** — `0.2.47 — cross-sensor smoothed-average emission fidelity` —
  A reproduce-first packet that **overturned its own premise**: the stale framing
  "multi-input rolling_mean grounding" was wrong. The live repro
  (`scripts/repro_delta_rolling_grounding.py`, case `rolling_cross`, 4/4 withheld)
  showed the cross-sensor smoothed-average prompt never emits a `rolling_mean`
  claim at all — gemma computes the mean *of* a rolling average and reports it
  under a `{'metric':'mean'}` claim, a quantity ~0.11 °F off the plain mean and
  so past the 0.05 tolerance, meaning `_compute_mean` correctly withheld a
  correct-looking answer. **Fix is emission-only** (grounding untouched, still an
  independent drift detector): a `_CODEGEN_PROMPT_RULES` sentence pins any stated
  average to the raw aligned frame — smoothing is a chart transform.
  Eval-gated (`evals/rolling_avg_emission_gate.py`): with-rule 3/3 clean runs
  served + verified at the plain mean 73.88, without-rule 0/5. Suite 591/4.
  Arch-review (fresh context) OK; no new ADR. Also found: the local exec harness
  `.expenv` had drifted to pandas 3.x while the worker pins 2.x, turning real
  withholds into spurious runtime errors — use `/home/claude/.workerenv` as
  `EXEC_PY` (see `docs/gotchas.md`).

- **2026-07-22 (33rd session)** — `Claude-layer alignment with the agentic-workflow-kit` —
  Workflow-only, no product change (version stayed 0.2.46, suite 590/4).
  Native slash commands gained frontmatter + `$1`; review subagents registered
  (`code-reviewer`→`arch-reviewer` keeping `model: inherit`, plus
  `bdd-evidence-reviewer`); branch-agnostic drift checks; a fail-open
  SessionStart hook; and the continuity-budget guard ported and switched on.
  Two deliberate deviations from the kit: isolinear keeps its Codex layer
  (`codex/`, `AGENTS.md`) and its `claude/` config path. Committed + pushed as
  `6ed0091`.

- **2026-07-20 (32nd session)** — `Two-sensor comparison answers (0.2.46) + both deploy gates closed` —
  First **recovered** the 31st session's stranded packet: 0.2.45 sat staged in
  the index while STATUS claimed it was committed; the tree was verified
  (578/4) and landed as `8334dfe`. Then closed both deploy gates live on 0.2.45
  — (r) timeline Scenario A confirmed (clean off-track lane + a grounded,
  verified 8-second duration → spec promoted to accepted) and the 0.2.44
  correlation basis fix confirmed. Then shipped comparison answers, another
  packet whose **premise the live repro overturned**: across 7 production-path
  runs *zero* emitted a claim, so the dominant failure was emission, not
  recompute — and worse than a caveat, because a claimless answer grounds as
  `pass` with `answer_verification` **absent** (served uncaveated, never
  checked). Two-part fix: an emission rule making the average difference
  mandatory, and `_compute_delta` recomputing the aligned average difference for
  exactly two inputs. Arch review reproduced two false-contradiction paths the
  fix had opened (divergent align grids; delta being the first order-sensitive
  metric) — both resolved. Suite 590/4.

- **2026-07-19 (31st session)** — `(r) binary/timeline routing for the codegen render path (0.2.45)` —
  Live-reproduced e2e-09 first on the deployed 0.2.42: it drew ~4 near-zero
  axvspan verticals on a fake Open/Closed axis plus a degenerate "0.0 minutes"
  answer. Root cause: a *primary* timeline series is not an overlay, so
  `_compute_overlay_bands` handed codegen empty `derived_intervals`. Fix
  generalizes the ADR-0033 precompute to the primary series (spec
  `timeline-codegen-rendering`, no new ADR): precomputed timeline bands reusing
  the trusted Pillow region logic, a `broken_barh` lane idiom, a duration answer
  summing the precomputed intervals, and a `_compute_state_duration` grounding
  metric with a metric-aware relative tolerance. Eval-gated with/without the
  render rule. Suite 578/4. Arch review CONCERNS→resolved.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Live confirmation of 0.2.47` — not started

- [ ] Eyes-on the card for the cross-sensor smoothed-average prompt ("the
      average of the kitchen and basement temperatures smoothed with a rolling
      average") — confirm it SERVES a plain-mean number with
      `answer_verification: verified`, rather than withholding.
- [ ] If clean, note it in the rolling log and pull the next item from
      `ROADMAP.md`.

## Blockers

- None.
