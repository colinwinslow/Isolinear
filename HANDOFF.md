# HANDOFF.md

> **What this file is.** The current project phase, architectural direction,
> implementation status, and unresolved design details — the context a fresh
> session needs that isn't in the code. `STATUS.md` owns the current packet and
> the rolling session log; `ROADMAP.md` owns future work; `docs/gotchas.md`
> owns durable debugging knowledge.
>
> **2026-07-28 restructure.** This file previously carried ~4,150 lines of
> session history (~144k tokens loaded at every cold start, 7.5× its continuity
> budget). That history is preserved in git; only forward-looking and
> still-live content was kept. Anything below is current unless it says
> otherwise.

## Current project phase

### 2026-07-28 — answer-channel hardening; continuity docs restructured

**Where the project stands.** The model-authored analysis channel (ADR-0031 +
ADR-0034) is the active work front, and it now covers mean, delta, deviation,
distribution, rolling, correlation, two-sensor comparison and state-duration.
The last several packets have followed the same shape: a live reproduction
first, which repeatedly overturns the packet's stated premise, then a two-part
fix split across **emission** (a `_CODEGEN_PROMPT_RULES` sentence making the
quantity a mandatory deliverable) and **grounding** (an independent
deterministic recompute), gated by an eval that runs the production codegen
path with and without the rule. The LiteLLM / OpenAI-compatible provider
(ADR-0037) is the default and has been validated end to end. 0.2.47 is pushed
and live-deployed; its card-level eyes-on was never recorded.

**The recurring lesson, stated once.** Three consecutive packets were scoped
from a stale STATUS framing that a live repro then disproved — 0.2.44
("emission miss" was actually a verdict-basis contradiction), 0.2.46 ("verify
as caveats" was actually zero emission), and 0.2.47 ("multi-input rolling_mean
grounding" was actually a mean-of-a-rolling-average emission). Reproduce on the
real pipeline before designing. A synthetic backend reproduces a *different*
bug.

**Two diagnostic traps worth remembering.** A **withheld** answer is suppressed
on the card and looks identical to a plot-only response — check the grounding
outcome before concluding the model didn't answer. A **claimless** answer is
worse: it grounds as `outcome: pass` with `answer_verification` *absent*, so it
is served uncaveated and never checked; one run stated "4.0 %" against an
aligned truth of 4.63. Emission gaps and recompute gaps are different bugs.

**Continuity restructure (35th session, 2026-07-28/29, no product change).** A
fresh-context architecture review returned CONCERNS and its findings were
applied before commit — most importantly that the **Codex layer** (`AGENTS.md`,
`codex/startup.md`, `codex/closeout.md`) had been left pointing at the old read
set, which would have hidden every queued item from a Codex session, and that
**ADR-0035 has five demolition steps, not four**. `STATUS.md` was
rebuilt to the kit's template shape with a true rolling-5 log (now the 30th–34th
sessions; the 29th–33rd had never been logged there); `HANDOFF.md` was pruned to this
file; `ROADMAP.md` was created for forward-looking work; `docs/gotchas.md` was
created to rescue operational knowledge that existed only in session history.
`docs/ONBOARDING.md` was added for new engineers.

### 2026-07-23 (34th session) — cross-sensor smoothed-average emission fidelity (0.2.47)

The cross-sensor "average of X and Y smoothed with a rolling average" prompt
never emits a `rolling_mean` claim. Gemma computes
`align().mean(axis=1).rolling('2D', min_periods=1).mean().mean()` — the mean
*of* a rolling average — and emits it under a `{'metric':'mean'}` claim. That
quantity is window-dependent and ~0.11 °F off the plain mean (the gap grows
with the window: 30 min → 0.010, 2 d → 0.111), which is past the 0.05
tolerance, so `_compute_mean` correctly withheld a correct-*looking* answer.

Fix is **emission only** — grounding was deliberately left untouched so it
remains an independent drift detector. A `_CODEGEN_PROMPT_RULES` sentence pins
any stated average to the raw aligned frame (`frame.mean(axis=1).mean()`);
smoothing is a chart transform, not an answer transform. The spec §5
`rolling_mean` negative result therefore **stands** — no recompute change was
needed.

Proof: `evals/rolling_avg_emission_gate.py` on the production codegen path with
real recorder temperatures — with-rule 3/3 clean-emitting runs served and
verified at the plain mean 73.88, without-rule 0/5 (4 withheld
`repair_contradicted`). Suite 591/4. Arch review (fresh context) OK; no new ADR
(additive prompt rule under accepted ADR-0031 D8a).

### 2026-07-20 (32nd session) — two-sensor comparison answers (0.2.46)

Emission: a comparison question has the same shape as correlation — the gap is
a scalar with nothing new to plot — so a rule makes the average difference the
mandatory deliverable, computed off the aligned frame with `inputs` in the same
order as the subtraction. Grounding: `_compute_delta` for exactly two inputs
recomputes the aligned average difference (it previously took last-minus-first
of `inputs[0]`); three or more inputs return no reference.

**Two false-contradiction paths the arch review caught** — both are the
withhold-a-correct-answer failure mode, and both are now guarded:

1. The prompt prescribes `align(history_series)`, whose `dropna` spans *every*
   numeric column, while the recompute intersected only the two claim inputs.
   With a third numeric series the grids diverge (measured live: 5.40 vs 4.65,
   15× tolerance). Both defensible grids are now computed and a value matching
   either verifies.
2. `delta` is the first **order-sensitive** multi-input metric (mean and
   pearson are symmetric), so a sign-only disagreement now degrades to a caveat
   (`grounding_delta_sign_ambiguous`) instead of withholding.

A wrong magnitude still matches no candidate and contradicts, pinned by
`test_wrong_value_still_contradicts_despite_guards` — step 4 stays
load-bearing.

### 2026-07-19 (31st session) — binary/timeline routing for codegen (0.2.45)

A *primary* timeline series is not an overlay, so `_compute_overlay_bands`
(which only iterates `chart_spec['overlays']`) handed codegen empty
`derived_intervals` and the model derived on-regions from raw points badly —
an invariant-#9 gap on the codegen path since the 16th session. The fix
generalizes the ADR-0033 precompute to the primary series under spec
`timeline-codegen-rendering` (accepted; a bounded extension of
ADR-0022/0030/0031/0033, no new ADR): precomputed timeline bands reusing the
trusted Pillow `_binary_on_regions` logic, a `broken_barh` lane idiom, a
duration answer that sums the *precomputed* intervals, and a
`_compute_state_duration` grounding metric.

That last piece established a policy worth knowing: `state_duration` is treated
as a **descriptive, value-only metric class** — a spurious model verdict/rule
is nulled so a correct duration can't be contradicted — with a metric-aware
relative tolerance, since milliseconds dwarf the 0.05 default. The arch review
flagged this as decision-shaped and a candidate future ADR
(`value-only-metric-classes-in-grounding`).

## Product summary

Isolinear turns natural-language questions about approved Home Assistant
entities into validated charts **and grounded natural-language answers**,
computed from that entity history by sandboxed, model-authored Python.

## Current architecture direction

See **`docs/ARCHITECTURE.md`** — it is the current-state map (the spine, the
load-bearing decisions, the component weights, the deployment topology, and
what is slated for demolition), synced at `/closeout`. The decisions
themselves live in `docs/decisions/`; the enforced invariants live in
`CLAUDE.md`.

*(The prose list that used to live here was materially stale — it still called
the trusted chart-spec renderer the default path and sandboxed codegen an
"advanced path", which ADR-0030 inverted, and it named an Ollama-only provider,
which ADR-0037 superseded. It was deleted rather than preserved.)*

## Implementation status

The 0.1.x implementation history — the fake vertical slice, the first real
vertical slice, the Home Assistant scaffold / config-flow / WebSocket /
orchestration anchors, the trusted Pillow renderer families, the
reasoning-streaming saga, semantic aliases, and the ADR-0023 capability
envelope — is **complete**, and its record lives in git history, the ADRs, and
`docs/specs/`.

Two notes on reading that history: the ADR-0015/0016 durable token-lifecycle
and health-polling scaffolds it describes were **deleted** by ADR-0032, so any
prose about them describes code that no longer exists; and the ADR-0023
envelope machinery it treats as new is now an ADR-0035 demolition target.

Current implementation state is best read from `STATUS.md` (version, suite
count, deploy state) and `docs/ARCHITECTURE.md` (component map).

## Known unresolved design details

- **Overlay follow-ups** — overlay for ≥2 numeric primaries (multi-axis),
  overlay on the `timeline` family, and categorical (non-binary) overlays.
  Also a dedicated `timeline_history_unavailable` failure code for
  beyond-retention binary windows (0.1.25/0.1.26 reuse
  `no_long_term_statistics`).
- **Semantic memory** — migrations and a repair UI beyond the shipped
  envelope contract and the save/load/match tranches.
- **Allowlist picker ergonomics** beyond Home Assistant's native multi-entity
  selector (device/area/label grouping). **Constraint: the stored allowlist
  must remain explicit entity IDs.**
- **Production entity/device/area/label registry adapters** beyond the
  scaffold-compatible approved-entity metadata shape. Best-effort registry
  enrichment exists; a production adapter contract does not.
- **A true live browser smoke** of the dashboard card against a real HA dev
  server. The live e2e harness drives the real card path and produces eyes-on
  PNGs, but nothing exercises the browser itself — which is also where the
  stale-bundle-cache trap lives.
- **Worker packaging for multi-arch / Raspberry Pi images.** The amd64 build is
  done (ADR-0029 packet 3, with scipy + seaborn); multi-arch is deferred.
- **Grounding tolerance coarseness** — a single global `_TOLERANCE = 0.05`
  spans correlation, means and hour-counts. Arch review called this accepted
  tranche-1 coarseness; only `state_duration` has a metric-aware relative
  tolerance so far.

## Session log

Per-session details live in `STATUS.md` (rolling 5-entry log) and git history.
Older sessions are archived in git commits — `git log --follow HANDOFF.md` will
surface the full pre-2026-07-28 phase history if you need it.
