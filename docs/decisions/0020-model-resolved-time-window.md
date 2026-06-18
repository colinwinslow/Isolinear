---
id: 0020
title: Model-resolved chart time window
status: accepted
date: 2026-06-18
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - model-provider
  - orchestration
  - vertical-slice
---

# ADR-0020: Model-resolved chart time window

## Context

The first real vertical slice (ADR-0017) charts approved recorder history over
a time window. As shipped in `0.1.21`, that window was chosen by a deterministic
regex (`_history_window_from_prompt`) that matched templated phrases like
"last N hours/days/weeks" and otherwise fell back to 24h. The regex ran at
`job/start`, *before* the model was called, and the model's own emitted
`chart_spec.time_range` was ignored.

This is brittle by construction: fuzzy, real-world phrasings — "during the
night", "last weekend", "since the spring equinox", "while I was on vacation" —
do not match the templates and silently collapse to 24h. Natural-language time
resolution is exactly the kind of judgment the model is suited for and a regex
is not.

Two structural facts make a change feasible: (1) the planner is given only
entity IDs, never the history data points, so history retrieval does not need to
precede planning; and (2) the canonical `chart-spec.schema.json` already allows
an `absolute {type, start, end}` time range — only the Ollama structured-output
schema was narrowed to relative-only.

## Decision

1. **The model resolves the window.** The model returns an **absolute**
   `chart_spec.time_range = {type: "absolute", start, end}` (ISO 8601,
   timezone-aware). The Ollama structured-output schema is widened to require
   the absolute shape; relative output is no longer requested.

2. **The request carries clock context.** The planner request includes `now`
   (ISO 8601, tz-aware) and `time_zone` (from `hass.config.time_zone`) so the
   model can resolve relative and fuzzy phrases against the user's actual clock.

3. **The integration owns deterministic clamp/validate.** Before any history
   read, the model's window passes a deterministic gate (`_resolve_history_window`):
   - parse both endpoints as tz-aware datetimes; normalize to UTC;
   - require `start < end`;
   - clamp `end` to `now` if the model returns a future end;
   - clamp the span to `MAX_HISTORY_WINDOW` (366 days) by moving `start` forward;
   - enforce a positive floor `MIN_HISTORY_WINDOW` (60 s).
   A window that survives clamping is used as-is.

4. **One deterministic fallback: last-24h.** If no planner is configured, or the
   model omits the window, or it is unparseable / inverted / otherwise
   unclampable, the integration uses a fixed `now − 24h .. now` window. **The
   regex keyword parser is removed entirely** — last-24h is the *only*
   deterministic fallback.

5. **History is fetched after planning.** For the first-real-slice path,
   orchestration is reordered so `retrieve_approved_history` runs in the
   snapshot/plan path using the resolved window, instead of at `job/start` with
   a pre-guessed window. The `job/start`, clarification-continuation, and retry
   handlers no longer fetch history for the real path; they stage entity
   selection and a planning snapshot, and the snapshot path resolves the window,
   fetches history, and renders. (The legacy non-real scaffold path keeps its
   start-time retrieval; it has no model and therefore no model-driven window.)

The 366-day ceiling is only useful because windows older than recorder
retention are served from long-term statistics — see ADR-0021. A resolved
window may therefore map to statistics data; the chosen source and resolution
are recorded on each `HistorySeries`.

## Consequences

- Robust to arbitrary phrasing; the model does the NL work, the integration
  keeps the safety boundary. Invariant 5 (deterministic plan validation) is
  preserved, just relocated to the clamp layer.
- `_history_window_from_prompt` and its constants/tests are deleted;
  `_default_history_time_range` becomes a plain last-24h helper used as the
  fallback.
- The real-slice snapshot path grows a history read; the real-slice start path
  loses one. The "fetching_history" progress snapshot relocates accordingly.
- A query whose window predates recorder retention now succeeds for entities
  with long-term statistics, where previously the start-time 24h fetch would
  have failed before planning.
- Some phrases ("while I was on vacation") are not derivable from prompt + now;
  the model will emit a plausible-but-possibly-wrong range. Clamping bounds the
  blast radius (never unbounded, never future, ≤366 days) but cannot guarantee
  semantic correctness. Accepted limitation.
- Timezone/DST handling becomes load-bearing and needs explicit tests.
- Evals stay deterministic by pinning the clamp layer and a `FakePlanner` with
  fixed windows; real-model output is never asserted on.

## Alternatives considered

- *Keep the regex as fallback* — rejected; last-24h is the sole fallback to
  avoid two competing deterministic parsers.
- *Model returns a relative spec the integration re-parses* — rejected; pushes
  NL ambiguity back into deterministic code, defeating the purpose. Absolute
  endpoints keep the ambiguity in the model.
- *Separate window-only model call at job/start* — rejected; adds a second
  round-trip. The window rides in the existing single `plan_chart` call.

## Follow-ups

- BDD/evidence proving a fuzzy prompt resolves to a sane bounded window
  end-to-end via a fake planner.
- Live HACS retest after implementation.
