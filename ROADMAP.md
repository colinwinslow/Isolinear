# ROADMAP.md — Isolinear

> **Forward-looking work.** Everything here is *not yet started* or *not yet
> finished*. `STATUS.md` owns the current packet and the rolling session log;
> this file owns what comes after. Pull from here when the active packet
> closes. Loaded at every session start, so keep entries tight — the reasoning
> belongs in the ADR/spec, not here.
>
> Letter tags are historical and referenced throughout git history and
> `HANDOFF.md`; they are kept even though they are no longer alphabetical.

## Strategic — the ADR-0035 demolition plan

ADR-0035 (accepted 2026-07-06) declared the v0.3 north star — the product is
saved, re-runnable, model-authored analysis code — and attached a sequenced
demolition plan. Step 1 landed in 0.2.28.

- [x] **Step 1 — split the `job_orchestration.py` god module.** Done 2026-07-07
  (0.2.28), seven seam modules + a facade, behavior-preserving.
- [ ] **Step 2 — retire the `first_real_vertical_slice` gate (ADR-0017).** A
  completed milestone whose flag still threads the facade plus render/history
  dispatch (~19 refs). Safe to do now.
- [ ] **Step 3 — shrink ChartSpec to a pure planning/intent contract.** Remove
  the render-side surface (`render_as`, envelope widening). Gates on e2e
  evidence.
- [ ] **Step 4 — retire the Pillow histogram/aggregate_bar families and the
  ADR-0023 envelope machinery** once codegen-authored presentation demonstrably
  covers those prompts. Pillow itself stays as the narrowed surfaced fallback
  (numeric lines + raw-states step track). Gates on e2e evidence.
- [ ] **Step 5 — archive the ADRs each step obsoletes** (0017 and 0023
  expected; others as they fall) and **sync `docs/ARCHITECTURE.md` at each
  `/closeout`**. This is a per-step obligation, not a final one.
- [ ] **The saved-viz slice itself** — the `saved_viz_id` record + the
  model-free refresh loop described in ADR-0035. Not yet specced.

## Next-packet candidates

- **(gg) Restore the context-overflow safety net on the LiteLLM path.** The
  detector is inert on the OpenAI-compatible provider: `_context_overflow()` is
  only called inside `OllamaCompatiblePlannerClient`'s codegen methods (the
  OpenAI subclass overrides them) and `_provider_response_summary` reads
  Ollama-native `prompt_eval_count`, which OpenAI responses don't carry. Fix:
  carry `usage.prompt_tokens` into the OpenAI response summary and run the
  existing check — **measured**, Ollama's `/v1` returns HTTP 200 with
  `usage.prompt_tokens` capped at exactly 8192 on a ~14k-token prompt, so
  `usage.prompt_tokens >= num_ctx` is a drop-in replacement. A cloud backend
  would instead need the 400 `context_length_exceeded` classified into the same
  `codegen_context_overflow` failure. **Caution:** the detector compares against
  `_CODEGEN_NUM_CTX` while the *effective* context is set server-side by
  `OLLAMA_CONTEXT_LENGTH` — surface that coupling loudly rather than silently
  mis-calibrating.

- **(t) The >2-day state-overlay tiering wall (e2e-04) — needs a small ADR.** A
  numeric+state overlay prompt spanning more than 2 days fails at
  `approved_history_retrieval` with `no_long_term_statistics` before any render:
  `RAW_TIER_MAX_SPAN=2d` plus ADR-0021's single-source-per-window rule routes
  *every* series — including the state entity — to the long-term-statistics
  tier, which a state entity lacks. Proven: short-window e2e-10 passes,
  five-day e2e-04 fails. Design fix: per-KIND tiering (numeric from statistics,
  state overlays from recorder raw states inside retention in the same window),
  or cap the overlay to the raw-retention sub-window. Touches the ADR-0021
  single-source invariant, so it needs an ADR.

- **(F) Cosmetics bucket.** Timeline on-bar `#ffe0b2` is low-contrast against
  the grey off-track; the correlation verdict string splices mid-sentence
  ("temperatures Not really move together"); e2e-20 shows a generic
  "Temperature" legend label; legend colour-fidelity (self-reported colours ≠
  drawn, e2e-14); e2e-14 mixed °F/% axis; raw-epoch x-axis variance; e2e-09
  y-tick shows the raw entity id (`kitchen_door`) not the friendly name; the
  timeline lane label clips against the axis.

- **(s) Histogram unit — likely fixed, confirm before closing.** The
  16th-session bug put °F on the density y-axis and "Value" on the x. The
  18th-session live run (e2e-16) rendered correctly ("Temperature (°F)" x,
  "Frequency (Count)" y). Re-confirm across a couple of runs — it may be model
  variance — before closing. Residual: the axis-WORD cosmetic (device_class →
  "Temperature") still applies where the model picks "Value".

## Open gaps

- **(aa) Latent codegen stray-quote guard-branch emission.** While diagnosing
  (w), 2/3 counterfactual runs emitted a dead-code "data not found" guard
  containing `transform=ax.transAxes')` — a stray quote → `syntax_error`,
  re-emitted on every repair attempt (temperature 0 regenerates its own bug, so
  more repair budget won't help). Not heatmap-specific. Worth a prompt nudge
  against the guard-branch preamble, or a targeted repair hint.

- **(g) part 2 — per-entity vs all-or-nothing catalog rebuild.** One
  unresolvable allowlist entry currently clears the whole catalog. Should it
  fail per-entity instead? (Part 1 and the original `kitchen_door` root cause
  were closed in 0.1.24/0.1.25 under ADR-0022.)

- **(i) Overlay follow-ups.** Overlay for ≥2 numeric primaries (multi-axis);
  overlay on the `timeline` family; a dedicated `timeline_history_unavailable`
  failure code for beyond-retention binary windows (0.1.25/0.1.26 reuse
  `no_long_term_statistics`).

- **(r) residual — categorical multi-lane polish.** `_compute_timeline_bands`
  (C1) handles categorical (HVAC-mode) multi-lane, but only the binary case is
  anchored and eyes-on'd.

- **(k) Cosmetic: planning-phase label during deferred selection.** After
  ADR-0026 some in-progress polls show `progress.message` = "Approved entities
  are staged for model planning." (the static deferral-snapshot message)
  instead of "Planning chart…"; reasoning still streams. `apply_live_reasoning`
  should normalize the message/stage to the active phase label on the
  entities-bearing planning snapshot.

- **(o) Eval-gate the generation-side bare-non-ASCII rule for retirement.** The
  `_CODEGEN_PROMPT_RULES` "labels must be string literals; no bare `°`/`%`"
  rule (0.2.13) is failure-driven, and the 0.2.17 unit-from-data rule made it
  doubly redundant (the model reads `°` from `history_series[i]['unit']`, a str
  variable). Strong candidate to drop — run `evals/codegen_reliability.py` with
  and without it first. Per the standing division: contract rules stay; style
  hints must earn their accept-rate.

- **(p) residual — e2e harness hardening.** Hard assertions and
  `series_plotted` / `unit_used` metadata. The harness itself is done and is a
  standing tool.

- **(a)/(b) Missing executable evals.** Aggregate-style ambiguous entity
  clarification (a); aggregate alias creation/reuse (b). Both beyond the
  existing threshold-backed proofs.

- **Stranded spec promotion — `docs/specs/card-level-legend-codegen.md` is
  still `status: draft`** while its evidence file records all four scenarios
  proven and Scenario A confirmed live on 2026-07-17. Colin's eyes-on of the
  0.2.43 line-sample swatch was the last gate; promote draft→accepted.

- **Extend the legend manifest + card-level legend to the `timeline`,
  `histogram` and `aggregate_bar` families.** Deferred follow-up from the
  ADR-0027 work — currently only `time_series` is covered. Note this
  intersects ADR-0035 step 4, which may retire the latter two families.

- **(x) e2e-09 zero-duration intervals — believed closed, never recorded as
  such.** 0.2.45's duration answer sums precomputed intervals and live-verified
  "0 minutes and 8 seconds" on the deployed build, which should have resolved
  the "16:45 to 16:45" degenerate output. Confirm on one live run and strike it,
  or reopen with evidence.

- **Verify e2e-14 resolves both sensors through the card.** An unchecked HACS
  redownload + verification step carried since 0.2.29; the cross-metric fix is
  confirmed by harness runs but never eyes-on'd through the card itself.

## Needs a decision from Colin

- **(u) residual — ADR-vs-spec on the bounded re-plan loop.** It shipped as
  spec-level with no ADR, mirroring how ADR-0030 treated the repair loop. The
  spec stays `draft` until this is called. Corrective re-plan is tranche 2.
- **`mixed_chart_composition_unsupported` is dead code** since `372a437`
  (2026-06-24) — every numeric+state set routes to `time_series_overlay`, so
  the "mixed" family is unreachable through `_resolve_render_family`. Delete
  the defensive gate, or keep it documented-unreachable?
- **Delta subtraction-order semantics need explicit sign-off.** The 0.2.46 arch
  review asked for a human call rather than an ADR on how a two-input `delta`
  claim fixes its sign: `inputs` must be in the same order as the subtraction,
  and a sign-only disagreement degrades to a caveat
  (`grounding_delta_sign_ambiguous`) rather than withholding. The mechanism
  shipped; the sign-off was never obtained.
- **(G) Reconcile the two invariant lists.** `CLAUDE.md`'s 9 enforced
  invariants and `docs/ARCHITECTURE.md`'s 12 load-bearing decisions are
  separate numbered lists with no cross-reference. Colin's lean: make the 12 an
  explicit superset citing which rows are the enforced 9.
- **(e) Re-scope or retire the stale live-retest checklist.** Written for
  `0.1.23` and now ~24 versions old; the behaviours it lists (fuzzy window
  resolution, daily-statistics rendering with a min/max band, a card-facing
  `no_long_term_statistics` failure, executor-hygiene warnings gone) have
  largely been exercised by later live e2e runs, but no run explicitly closed
  it. Either fold the unverified parts into the e2e prompt set or retire it.

## Future features (not yet ADR'd)

- **(h) Night mode / dark theme.** Scope: chart PNG + card UI, auto-following
  the HA theme (no user toggle). Two coupled surfaces: (1) the Pillow renderer
  bakes a white background at render time, so a dark variant needs a second
  palette **and** the resolved theme plumbed card → `job/start` → render request
  (schema-touching); (2) the Lit card already consumes HA theme CSS vars with
  light *fallbacks* plus a few hardcoded light values (e.g. `#f7f9fb`) to clean
  up, and must detect HA dark/light (`hass.themes.darkMode` /
  `prefers-color-scheme`). Needs a spec and likely an ADR per invariant #8.

- **(l) residual — conversational refinement.** Back-and-forth with the model
  to refine a chart: mechanically the codegen repair loop with human feedback
  instead of sandbox errors (previous code + instruction → revised code). The
  *saved live visualizations* half of the original (l) stub was promoted into
  **ADR-0035** (accepted), which also settled the stub's axes-drift open
  question: slice-1 policy is matplotlib autoscale, refined later — if ever —
  by a deterministic integration-side bounds policy, not by smarter generated
  code.

- **(c) Floorplan heatmap renderer.** Post-MVP. Home Assistant floors and areas
  do not provide room geometry, so this needs explicit user-provided geometry
  plus area/entity mappings. **The word "heatmap" is reserved for this spatial
  renderer** — a temporal calendar heatmap, if ever built, must be its own named
  family (Colin's "ship simple" ruling; see `docs/gotchas.md`).

- **(bb) Correlation-matrix asks degrade to multi-line.** A multi-entity
  "heatmap of correlations" routes through the `time_series` envelope, so the
  (w) family-degrade rule sends it to multi-line series — coherent but a weak
  substitute. Accepted by the coherent-degrade bar; revisit only if
  correlation-matrix asks become common, and then as a named family.

## Parked

- **Packet 6 — the multimodal visual validator** (ADR-0031). Planned direction,
  not yet specced.
- **Anchored-window tranche 2.**
- **(z)/(B) repair-intent retention rule.** Recommended after the (z) fix, but
  the cross-math variance root cause turned out to be an intermittent `KeyError`
  indexing a concatenated DataFrame — the retention rule is harmless but is not
  the fix.
- **Multi-arch worker image builds and HA add-on packaging/ingress** (ADR-0029,
  deferred not boxed out). Also unpinned: `worker/Dockerfile` does not
  digest-pin `python:3.12-slim`.
- **(d) Worker durability follow-ons** — token rotation UI, HA Repairs
  semantics, durable retry/polling. Largely retired by ADR-0032, which deleted
  the machinery. Any revival needs a new ADR.
