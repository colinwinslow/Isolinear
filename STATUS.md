# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file, `HANDOFF.md`
> and `ROADMAP.md`. `/closeout` updates it. Keep it current; keep it short.
>
> Companions: **`ROADMAP.md`** = everything not yet started or finished.
> **`HANDOFF.md`** = current phase + unresolved design details.
> **`docs/ARCHITECTURE.md`** = the current-state architecture map.
> **`docs/gotchas.md`** = durable debugging knowledge.

**Last updated:** 2026-08-07 (`0.2.48 — repair-prompt rule pruning; the stable-7 e2e failures went 0/7 → 6/7.`)
**Phase:** `Answer-channel hardening on the codegen path (ADR-0031/0034) — the channel now covers mean, delta, deviation, distribution, rolling, correlation, comparison and state-duration. LiteLLM/OpenAI-compatible provider (ADR-0037) is the default and live-validated. ADR-0035 demolition steps 2–4 outstanding.`
**Next bounded packet:** `Colin's call on the e2e-21 intent question (does "show the average … smoothed" require a scalar answer?) — it decides whether ROADMAP (jj) is a bug or a bad test, and the 0.2.47 card-level proof depends on it. Then (ii) the e2e-04 KeyError, or (hh) the retry-policy schema bug.`
**Current readiness:** `READY-FOR-NEXT-PACKET — main == origin/main at 0.2.48, live-deployed and verified 2026-08-07 via WS manifest/get, suite 601 passed / 4 skipped.`

> **⚠️ Direction (2026-07-02, ADR-0030):** matplotlib codegen via the sandboxed
> worker is the PRIMARY render path; Pillow is the surfaced fallback; the model
> is empowered to transform data in generated code. The 2026-06-12 reality
> pivot completed — the simulated scaffold is deleted (`f8f7760`) and pytest is
> the single source of behavioral truth (`docs/reality-pivot-review.md` is
> historical context).

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older
> sessions live in git history.

- **2026-07-30/08-07 (36th session)** — `0.2.48 — the repair prompt was truncating; stable-7 e2e failures 0/7 → 6/7` —
  A measure-first packet that **overturned two standing beliefs**. The 7 e2e
  prompts that failed identically across both 0.2.47 runs were emitting
  mock-data boilerplate (`np.random.seed(42)`, 2023 `date_range`, `_mock`
  arrays) and failing the static gate as `unsafe_code`. The standing theory —
  recorder points overflowing the context — was **already fixed and wrong**:
  Colin correctly recalled the 12-point preview, and it holds (550–950 tok
  against 2,900 raw points). New `scripts/measure_codegen_prompt.py` built the
  real payloads from live recorder data and asked the REAL tokenizer
  (`num_predict=1` → `prompt_eval_count`): **generation fits at 58–79%, every
  repair pinned at exactly 8192 — truncated.** Ollama drops leading tokens, so
  the repair loop was evicting the system prompt and rules — the contract it
  exists to enforce. A chars/token estimate could not have found this (real
  ratios 2.41–3.51, not 4.0; that gap *is* the fits-vs-truncates margin).
  Fix (`_repair_prompt_rules`): repair sends the contract core plus only the
  rule families its failure class implicates; generation untouched; fails open
  on an unmatched rules list so eval arms still work. Proof: 10 new unit tests,
  suite 601/4, and **4 live e2e passes** (2 pre-fix, 2 post-fix) — stable-7
  **0/7 → 6/7**, `unsafe_code` gone from 42 post-fix prompts, answer emission
  roughly doubled (2–3 → 4–7 of completed askers), median 153.8s → ~79s.
  **Methodology finding that outlives the packet:** two runs on unchanged code
  flipped 5/19 prompts (~26%), so single-run A/B is worthless — judge changes on
  the always-fail set, report eventual success across passes. Both now in
  `docs/gotchas.md`. Also: the HA token rotated mid-session and killed a run
  (`scripts/ha_token.py` now resolves it from the homelab SOPS vault with a
  negative-control `--check`); Colin's template-render-tier proposal scoped in
  `docs/research/template-render-tier.md` and **de-prioritized** once the
  failures proved to be a truncation bug rather than a capability ceiling.
  Opened: (hh) retry-policy schema bug, (ii) e2e-04 `KeyError: 'bedroom'`,
  (jj) e2e-21 emits no answer + gate-vs-live disagreement.

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

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `0.2.48 repair-prompt rule pruning` — COMPLETE

- [x] Measure the real codegen prompt budget with the real tokenizer
      (`scripts/measure_codegen_prompt.py`, `LIVE_TOKENS=1`).
- [x] Prune repair rules to the failure class; leave generation untouched.
- [x] Unit proof: `tests/test_repair_rule_pruning.py` (10 tests). Suite 601/4.
- [x] Live proof: 2 pre-fix + 2 post-fix e2e passes. Stable-7 **0/7 → 6/7**;
      `unsafe_code` absent from 42 post-fix prompts.
- [x] Deployed and verified live at 0.2.48 (WS `manifest/get`), pushed.

### `Next` — blocked on one decision

- [ ] **Colin's call:** does *"show the average of X and Y smoothed with a
      rolling average"* require a scalar answer, or is the derived series the
      answer? Decides whether ROADMAP (jj) is a bug or a bad test expectation,
      and gates the 0.2.47 card-level proof.
- [ ] Then (ii) e2e-04 `KeyError: 'bedroom'` — the one stable-7 holdout, now a
      genuine `runtime_error` rather than the truncation artifact.
- [ ] Then (hh) the retry-policy schema bug — capture the offending policy
      object before attempting a fix.

## Blockers

- None blocking work; (jj) is blocked on the intent decision above.
- **Environmental, recurring:** the model provider degrades mid-run (connection
  errors + timeouts late in a 21-prompt pass, seen in pre-1 and post-2). Not
  caused by any packet; it corrupts long A/B runs and is worth its own look.
