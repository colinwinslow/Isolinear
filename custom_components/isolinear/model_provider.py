"""Ollama-compatible model-provider planning boundary for Isolinear."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from ._paths import load_schema_document, schema_path
from .const import (
    DOMAIN,
    MODEL_PROVIDER_OLLAMA_COMPATIBLE,
    MODEL_PROVIDER_OPENAI_COMPATIBLE,
    RENDER_PATH_AUTO,
    RENDER_PATH_PILLOW,
)
from .model_provider_key_storage import stored_model_provider_key

_LOGGER = logging.getLogger(__name__)


DATA_MODEL_PROVIDER_PLANNER = "model_provider_planner"
DATA_MODEL_PROVIDER_SETUP = "model_provider_setup"
# ADR-0029 packet 4: a separate, configurable codegen client. It shares the
# Ollama transport with the planner but may point at a different (code-
# specialized) model. When `codegen_model` is unset it defaults to the planner
# model. It is installed only when codegen is opt-in enabled (invariant #6).
DATA_MODEL_PROVIDER_CODEGEN = "model_provider_codegen"
DATA_MODEL_PROVIDER_CODEGEN_SETUP = "model_provider_codegen_setup"

PLANNER_RESULT_SCHEMA_PATH = schema_path("planner-result.schema.json")
# A local gemma planner call observed ~30s for a simple chart; the prior 30s
# cap timed out on anything heavier (mixed/overlay prompts). Codegen for
# complex charts regularly runs 60-90 s; 180 s matches the configurable default
# (ADR-0024 also adds a model entity-selection round-trip). Keep this in sync
# with config_schema.default_options_data()["ollama_timeout_seconds"] — this is
# the fallback used when an entry has no configured value.
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 180
MODEL_PROVIDER_HEALTH_PATH = "/api/tags"
# ADR-0037: the OpenAI-compatible (LiteLLM) provider's health check hits
# GET /models, not the Ollama-native /api/tags. Recorded metadata must reflect
# the actual endpoint checked for the configured provider.
MODEL_PROVIDER_OPENAI_HEALTH_PATH = "/models"

# ADR-0037: reasoning effort requested from the OpenAI-compatible provider on the
# streaming (reasoning) pass. Only sent when a reasoning trace is wanted (an
# `on_reasoning` callback is provided); the value is a hint — models that ignore
# it or emit no reasoning degrade to the ADR-0025 D6 "nothing shown" fallback.
DEFAULT_OPENAI_REASONING_EFFORT = "low"

# ADR-0025 R1: the live reasoning trace surfaced to the card is capped to this
# many characters. The cap bounds snapshot size against a runaway model trace
# (D5) and is mirrored by `progress.reasoning.maxLength` in the snapshot schema.
REASONING_CHAR_CAP = 2000

# ADR-0025 D5: the model thinking trace is unsanitized output. Before it reaches
# the card it gets the same redaction posture as every card-facing field — no
# tokens, endpoints/worker URLs, or local filesystem paths. Approved entity IDs
# and the user's own prompt may remain (already disclosed). These patterns are
# intentionally broad; over-redaction of wait-feedback is harmless.
_REASONING_REDACTIONS: tuple[re.Pattern[str], ...] = (
    # http(s) endpoints / worker URLs (host, port, path).
    re.compile(r"https?://\S+"),
    # Bearer / authorization tokens.
    re.compile(r"(?i)bearer\s+\S+"),
    # Named secret vocabulary, mirroring job_orchestration's
    # FORBIDDEN_WORKER_PROGRESS_TEXT / FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT so
    # the reasoning surface can't drift from the rest of the card-facing fields.
    # Redact the key *and* any attached value (``access_token=...``, ``token: ...``).
    re.compile(
        r"(?i)\b(?:access_token|home_assistant_token|long_lived_access_token|"
        r"worker_token|model_provider_token|ollama_api_key|api[_-]?key)\b"
        r"(?:\s*[:=]\s*\S+)?"
    ),
    # Bare secret-like tokens: OpenAI-style ``sk-...`` keys and JWTs
    # (three dot-separated base64url segments). The model can echo such
    # material verbatim from a prompt; over-redacting wait-feedback is harmless.
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    # Windows filesystem paths (drive-letter rooted).
    re.compile(r"[A-Za-z]:\\[^\s\"']+"),
    # Unix-ish absolute paths with at least two segments (avoid eating prose
    # like "and/or"; require a leading slash and a path separator).
    re.compile(r"(?<!\w)/[\w.-]+(?:/[\w.-]+)+"),
)
_REASONING_REDACTION_PLACEHOLDER = "[redacted]"


def sanitize_reasoning(raw: str) -> str:
    """Redact off-limit material and roll-tail-cap a model thinking trace.

    ADR-0025 D5 (redaction), R1 (2000-char cap), R2 (rolling tail). Returns the
    trailing ``REASONING_CHAR_CAP`` characters of the redacted trace; when
    content was elided from the front a single leading ``…`` marks the cut.
    An empty input (or one that redacts to nothing) returns an empty string and
    the caller omits the field.
    """
    if not raw:
        return ""
    text = raw
    for pattern in _REASONING_REDACTIONS:
        text = pattern.sub(_REASONING_REDACTION_PLACEHOLDER, text)
    if len(text) <= REASONING_CHAR_CAP:
        return text
    # Rolling tail: keep the newest content, mark the elision with an ellipsis
    # that itself counts toward the cap.
    tail = text[-(REASONING_CHAR_CAP - 1):]
    return "…" + tail


# ADR-0029 packet 4: codegen generation/repair prompts. The model writes a
# single fixed-entry-point function; the sandbox enforces safety (ADR-0008), so
# the prompt only needs to communicate the contract, not police it.
# A bounded, evenly-downsampled preview of REAL points shown in the prompt under
# the SAME key the runtime data uses (`points`), so the model both sees the exact
# point dict shape AND has concrete data to anchor its plotting/labeling on — the
# FULL points still arrive at render time. A pure summary (no real points) was
# tried in 0.2.18 and measured unreliable: gemma4:e4b drifted to the chart_spec
# and produced EMPTY plots ~2/3 of the time; a live grounding experiment showed a
# small preview restores 6/6 reliability. 12 sits comfortably above the ~6-point
# floor at a modest, constant token cost. The preview key MUST stay `points`:
# renaming it (the 0.2.18 `sample_points`) let the model bind to a key absent at
# runtime → KeyError / empty plot.
_CODEGEN_PROMPT_PREVIEW_POINTS = 12
# Distinct state values disclosed for binary/categorical series (ADR-0022): the
# state-data analog of numeric value_stats. Capped so a pathologically-varied
# categorical series cannot reinflate the prompt.
_CODEGEN_PROMPT_MAX_DISTINCT_STATES = 50
# The prompt is now bounded (a per-series summary, not the full points), so a
# modest explicit context window is ample and keeps the instructions in-window
# regardless of the model's small default num_ctx (the overflow that made the
# model reply with prose instead of code).
_CODEGEN_NUM_CTX = 8192
# ADR-0034: the user's request text is disclosed to the codegen model (the
# analysis-intent conduit) so it knows whether to compute a derived series /
# answer a question rather than plot the raw inputs. It is a generation-time
# input only — it is passed as an explicit argument to the payload builders and
# never enters the render request that crosses to the worker sandbox. Bounded
# for token discipline (not security — it is the same user text the planner and
# entity-selector prompts already carry); a card prompt is a short sentence.
_CODEGEN_MAX_USER_REQUEST_CHARS = 500


def _bounded_user_request(user_request: str | None) -> str:
    """Trim the user's request to a bounded prompt-safe string (ADR-0034)."""
    if not isinstance(user_request, str):
        return ""
    text = user_request.strip()
    if len(text) <= _CODEGEN_MAX_USER_REQUEST_CHARS:
        return text
    return text[:_CODEGEN_MAX_USER_REQUEST_CHARS].rstrip() + "…"


_CODEGEN_SYSTEM_PROMPT = (
    "You are the Isolinear chart-code generator. Always wrap your entire Python "
    "output in a single code fence: ```python\\n<code>\\n```. No prose, no "
    "explanation, nothing outside the fence."
)
# Repair-intent retention (open-queue (B) investigation, 0.2.31): a candidate
# repair-only instruction to preserve the previous_code's derived series +
# answer_text while fixing a runtime error. NOT SHIPPED — eval-gated with/without
# arms (evals/repair_intent_retention_gate.py) it showed NO separation (3/3
# retained in both arms: on a clean fixable error gemma keeps intent regardless),
# so per the 0.2.22 "failure-driven hints must earn their accept-rate" principle
# it was dropped. The variance basin's real fix was the entity-id-keyed combined
# frame rule below (the live runtime_error was an intermittent KeyError from
# indexing a concat'd frame by entity_id — a fix-rate bug, not intent erosion).
_CODEGEN_PROMPT_RULES = [
    "Define exactly one top-level function: def render_chart(data, output_path):",
    "Implement the supplied chart_spec using matplotlib and the supplied history_series.",
    # The prompt's history_series carries a bounded PREVIEW of points (key
    # 'points', plus point_count / points_truncated) — enough real data to ground
    # the code, not the whole series. At runtime the SAME 'points' key holds every
    # point, so accessors written against the preview work unchanged.
    "In this prompt each data['history_series'][i]['points'] is a bounded PREVIEW "
    "(see point_count and points_truncated); at runtime that same 'points' list "
    "holds EVERY point. Write your code to iterate data['history_series'][i]['points'] "
    "in full — do not hard-code the preview length or assume only a few points.",
    # The 0.2.18 failure mode: with only a summary, the floor model plotted/labeled
    # from the chart_spec (planner-guessed unit, no top-level entity_id) → empty
    # plots, wrong units. history_series is the sole source of truth for data.
    # ADR-0034: raw-line plotting stays the DEFAULT (grounding preserved), with a
    # compute-the-derived-series EXCEPTION driven by user_request — the conduit
    # that makes the model-authored analysis layer actually fire (measured live:
    # baseline 0/12 vs this arm 12/12 on the production codegen path). When
    # user_request is empty the exception is trivially inert → raw-line default.
    # ADR-0036 (0.2.34): cross-series plumbing goes through the in-sandbox helper
    # isolinear_analysis.align() instead of a transcribed resample/keying idiom —
    # the third rung of the idiom-over-prose ladder (prose → literal idiom →
    # callable). Every recent live cross-math failure (0.2.31 entity-id KeyError,
    # the 0.2.32 "nan °F" empty frame, e2e-18 repair exhaustion) died in the
    # transcription of exactly this step. Gated (evals/analysis_helper_gate.py,
    # 4 members × 6 runs × 2 arms): deviation eventual-success 6/6 vs 4/6 with
    # 2 repair-exhaustions (the live e2e-18 failure reproduced), repairs converge
    # in one round instead of cascading through hand-rolled plumbing errors,
    # helper adoption 24/24, no regression on mean/delta/correlation, and the
    # rule text is ~415 chars shorter.
    "By default plot each series in data['history_series'] whose 'kind' is 'numeric' "
    "as a line, iterating that list directly and using each series' own 'label' and "
    "'unit'. EXCEPTION: when user_request asks for a computed analysis — an average "
    "or combination across sensors, a difference ('how much warmer'), a correlation, "
    "a deviation from average, a smoothed/rolling series, or similar — COMPUTE that "
    "derived series from the numeric history_series points with pandas/numpy/scipy and "
    "plot the DERIVED result, labelled for what it is; plot the raw inputs only if they "
    "help answer the request. Each entity's points are sampled IRREGULARLY at "
    "different times (two entities share NO timestamps), so for ANY math across two "
    "or more series (average, difference, correlation, deviation) FIRST call: import "
    "isolinear_analysis; frame = isolinear_analysis.align(data['history_series']) "
    "— it aligns every numeric series onto one shared time grid and returns a "
    "pandas DataFrame whose columns ARE the entity_id strings. Then compute with "
    "one-liners: frame.mean(axis=1) is the cross-sensor average series; "
    "frame['<entity_id_a>'] - frame['<entity_id_b>'] is the difference series; "
    "frame.corr().iloc[0, 1] is the correlation coefficient; "
    "frame.sub(frame.mean(axis=1), axis=0) is the per-sensor deviation from the "
    "mean. Plot with frame.index as the x-axis. NEVER align, resample, join, or "
    "intersect raw series yourself — isolinear_analysis.align is the only "
    "correct way to combine series. Never plot a series whose 'kind' is 'binary_state' or "
    "'categorical_state' as a line (its value is a state string like 'cool', not a "
    "number) — those are state overlays, already provided to you as shaded bands (see "
    "the derived_intervals rule). The chart_spec is intent/metadata only (title, "
    "requested series) — NEVER read the data to plot, the list of series, or the unit "
    "from chart_spec; a chart_spec unit may be wrong. Use "
    "data['history_series'][i]['entity_id'] for identity.",
    # Family degrade (invariant #9; open-queue (w), 0.2.26): the integration
    # owns the chart FAMILY (line / histogram / bar); the model owns the
    # COMPUTATION within it. A heatmap is a family, not a computation, and there
    # is no heatmap family — so codegen must never invent one, or the
    # planner-chosen histogram spec and a "heatmap" user_request collide into a
    # garbage chart (live e2e-15). "heatmap" the word is reserved for a future
    # spatial/floorplan renderer (open-queue (c)); a temporal calendar heatmap,
    # if ever built, becomes its own named family. Degrade to the distribution.
    "Render only these chart families: line charts, histograms, and bar charts. "
    "NEVER draw a 2-D heatmap, matrix, grid, calendar map, or spatial/floorplan "
    "map, and never use seaborn.heatmap, ax.pcolormesh, ax.imshow, or ax.hist2d. "
    "If user_request asks for a 'heatmap' or a '<value> by hour of day and day'-"
    "style matrix of a sensor, do NOT build a 2-D grid — render a histogram of "
    "that sensor's values (its distribution, ax.hist over the numeric points) "
    "instead. user_request may change WHAT you compute (an average, a difference, "
    "a distribution) but NEVER which chart family you draw — the family is fixed by "
    "the data, not by user_request: numeric series get lines/histograms/bars, and a "
    "series that is ENTIRELY binary/categorical state gets a state step track (see "
    "the timeline rule below).",
    # Timeline family (spec timeline-codegen-rendering; invariant #9, ADR-0022): a
    # binary/categorical entity charted on its own is a step track, not a line and
    # not the numeric-overlay axvspan bands. The integration precomputes the state
    # intervals into derived_intervals (same trusted region logic as the overlay
    # bands); the model just draws them as broken_barh lanes. This is the primary
    # signal the model can read from the data (every series is a state series, no
    # numeric line to draw). Without it the model drew near-zero verticals off raw
    # points + a 0.0-minute answer (live e2e-09).
    "If EVERY series in data['history_series'] is a state series (its 'kind' is "
    "'binary_state' or 'categorical_state'), you are drawing a TIMELINE step track "
    "— NOT a line and NOT axvspan background bands. import matplotlib.dates as "
    "mdates. Give each entity ONE fixed horizontal lane: pick a lane_y per entity "
    "(e.g. 0 for the first) and a fixed bar height (e.g. 0.6). FIRST draw a light "
    "grey 'off' baseline track for that lane spanning the WHOLE window, so a "
    "mostly-off entity reads as present-but-off rather than a few floating marks: "
    "win0 = mdates.date2num(pandas.to_datetime(min ts_epoch_ms across the series, "
    "unit='ms')); win1 = mdates.date2num(pandas.to_datetime(max ts_epoch_ms, "
    "unit='ms')); ax.broken_barh([(win0, win1 - win0)], (lane_y, 0.6), "
    "facecolors='#e8e8e8'). THEN draw the on/active intervals as colored bars ON "
    "THE SAME lane (same lane_y, same height): for each band in "
    "data['derived_intervals'] for that entity, start = mdates.date2num("
    "pandas.to_datetime(band['start_ms'], unit='ms')); width = max(mdates.date2num("
    "pandas.to_datetime(band['end_ms'], unit='ms')) - start, min_w) where min_w = "
    "(win1 - win0) / 100 (about 1% of the visible window, so even a brief opening "
    "stays visible on a multi-hour axis — a few real minutes would otherwise be an "
    "invisible sliver); ax.broken_barh([(start, width)], (lane_y, 0.6), "
    "facecolors=band['color']). Call ax.xaxis_date() so the x-axis reads as time. "
    "Set exactly ONE y-tick per entity at its lane_y, labelled with the entity's "
    "name — NOT 'on'/'off' (state is shown by the colored bars over the grey "
    "off-track, not by y position). Do NOT derive intervals from raw points and do "
    "NOT plot the state as a line. If derived_intervals is empty, still draw the "
    "grey off-track lane across the window so it reads present-but-off.",
    # Timeline duration answer (spec C3): the e2e-09 "0.0 minutes" came from the
    # model deriving intervals from raw points; sum the PRECOMPUTED intervals
    # instead. Grounded via a state_duration claim (C4). Integration-only — no new
    # request field, so no worker rebuild.
    "If the user asks HOW LONG or WHEN a state entity was on/open (a timeline "
    "duration question), compute the total on-time by summing "
    "(band['end_ms'] - band['start_ms']) over the bands in data['derived_intervals'] "
    "for that entity — these intervals are precomputed and correct, so NEVER count "
    "raw points or recompute intervals. Present it in answer_text in minutes/hours "
    "(converted for readability) and emit a claim with metric 'state_duration', "
    "inputs=[<entity_id>], value=<the total on-time in MILLISECONDS, i.e. the raw "
    "sum you computed>, and params={'active': [<the on-state strings, e.g. "
    "'on','open'>]}. The claim value is milliseconds (machine-checked); the "
    "answer_text prose may use minutes/hours. A duration is a plain descriptive "
    "value, so emit no verdict and no rule.",
    # State overlays (ADR-0033): the integration precomputes the shaded intervals
    # (e.g. when the AC was cooling/heating, from hvac_action) — the floor model
    # cannot reliably derive them, so it must NOT try; it just draws the given bands.
    "data['derived_intervals'] is a list of precomputed shaded background bands "
    "marking state overlays (e.g. when the AC was cooling). Each band is "
    "{'start_ms': epoch_ms int, 'end_ms': epoch_ms int, 'color': hex string, "
    "'label': state name}. Draw EACH as a background span behind the lines: "
    "ax.axvspan(pandas.to_datetime(band['start_ms'], unit='ms'), "
    "pandas.to_datetime(band['end_ms'], unit='ms'), color=band['color'], alpha=0.3, "
    "zorder=0). Do NOT compute these intervals yourself and do NOT plot the overlay "
    "as a line. If derived_intervals is empty, draw no bands. Add one legend entry "
    "per distinct band label/color (e.g. a Patch), not per band.",
    # ADR-0031 D9: the model is handed epoch integers, never raw HA ISO strings —
    # the projection strips 'ts', so 'ts_epoch_ms' is the only timestamp key.
    "Read the series points from data['history_series']; each point has 'ts_epoch_ms' "
    "(Unix epoch MILLISECONDS, an integer) and 'value'. Use ts_epoch_ms directly for "
    "the x-axis; if you need datetimes, pandas.to_datetime(<ts_epoch_ms values>, "
    "unit='ms'). Never parse a raw timestamp string.",
    # Grounding: the real HA unit is in the series record. Use it — do not guess
    # or convert. Reading it from the data (a str variable) also keeps any
    # non-ASCII unit symbol (e.g. '°F') out of a bare code literal.
    "Each series in data['history_series'] carries a 'unit' string (e.g. '°F'). Label "
    "the axis and any answer_text using that exact unit value read from the data — "
    "e.g. unit = data['history_series'][0].get('unit') or ''; "
    "ax.set_ylabel(f'Temperature ({unit})'). Never guess the unit or convert between "
    "units; if 'unit' is missing or empty, omit the unit rather than inventing one.",
    "Save the figure to output_path as PNG (fig.savefig(output_path, format='png', "
    "bbox_inches='tight')).",
    # Legibility: the PNG is displayed on a phone-width card, so it is scaled down.
    # Render large enough that text stays readable after that downscale.
    "Render for a phone-width card: create the figure at about 8x4.5 inches with "
    "dpi=110 (fig, ax = plt.subplots(figsize=(8, 4.5), dpi=110)); use a title around "
    "fontsize 15, axis labels around 13, and tick labels around 11 so text stays "
    "legible when the image is scaled down.",
    # ADR-0031 D6: the analysis libraries the sandbox allowlists. Kept in sync
    # with the worker sandbox policy (worker/isolinear_worker/codegen_sandbox.py).
    "You may import matplotlib (and matplotlib.pyplot), pandas, numpy, scipy "
    "(scipy.stats / scipy.signal / scipy.optimize), and seaborn. Import nothing "
    "else: no os, sys, socket, requests, subprocess, open() on arbitrary paths, "
    "or network access.",
    "Do not read environment variables, secrets, tokens, or files other than writing "
    "the figure to output_path.",
    "Return a small metadata dict (title, series_plotted, warnings, legend) from render_chart.",
    # ADR-0027 D1 card-level legend on the codegen path (spec
    # card-level-legend-codegen). The card renders a rich legend OUTSIDE the plot
    # from a self-reported color manifest — the same proven self-report pattern as
    # series_plotted/answer_text (metadata about code you just wrote). The model
    # owns matplotlib colors here (no integration palette), so the swatch can only
    # match the line if you assign an explicit HEX color and report that same hex.
    # kind carries Colin's convention: real sensors solid, computed series dashed;
    # a computed series is a LINE, not a shaded band, so it is 'computed', never
    # 'overlay'. Legend is cosmetic — a missing/partial one never fails the render.
    "Assign each plotted line an explicit lower-case hex color and pass it to "
    "ax.plot(..., color='#rrggbb'). Draw raw sensor series as SOLID lines and any "
    "series you COMPUTED (a cross-sensor average, difference, deviation, or "
    "rolling mean) as a DASHED line (linestyle='--'), so the two read differently. "
    "Do NOT call ax.legend() — the card draws the legend itself from the manifest "
    "below, so an in-image legend is redundant. Return a 'legend' list in the "
    "metadata dict, one entry per line/band you drew in draw order, each a dict "
    "with: 'label' (the descriptive label), 'entity_id' (the series' entity_id "
    "from history_series; for a computed series use its primary input entity_id, "
    "or '' if none applies), 'color' (the EXACT hex you passed to ax.plot, "
    "lower-case '#rrggbb'), and 'kind' — 'series' for a raw sensor line, 'computed' "
    "for a series you computed, 'overlay' for a shaded state band. Omit the legend "
    "or return [] if you drew a single plain series.",
    # ADR-0031 tranche 1: grounded natural-language answer. The number and any
    # verdict MUST be computed inside render_chart and formatted into the string —
    # never asserted at generation time (an honest number must not ride a
    # contradicting verdict). ADR-0034: keyed on user_request (the conduit), which
    # the model now sees — previously this referenced a "prompt" the codegen model
    # was never shown, so the answer channel never fired live.
    "If user_request asks a question (e.g. 'are they correlated?', 'how much…?', "
    "'what was the average…?'), also return an 'answer_text' string in the metadata "
    "dict answering it in one plain sentence.",
    "Compute the answer_text from variables you calculate over the data and format "
    "them in with an f-string — e.g. corr = frame.corr().iloc[0, 1]; "
    "answer_text = f'The correlation coefficient is {corr:.2f}.' Never write the "
    "number or a Yes/No verdict as a literal; derive the verdict too "
    "(verdict = 'Yes' if abs(corr) > 0.3 else 'Not really').",
    # (ff): two coupled correlation failures. (1) EMISSION — a correlation is a
    # single SCALAR with nothing new to plot, so the floor model can plot the two
    # raw sensors and stop; this rule makes emitting the coefficient mandatory
    # (eval-gated evals/correlation_answer_gate.py). (2) VERDICT-BASIS (the live
    # e2e-13/e2e-20 "no answer" — reproduced 6/6 on REAL kitchen/basement data,
    # scripts/repro_correlation_emission_realdata.py): the model DID emit a correct
    # coefficient but grounding WITHHELD it (grounding_verdict_contradicted) because
    # the rule's 'basis' didn't match the abs(corr) verdict — see the basis:'abs'
    # rule below. A withheld answer is suppressed on the card, so it looked like a
    # plain plot-only miss. Fixing the basis is what actually serves negative
    # correlations.
    "IMPORTANT for correlation questions ('are they correlated?', 'do they move "
    "together?', 'how are they related?'): the correlation coefficient is a single "
    "number, NOT a plotted series — so drawing the two raw sensor lines is NOT the "
    "analysis and is NOT enough on its own. You MUST also compute the coefficient "
    "(frame = isolinear_analysis.align(data['history_series']); "
    "corr = frame.corr().iloc[0, 1]) and report it in answer_text. Never plot the "
    "inputs and return without an answer_text when user_request asks whether or how "
    "two sensors are correlated.",
    # 2026-07-20, live-driven (e2e-08): a two-sensor COMPARISON prompt is the
    # same emission shape as correlation — the interesting quantity (how far
    # apart the sensors run) is a scalar with nothing new to plot, so the model
    # draws both lines and either stops or answers qualitatively ("generally
    # higher"), emitting no claim at all. A claimless answer grounds as
    # `outcome: pass` with answer_verification ABSENT: it is served with no
    # caveat and was never checked against the data — worse than a caveat,
    # because a wrong number reads as an unqualified fact (a live run answered
    # "4.0 %" where the aligned truth was 4.63). The subtraction ORDER and the
    # average-over-the-window reading are pinned here so the claim and the
    # integration's independent reference are the same quantity by contract —
    # the tactic the 0.2.44 basis:'abs' fix used for correlation.
    "IMPORTANT for two-sensor comparison questions ('compare A and B', 'how "
    "does A compare to B', 'which is warmer/more humid', 'how much higher'): "
    "the size of the gap is a single number, NOT a plotted series — so drawing "
    "both sensor lines is NOT the analysis and is NOT enough on its own. You "
    "MUST also compute the AVERAGE DIFFERENCE over the window from the aligned "
    "frame (frame = isolinear_analysis.align(data['history_series']); "
    "diff = (frame[a] - frame[b]).mean(), where a is the sensor named FIRST in "
    "the question) and state that number in answer_text. Emit the claim "
    "{'metric': 'delta', 'inputs': [a, b], 'value': diff} with 'inputs' in the "
    "SAME order you subtracted — the integration recomputes (frame[inputs[0]] - "
    "frame[inputs[1]]).mean() and a swapped order flips the sign and rejects a "
    "correct answer. Report the average over the whole window, not the "
    "difference at a single instant.",
    # Paired with the above: when a smoothing answer DOES state a number, the
    # rolling_mean recompute needs `window_ms` (a registry-required param) or it
    # returns no reference and the value can never be verified. The chart is the
    # real deliverable for a smoothing prompt, so this does NOT force a number —
    # it only makes a stated one checkable.
    #
    # Emission fidelity (2026-07-23, live-reproduced 4/4 withheld): a cross-sensor
    # "the average of X and Y, smoothed with a rolling average" prompt made gemma
    # report `mean(rolling(mean(axis=1)))` under a {'metric':'mean'} claim. The
    # mean OF a rolling average is a window-dependent quantity (with a window near
    # the query span it drifts ~0.11 °F from the plain mean — far past the 0.05
    # tolerance), so grounding recomputed the plain cross-sensor mean and WITHHELD
    # a correct-looking answer. Smoothing is a CHART transform; the stated average
    # must be the plain window mean so the {'metric':'mean'} claim verifies. Same
    # family as the 0.2.44 correlation basis fix — pin the claim's quantity to what
    # grounding recomputes, by contract.
    "If your answer_text states a numeric rolling/smoothed average, include the "
    "smoothing window in the claim as 'params': {'window_ms': <the window length "
    "in milliseconds you actually used>}; without it the value cannot be "
    "verified. A smoothing request is satisfied by the chart itself — do not "
    "invent a summary number if the question only asked to see the data smoothed. "
    "When the request asks for BOTH an average and smoothing (e.g. 'the average of "
    "the kitchen and basement temperatures smoothed with a rolling average'), "
    "apply the smoothing ONLY to the plotted line and compute the stated average "
    "from the RAW aligned frame (frame.mean(axis=1).mean() across the sensors), "
    "NEVER from the rolling/smoothed series — the mean of a rolling average is a "
    "different, window-dependent quantity that the grounding check recomputes as "
    "the plain mean and will reject, withholding your answer.",
    # ADR-0031 D8a: claims ledger for the integration-side grounding check.
    # The model emits a machine-readable recipe so the integration can independently
    # recompute the stated value and confirm the verdict follows the declared rule.
    # Band labels must not be substrings of one another (longest-match safety).
    # The ledger is used ONLY for verification; it never appears to the user.
    "When answer_text includes a qualitative verdict (yes/no/comparison), also "
    "return a 'claims' list in the metadata dict. Each claim is a dict with: "
    "'metric' (e.g. 'pearson_r', 'mean', 'hours_above', 'delta'), "
    "'inputs' (list of entity_ids from history_series), "
    "'value' (the SAME numeric variable formatted into the sentence, recorded as "
    "a raw JSON number — 'value': corr, NEVER a pre-formatted string like "
    "f'{corr:.2f}' or '3.0°F'; units belong in the sentence, not the claim), "
    "'verdict' (the same verdict variable formatted into the sentence), "
    "'rule' ({\"bands\": [[threshold_or_null, label], ...], \"basis\": \"value\" or "
    "\"abs\"}; bands in descending threshold order; last entry has null threshold as "
    "catch-all; labels must not be substrings of one another). CRITICAL: 'basis' MUST "
    "match how you derived the verdict — if the verdict comes from a MAGNITUDE "
    "(e.g. correlation strength: verdict from abs(corr) > 0.3) use 'basis': 'abs', "
    "otherwise 'basis': 'value'. A mismatch makes the integration re-derive a "
    "different verdict from your rule and REJECT a correct answer (a negative "
    "correlation like -0.40 has abs 0.40 > 0.3 = 'Yes', but under 'value' the rule "
    "reads -0.40 < 0.3 = 'Not really' → contradiction). Optionally add "
    "'window' ({\"start\": epoch_ms, \"end\": epoch_ms}) and 'params' (flat dict). "
    "Example (correlation — abs basis, since the verdict used abs(corr)): claims = "
    "[{'metric': 'pearson_r', 'inputs': ['sensor.a', 'sensor.b'], "
    "'value': corr, 'verdict': verdict, "
    "'rule': {'bands': [[0.3, 'Yes'], [None, 'Not really']], 'basis': 'abs'}}].",
    # (cc), 0.2.40: verdict/rule ONLY for band judgments. The grounding check's
    # step-5 verdict containment (answer_grounding.py) requires the claimed verdict
    # to appear verbatim as a band label in answer_text; a plain descriptive mean
    # ("the average was 72.9 °F") has no Yes/No label, so a spurious verdict+rule
    # fails containment (grounding_verdict_ambiguous) and burns the whole repair
    # budget re-deriving the same correct number. A value-only claim skips step 5
    # entirely and is still value-verified (step 4 recompute). Eval-gated
    # evals/verdict_omission_gate.py.
    "Attach 'verdict' and 'rule' to a claim ONLY when user_request asks a Yes/No "
    "or categorical judgment (e.g. 'are they correlated?', 'was it above 70?', "
    "'is it high or low?'). For a plain descriptive value answer ('what was the "
    "average / delta / total…?'), emit the claim with 'metric', 'inputs' and "
    "'value' ONLY and OMIT 'verdict' and 'rule' — a descriptive sentence has no "
    "Yes/No verdict to contain, so forcing one makes the grounding check reject a "
    "correct answer.",
    # Spec §1 anchored window (event-scoped answers, e.g. "after the AC started
    # cooling"): the claim window may carry an anchor record instead of absolute
    # bounds; the integration re-detects the transition to verify the same event.
    "When the analysis is scoped to a state-change event (e.g. 'after the AC "
    "started cooling'), the claim 'window' may instead be an ANCHORED window: "
    "{\"anchor\": {\"entity\": <the binary/categorical entity_id>, \"to\": <state "
    "transitioned INTO, exact string>, \"from\": <prior state, optional>, "
    "\"occurrence\": <1-based index among matching transitions; negative counts "
    "from the end, e.g. -1 = most recent>, \"search\": {\"start\": epoch_ms, "
    "\"end\": epoch_ms}, \"resolved_at\": <the epoch_ms timestamp of the "
    "transition your code actually found in the data>}, \"direction\": \"after\" "
    "or \"before\", \"duration_ms\": <window length>}. resolved_at must be the "
    "COMPUTED transition timestamp (a variable), never a guess.",
    # RETIRED 2026-07-06 (open-queue (o), 0.2.22): the bare-non-ASCII rule
    # (0.2.13, "never use ° / % as a bare Python token") was failure-driven and
    # is now doubly redundant — the unit-grounding rule above makes the model
    # read the unit from data['history_series'][i]['unit'] (a str variable), so
    # the ° symbol never lands as a bare code literal, and the worker's
    # source_line on every violation (0.2.14) recovers the class if it ever
    # recurs. Eval-gated for retirement: evals/codegen_rule_gate.py ran the
    # production codegen path with °F/% units against live gemma4:e4b, with vs
    # without this rule — 36 runs, ZERO bare-non-ASCII incidents in either arm
    # (both 18/18 accepted). The rule prevented nothing; small floor models
    # degrade on long rule lists, so it is dropped. Contract rules stay in the
    # prompt; failure-driven style hints must earn their accept-rate.
    "Return only the code — no commentary, no example invocation.",
]


# Repair-prompt rule pruning (2026-08-07). Measured with the real tokenizer
# (scripts/measure_codegen_prompt.py, LIVE_TOKENS=1) against gemma4:e4b: the
# GENERATION prompt fits _CODEGEN_NUM_CTX (58-79% across the e2e failure cases)
# but every REPAIR prompt hit prompt_eval_count == 8192 exactly — truncated.
# Ollama drops LEADING tokens on overflow, i.e. the system prompt and these
# rules, so the repair loop evicted the very contract it was enforcing and the
# model fell back to generic matplotlib boilerplate (np.random.seed(42), mock
# arrays — the stable 7-prompt failure signature of the 2026-07-31 e2e runs;
# repairs never recovered). The full rules list is ~45% of the window and was
# re-sent on every attempt alongside previous_code (~24%).
#
# The fix: a repair already knows what class of failure it is fixing, so it gets
# the contract-critical core plus only the rule families relevant to that class:
#   static (unsafe_code / syntax_error)  -> core only (the violations name the
#       broken contract lines; analysis/emission rules are dead weight)
#   runtime (traceback failures)         -> core + analysis plumbing (+ the
#       precomputed-bands rules when the request carries derived_intervals)
#   grounding_* (synthetic errors from the answer-grounding check) -> core +
#       analysis + the emission/claims block (the failure IS about claims)
# GENERATION is untouched — it fits, and it is where the full contract must be
# in view. Selection is by distinctive marker substring against the LIVE module
# list (not indices), so eval arms that monkeypatch _CODEGEN_PROMPT_RULES flow
# through unchanged; if no marker matches (a fully replaced list), fail open to
# the full list rather than silently repairing rule-less.
_REPAIR_RULE_MARKERS_CORE = (
    "Define exactly one top-level function",
    "bounded PREVIEW",
    "Never parse a raw timestamp string",
    "Never guess the unit",
    "fig.savefig(output_path",
    "Import nothing",
    "Do not read environment variables",
    "Return a small metadata dict",
    "no commentary, no example invocation",
)
_REPAIR_RULE_MARKERS_ANALYSIS = (
    "isolinear_analysis.align is the only",
    "Render only these chart families",
)
_REPAIR_RULE_MARKERS_BANDS = (
    "TIMELINE step track",
    "HOW LONG or WHEN",
    "precomputed shaded background bands",
)
_REPAIR_RULE_MARKERS_EMISSION = (
    "also return an 'answer_text' string",
    "Compute the answer_text from variables",
    "IMPORTANT for correlation questions",
    "IMPORTANT for two-sensor comparison",
    "If your answer_text states a numeric rolling",
    "return a 'claims' list",
    "OMIT 'verdict' and 'rule'",
    "ANCHORED window",
)
_STATIC_SANDBOX_ERROR_CODES = ("unsafe_code", "syntax_error")


def _repair_prompt_rules(
    sandbox_error_view: Mapping[str, Any], request: Mapping[str, Any]
) -> list[str]:
    """Select the subset of _CODEGEN_PROMPT_RULES relevant to this repair class."""
    code = sandbox_error_view.get("code")
    code = code if isinstance(code, str) else ""
    markers = list(_REPAIR_RULE_MARKERS_CORE)
    if code not in _STATIC_SANDBOX_ERROR_CODES:
        markers.extend(_REPAIR_RULE_MARKERS_ANALYSIS)
        if request.get("derived_intervals"):
            markers.extend(_REPAIR_RULE_MARKERS_BANDS)
    if code.startswith("grounding"):
        markers.extend(_REPAIR_RULE_MARKERS_EMISSION)
    selected = [
        rule
        for rule in _CODEGEN_PROMPT_RULES
        if any(marker in rule for marker in markers)
    ]
    # Fail open: a replaced/foreign rules list that matches no marker means we
    # cannot tell contract from style — send everything rather than nothing.
    return selected if selected else list(_CODEGEN_PROMPT_RULES)


def _codegen_request_view(request: dict[str, Any]) -> dict[str, Any]:
    """Project only the model-relevant, non-secret fields into the codegen prompt.

    Data boundary (ADR-0029, invariants #1/#3): only the already-validated
    ChartSpec and the normalized, allowlist-checked render data are disclosed.
    No request_id, transport metadata, tokens, endpoints, or secrets cross into
    the prompt.
    """
    if not isinstance(request, Mapping):
        return {"chart_spec": {}, "history_series": []}
    return {
        "chart_spec": deepcopy(request.get("chart_spec") or {}),
        "history_series": _history_series_prompt_view(request.get("history_series") or []),
        "derived_intervals": deepcopy(request.get("derived_intervals") or []),
        "output": deepcopy(request.get("output") or {}),
    }


def _downsample_preview(points: list[Any], n: int) -> list[dict[str, Any]]:
    """Return up to ``n`` real points spread evenly across ``points``.

    Keeps the first and last point (so the timestamp span is visible) and evenly
    samples in between. Non-mapping entries are skipped. A constant-size preview
    keeps the prompt bounded regardless of the true point count.
    """
    mappings = [p for p in points if isinstance(p, Mapping)]
    if n <= 0 or not mappings:
        return []
    if len(mappings) <= n:
        return mappings
    step = (len(mappings) - 1) / (n - 1) if n > 1 else 1
    indices = sorted({round(i * step) for i in range(n)} | {0, len(mappings) - 1})
    return [mappings[i] for i in indices if i < len(mappings)]


def _history_series_prompt_view(history_series: Any) -> list[dict[str, Any]]:
    """Project a compact per-series view for the codegen prompt.

    The COMPLETE point list is delivered to ``render_chart(data, output_path)``
    at RUNTIME in the sandbox (``codegen_sandbox`` passes the full
    ``history_series`` as ``data``), so the code iterates every point when it
    executes. Placing ALL recorder points in the PROMPT is harmful: a real window
    is thousands of points, which overflows the model's context, evicts the
    system prompt/rules, and makes the model emit a prose description instead of
    code (observed live as ``syntax_error@L1`` plus the ``missing_fixed_entry_point``
    / leading-zero partial-truncation variants).

    But a pure summary is the opposite failure: with no concrete data to anchor
    on, the small floor model (gemma4:e4b) drifts to plotting/labeling off the
    ``chart_spec`` — which carries a planner-guessed unit and no top-level
    ``entity_id`` — and produces EMPTY plots with wrong units (measured ~2/3 of
    the time). So the prompt carries the shape AND a bounded, evenly-downsampled
    PREVIEW of the real points under the SAME key the runtime uses (``points``):
    enough concrete data to ground the code, constant in size, and keyed so the
    model's accessors work against the full runtime data. Raw ISO ``ts`` is
    dropped from the preview (ADR-0031 D9): the model only ever sees integer
    ``ts_epoch_ms``. ``point_count`` and ``points_truncated`` tell the model the
    preview is not the whole series.
    """
    if not isinstance(history_series, list):
        return []
    summaries: list[dict[str, Any]] = []
    for series in history_series:
        if not isinstance(series, Mapping):
            continue
        points = series.get("points")
        points = points if isinstance(points, list) else []
        # Carry every series-level field (entity_id, kind, unit, label, and any
        # overlay metadata) but replace the bulky point list with a summary.
        summary = {key: deepcopy(value) for key, value in series.items() if key != "points"}
        summary["point_count"] = len(points)
        preview = _downsample_preview(points, _CODEGEN_PROMPT_PREVIEW_POINTS)
        # Same key the RUNTIME data uses (`points`) so the model writes accessors
        # that work at render time; raw ISO `ts` stripped (D9 — epoch-ms only).
        summary["points"] = [
            {key: value for key, value in point.items() if key != "ts"}
            for point in preview
        ]
        summary["points_truncated"] = len(preview) < len(points)
        epoch_values = [
            point["ts_epoch_ms"]
            for point in points
            if isinstance(point, Mapping)
            and isinstance(point.get("ts_epoch_ms"), int)
            and not isinstance(point.get("ts_epoch_ms"), bool)
        ]
        if epoch_values:
            summary["ts_epoch_ms_range"] = {"first": epoch_values[0], "last": epoch_values[-1]}
        numeric_values = [
            point["value"]
            for point in points
            if isinstance(point, Mapping)
            and isinstance(point.get("value"), (int, float))
            and not isinstance(point.get("value"), bool)
        ]
        if numeric_values:
            summary["value_stats"] = {
                "min": min(numeric_values),
                "max": max(numeric_values),
                "mean": round(sum(numeric_values) / len(numeric_values), 4),
            }
        # Binary/categorical series (ADR-0022): disclose the distinct states the
        # code must handle (colour/branch on), since a numeric value_stats is
        # meaningless and the points preview alone may not surface every state.
        distinct_states: list[Any] = []
        for point in points:
            if not isinstance(point, Mapping):
                continue
            state = point.get("raw_state")
            if state is None or state in distinct_states:
                continue
            distinct_states.append(state)
            if len(distinct_states) >= _CODEGEN_PROMPT_MAX_DISTINCT_STATES:
                break
        if distinct_states:
            summary["distinct_states"] = distinct_states
        summaries.append(summary)
    return summaries


def _sandbox_error_view(sandbox_error: Any) -> dict[str, Any]:
    """Project the sandbox error into a repair-prompt-safe view.

    Carries ``code``, ``message``, the runtime ``traceback`` (runtime failures),
    AND the static-check ``violations`` (``unsafe_code`` failures). The
    violations are essential: an ``unsafe_code`` failure has NO traceback — its
    specifics (the exact disallowed import/attribute/call and line number) live
    only in ``details.violations``. Without them the model repairs blind and can
    never clear the static gate, so a single systematically-disallowed construct
    exhausts the whole repair budget and falls back to Pillow every time.
    """
    if not isinstance(sandbox_error, Mapping):
        return {"code": None, "message": str(sandbox_error), "traceback": None}
    details = sandbox_error.get("details")
    traceback = details.get("traceback") if isinstance(details, Mapping) else None
    violations = details.get("violations") if isinstance(details, Mapping) else None
    view: dict[str, Any] = {
        "code": sandbox_error.get("code"),
        "message": sandbox_error.get("message"),
        "traceback": traceback,
    }
    if violations:
        view["violations"] = deepcopy(violations)
    return view


def _build_planner_client(
    config_data: Mapping[str, Any],
    options_data: Mapping[str, Any],
    *,
    api_key: str | None = None,
) -> Any:
    """Construct the model-provider client for the configured provider type.

    ADR-0037: ``openai_compatible`` (a LiteLLM proxy) posts OpenAI-shaped
    requests; the optional bearer key comes from the write-only model-provider
    key store (``api_key=None`` while auth is disabled).
    ``ollama_compatible`` keeps the native client. Both share the timeout option.
    """
    raw_timeout = options_data.get("ollama_timeout_seconds", DEFAULT_OLLAMA_TIMEOUT_SECONDS)
    timeout = int(raw_timeout) if isinstance(raw_timeout, (int, float)) else DEFAULT_OLLAMA_TIMEOUT_SECONDS
    if config_data.get("model_provider_type") == MODEL_PROVIDER_OPENAI_COMPATIBLE:
        return OpenAICompatiblePlannerClient(
            endpoint_url=config_data["model_endpoint_url"],
            planner_model=config_data["planner_model"],
            api_key=api_key,
            timeout_seconds=timeout,
        )
    return OllamaCompatiblePlannerClient(
        endpoint_url=config_data["model_endpoint_url"],
        planner_model=config_data["planner_model"],
        timeout_seconds=timeout,
    )


def setup_model_provider_codegen(hass: Any, entry: Any) -> dict[str, Any]:
    """Install a codegen client unless render_path is explicitly "pillow".

    ADR-0030: codegen is the PRIMARY render path (invariant #6) — with the
    default ``render_path: "auto"`` the client is installed whenever a planner
    is configured; ``"pillow"`` explicitly keeps the trusted renderer. The
    codegen client shares the Ollama transport with the planner but uses the
    configured ``codegen_model`` when set, defaulting to the planner model when
    unset. Config-entry data may be a ``mappingproxy`` (the recurring repo
    gotcha); ``_has_planner_config`` accepts any ``Mapping`` and options
    are read the same tolerant way.
    """
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    config_data = getattr(entry, "data", {}) or {}
    options_data = getattr(entry, "options", {}) or {}
    setup = _codegen_setup_disabled(entry_id, "model_provider_codegen_disabled")

    if configured_render_path(options_data) != RENDER_PATH_PILLOW and _has_planner_config(config_data):
        codegen_model = _configured_codegen_model(config_data)
        api_key = stored_model_provider_key(hass, entry_id)
        client = _build_planner_client(config_data, options_data, api_key=api_key)
        entry_data[DATA_MODEL_PROVIDER_CODEGEN] = client
        setup = {
            "accepted": True,
            "code": "model_provider_codegen_configured",
            "entry_id": entry_id,
            "config_entry_scoped": True,
            "enabled": True,
            "codegen_model": codegen_model,
            "codegen_model_defaulted_to_planner": _configured_codegen_model_raw(config_data) is None,
            "provider": client._codegen_provider_metadata(codegen_model),
            "orchestration": model_provider_setup_side_effects(),
        }
    else:
        entry_data.pop(DATA_MODEL_PROVIDER_CODEGEN, None)

    entry_data[DATA_MODEL_PROVIDER_CODEGEN_SETUP] = setup
    return setup


def get_model_provider_codegen(hass: Any, entry_id: str) -> Any | None:
    """Return the configured codegen client for one config entry, if any."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    client = entry_data.get(DATA_MODEL_PROVIDER_CODEGEN) if isinstance(entry_data, dict) else None
    return client if client is not None else None


def configured_render_path(options_data: Any) -> str:
    """Return the configured render path: "auto" (default) or "pillow" (ADR-0030)."""
    if isinstance(options_data, Mapping) and options_data.get("render_path") == RENDER_PATH_PILLOW:
        return RENDER_PATH_PILLOW
    return RENDER_PATH_AUTO


def configured_codegen_model(config_data: Any, *, planner_model: str | None = None) -> str | None:
    """Return the effective codegen model: ``codegen_model`` or the planner model."""
    explicit = _configured_codegen_model_raw(config_data)
    if explicit is not None:
        return explicit
    if planner_model is not None:
        return planner_model
    return _configured_planner_model(config_data)


def _configured_codegen_model(config_data: Any) -> str | None:
    return configured_codegen_model(config_data)


def _configured_codegen_model_raw(config_data: Any) -> str | None:
    if not isinstance(config_data, Mapping):
        return None
    value = config_data.get("codegen_model")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _configured_planner_model(config_data: Any) -> str | None:
    if not isinstance(config_data, Mapping):
        return None
    value = config_data.get("planner_model")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _codegen_setup_disabled(entry_id: str, code: str) -> dict[str, Any]:
    return {
        "accepted": True,
        "code": code,
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": False,
        "codegen_model": None,
        "provider": None,
        "orchestration": model_provider_setup_side_effects(),
    }


def setup_model_provider_planner(hass: Any, entry: Any) -> dict[str, Any]:
    """Install an Ollama-compatible planner client when config-entry data exists."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    config_data = getattr(entry, "data", {}) or {}
    options_data = getattr(entry, "options", {}) or {}
    setup = _setup_disabled(entry_id, "model_provider_config_missing")

    if _has_planner_config(config_data):
        api_key = stored_model_provider_key(hass, entry_id)
        client = _build_planner_client(config_data, options_data, api_key=api_key)
        entry_data[DATA_MODEL_PROVIDER_PLANNER] = client
        setup = {
            "accepted": True,
            "code": "model_provider_planner_configured",
            "entry_id": entry_id,
            "config_entry_scoped": True,
            "enabled": True,
            "provider": client.provider_metadata(),
            "orchestration": model_provider_setup_side_effects(),
        }

    entry_data[DATA_MODEL_PROVIDER_SETUP] = setup
    return setup


def get_model_provider_planner(hass: Any, entry_id: str) -> Any | None:
    """Return the configured planner client for one config entry, if any."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    planner = entry_data.get(DATA_MODEL_PROVIDER_PLANNER) if isinstance(entry_data, dict) else None
    return planner if planner is not None else None


# Render families the integration may request from the planner.
# ADR-0022: the integration deterministically picks the family from each
# resolved entity's series kind.  ADR-0023 extends this: the envelope can
# contain multiple families so the model selects intent within the set.
PLANNER_RENDER_FAMILIES = {
    "time_series": {"chart_type": "time_series", "render_as": "line"},
    "timeline": {"chart_type": "timeline", "render_as": "step"},
    "histogram": {"chart_type": "histogram", "render_as": "histogram"},
    "aggregate_bar": {"chart_type": "bar", "render_as": "bar"},
}


def load_planner_result_schema(
    family: str = "time_series",
    *,
    envelope: list[str] | None = None,
    entity_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Load the PlannerResult JSON Schema for Ollama structured output.

    ``family`` is the default/fallback render family (ADR-0022).  ``envelope``
    is the full ADR-0023 capability list; when it contains more than one family
    the ``chart_type`` enum is widened to all members so the model can choose
    intent within the set.  When ``envelope`` has exactly one member (or is
    omitted) the schema is identical to the single-family ADR-0022 form.

    ``entity_ids`` pins ``source.entity_id`` to an enum of exactly the
    disclosed IDs so constrained decoding cannot emit an off-allowlist entity
    (invariant #1).  Without it the field stays a free string.
    """
    effective_envelope = [f for f in (envelope or []) if f in PLANNER_RENDER_FAMILIES]
    if not effective_envelope:
        effective_envelope = [family]
    is_multi_family = len(effective_envelope) > 1

    disclosed_entity_ids = [
        entity_id for entity_id in (entity_ids or []) if isinstance(entity_id, str) and entity_id
    ]
    entity_id_schema: dict[str, Any] = (
        {"enum": list(dict.fromkeys(disclosed_entity_ids))}
        if disclosed_entity_ids
        else {"type": "string"}
    )

    if is_multi_family:
        chart_spec_fragment = _multi_family_chart_spec_schema(effective_envelope, entity_id_schema)
    else:
        single_spec = PLANNER_RENDER_FAMILIES.get(effective_envelope[0], PLANNER_RENDER_FAMILIES["time_series"])
        chart_spec_fragment = _single_family_chart_spec_schema(single_spec, entity_id_schema)

    schema = load_schema_document(PLANNER_RESULT_SCHEMA_PATH)
    schema.setdefault("properties", {})["chart_spec"] = chart_spec_fragment
    return schema


def _time_range_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["type", "start", "end"],
        "additionalProperties": False,
        "properties": {
            "type": {"const": "absolute"},
            "start": {"type": "string", "format": "date-time"},
            "end": {"type": "string", "format": "date-time"},
        },
    }


def _single_family_chart_spec_schema(spec: dict[str, Any], entity_id_schema: dict[str, Any]) -> dict[str, Any]:
    """Build the chart_spec schema fragment for a single-family (ADR-0022) envelope."""
    return {
        "type": "object",
        "required": ["chart_id", "chart_type", "title", "summary", "time_range", "series"],
        "additionalProperties": False,
        "properties": {
            "chart_id": {"type": "string"},
            "chart_type": {"enum": [spec["chart_type"]]},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "time_range": _time_range_schema(),
            "series": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["series_id", "label", "source", "role", "render_as", "transform", "unit"],
                    "additionalProperties": False,
                    "properties": {
                        "series_id": {"type": "string"},
                        "label": {"type": "string"},
                        "source": {
                            "type": "object",
                            "required": ["type", "entity_id", "attribute"],
                            "additionalProperties": False,
                            "properties": {
                                "type": {"enum": ["entity"]},
                                "entity_id": entity_id_schema,
                                "attribute": {"type": ["string", "null"]},
                            },
                        },
                        "role": {"enum": ["primary", "comparison", "secondary", "annotation"]},
                        "render_as": {"enum": [spec["render_as"]]},
                        "transform": {
                            "type": "object",
                            "required": ["operation", "window"],
                            "additionalProperties": False,
                            "properties": {
                                "operation": {"enum": ["none"]},
                                "window": {"type": ["string", "null"]},
                            },
                        },
                        "unit": {"type": ["string", "null"]},
                    },
                },
            },
            "overlays": {"type": "array", "items": {"type": "object"}},
            "x_axis": {"type": "object"},
            "y_axis": {"type": "object"},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
    }


def _multi_family_chart_spec_schema(families: list[str], entity_id_schema: dict[str, Any]) -> dict[str, Any]:
    """Build the chart_spec schema fragment for a multi-family (ADR-0023) envelope.

    ``chart_type`` is an enum of all families' chart_type values; ``render_as``
    and ``source.type`` are permissive enough for all families.  The
    out-of-envelope gate + renderer validate the actual choice post-hoc.
    """
    chart_types = list(dict.fromkeys(
        PLANNER_RENDER_FAMILIES[f]["chart_type"] for f in families if f in PLANNER_RENDER_FAMILIES
    ))
    render_as_values = list(dict.fromkeys(
        PLANNER_RENDER_FAMILIES[f]["render_as"] for f in families if f in PLANNER_RENDER_FAMILIES
    ))
    has_aggregate = "aggregate_bar" in families
    source_types: list[str] = ["entity", "aggregate"] if has_aggregate else ["entity"]
    return {
        "type": "object",
        "required": ["chart_id", "chart_type", "title", "summary", "time_range", "series"],
        "additionalProperties": False,
        "properties": {
            "chart_id": {"type": "string"},
            "chart_type": {"enum": chart_types},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "time_range": _time_range_schema(),
            "series": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["series_id", "label", "source", "role", "render_as", "transform", "unit"],
                    "additionalProperties": False,
                    "properties": {
                        "series_id": {"type": "string"},
                        "label": {"type": "string"},
                        "source": {
                            "type": "object",
                            "required": ["type", "entity_id"],
                            "additionalProperties": False,
                            "properties": {
                                "type": {"enum": source_types},
                                "entity_id": entity_id_schema,
                                "attribute": {"type": ["string", "null"]},
                                "operation": {"enum": ["mean", "min", "max", "sum", "count"]},
                            },
                        },
                        "role": {"enum": ["primary", "comparison", "secondary", "annotation"]},
                        "render_as": {"enum": render_as_values},
                        "transform": {
                            "type": "object",
                            "required": ["operation", "window"],
                            "additionalProperties": False,
                            "properties": {
                                "operation": {"enum": ["none"]},
                                "window": {"type": ["string", "null"]},
                            },
                        },
                        "unit": {"type": ["string", "null"]},
                    },
                },
            },
            "overlays": {"type": "array", "items": {"type": "object"}},
            "x_axis": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "bin_count": {"type": "integer", "minimum": 1},
                    "group_by": {"type": "string"},
                },
            },
            "y_axis": {"type": "object"},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
    }


def load_entity_selector_schema(candidate_entity_ids: list[str]) -> dict[str, Any]:
    """Build a structured-output schema for entity selection (ADR-0024 D2).

    Pins candidate entity IDs to an enum so the provider's constrained
    decoding cannot return an entity outside the disclosed candidate set.
    """
    deduped = list(dict.fromkeys(
        eid for eid in candidate_entity_ids if isinstance(eid, str) and eid
    ))
    entity_id_items: dict[str, Any] = {"enum": deduped} if deduped else {"type": "string"}
    return {
        "type": "object",
        "required": ["status"],
        "additionalProperties": False,
        "properties": {
            "status": {"enum": ["entity_selected", "clarification_needed"]},
            "entity_ids": {
                "type": "array",
                "minItems": 1,
                "items": entity_id_items,
            },
            "reasoning_summary": {"type": ["string", "null"]},
        },
    }


def planner_client_metadata(planner: Any) -> dict[str, str]:
    """Return schema-safe provider metadata from a planner client."""
    if hasattr(planner, "provider_metadata"):
        metadata = planner.provider_metadata()
        if isinstance(metadata, dict):
            return {
                "type": str(metadata.get("type") or MODEL_PROVIDER_OLLAMA_COMPATIBLE),
                "role": str(metadata.get("role") or "planner"),
                "endpoint_url": str(metadata.get("endpoint_url") or ""),
                "model": str(metadata.get("model") or metadata.get("planner_model") or ""),
            }

    return {
        "type": str(getattr(planner, "provider_type", MODEL_PROVIDER_OLLAMA_COMPATIBLE)),
        "role": str(getattr(planner, "role", "planner")),
        "endpoint_url": str(getattr(planner, "endpoint_url", "")),
        "model": str(getattr(planner, "planner_model", "")),
    }


def model_provider_setup_side_effects() -> dict[str, bool]:
    """Return side-effect accounting for model-provider setup."""
    return {
        "model_provider_called": False,
        "worker_called": False,
        "home_assistant_history_called": False,
        "home_assistant_service_or_state_mutation_called": False,
        "semantic_memory_called": False,
        "token_generated": False,
    }


class OllamaCompatiblePlannerClient:
    """Small stdlib client for Ollama-compatible planner chat calls."""

    provider_type = MODEL_PROVIDER_OLLAMA_COMPATIBLE
    role = "planner"

    def __init__(
        self,
        *,
        endpoint_url: str,
        planner_model: str,
        timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip("/")
        self.planner_model = planner_model
        self.timeout_seconds = timeout_seconds

    def provider_metadata(self) -> dict[str, str]:
        return {
            "type": self.provider_type,
            "role": self.role,
            "endpoint_url": self.endpoint_url,
            "model": self.planner_model,
        }

    def plan_chart(
        self,
        request: dict[str, Any],
        *,
        result_schema: dict[str, Any] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Call `/api/chat` with structured output and return a PlannerResult.

        When ``on_reasoning`` is provided the call uses two passes (ADR-0025 D1):
        Pass 1 streams with ``think:true`` (no format) so reasoning chunks are
        delivered to the card via the callback. Pass 2 is a non-streaming call
        with ``format:result_schema`` for reliable schema-constrained JSON —
        Ollama suppresses thinking when format is set, so they cannot share a
        single call. When ``on_reasoning`` is None a single format-constrained
        call is made (D6 fallback, unchanged behavior).

        ``temperature`` overrides the structured pass's default temperature 0 —
        used by the bounded re-plan loop so a retry is a genuinely fresh sample
        rather than a near-greedy repeat of the rejected plan (see
        docs/specs/planner-replan-on-validation-failure.md).
        """
        schema = result_schema or load_planner_result_schema()
        chat_url = _ollama_chat_url(self.endpoint_url)

        if on_reasoning is not None:
            # Pass 1 — thinking only: stream reasoning to the card, ignore content.
            think_payload = self._chat_payload(request, schema, stream=True)
            _LOGGER.debug(
                "Isolinear -> Ollama plan_chart think request: model=%s url=%s body=%s",
                self.planner_model,
                chat_url,
                json.dumps(think_payload, separators=(",", ":")),
            )
            self._read_chat(chat_url, think_payload, label="plan_chart_think", on_reasoning=on_reasoning)
            # Thinking-pass content is discarded; failures are non-fatal since
            # reasoning is presentational — planning proceeds regardless.

        # Pass 2 (or sole pass when not streaming): format-constrained structured output.
        plan_payload = self._chat_payload(request, schema, stream=False, temperature=temperature)
        _LOGGER.debug(
            "Isolinear -> Ollama plan_chart request: model=%s url=%s body=%s",
            self.planner_model,
            chat_url,
            json.dumps(plan_payload, separators=(",", ":")),
        )
        content, response_payload, failure = self._read_chat(
            chat_url, plan_payload, label="plan_chart", on_reasoning=None
        )
        if failure is not None:
            return failure
        if not isinstance(content, str) or not content.strip():
            return _provider_failure("model_provider_empty_response", "Planner response content was empty.", retry_safe=True)

        try:
            planner_result = json.loads(_strip_markdown_json(content))
        except json.JSONDecodeError as exc:
            return _provider_failure("model_provider_non_json_response", str(exc), retry_safe=False)

        return {
            "accepted": True,
            "code": "model_provider_planner_result_received",
            "provider": self.provider_metadata(),
            "planner_result": planner_result,
            "provider_response": _provider_response_summary(response_payload),
        }

    def select_entity(
        self,
        request: dict[str, Any],
        *,
        result_schema: dict[str, Any] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Call /api/chat to select an approved entity for the prompt (ADR-0024 D2).

        Uses the same two-pass approach as plan_chart when ``on_reasoning`` is
        provided: a streaming think pass delivers reasoning to the card, then a
        format-constrained pass returns the validated selection result.
        """
        schema = result_schema or load_entity_selector_schema(request.get("candidate_entity_ids", []))
        chat_url = _ollama_chat_url(self.endpoint_url)

        if on_reasoning is not None:
            think_payload = self._entity_selector_payload(request, schema, stream=True)
            _LOGGER.debug(
                "Isolinear -> Ollama select_entity think request: model=%s url=%s body=%s",
                self.planner_model,
                chat_url,
                json.dumps(think_payload, separators=(",", ":")),
            )
            self._read_chat(chat_url, think_payload, label="select_entity_think", on_reasoning=on_reasoning)

        select_payload = self._entity_selector_payload(request, schema, stream=False)
        _LOGGER.debug(
            "Isolinear -> Ollama select_entity request: model=%s url=%s body=%s",
            self.planner_model,
            chat_url,
            json.dumps(select_payload, separators=(",", ":")),
        )
        content, response_payload, failure = self._read_chat(
            chat_url, select_payload, label="select_entity", on_reasoning=None
        )
        if failure is not None:
            return failure
        if not isinstance(content, str) or not content.strip():
            return _provider_failure(
                "model_provider_empty_response",
                "Entity selector response content was empty.",
                retry_safe=True,
            )
        try:
            selection_result = json.loads(_strip_markdown_json(content))
        except json.JSONDecodeError as exc:
            return _provider_failure("model_provider_non_json_response", str(exc), retry_safe=False)
        return {
            "accepted": True,
            "code": "model_provider_entity_selection_received",
            "provider": self.provider_metadata(),
            "selection_result": selection_result,
            "provider_response": _provider_response_summary(response_payload),
        }

    def generate_chart_code(
        self,
        request: dict[str, Any],
        *,
        model: str | None = None,
        user_request: str | None = None,
    ) -> dict[str, Any]:
        """Generate freeform matplotlib chart code for a validated ChartSpec.

        ADR-0029 packet 4. Unlike ``plan_chart``/``select_entity`` (which return
        constrained JSON), codegen output is *freeform Python* — a single
        ``render_chart(data, output_path)`` function implementing the already-
        validated ChartSpec. Ollama's ``format`` is for JSON only, so this call
        sets no ``format``; the model's fenced code is extracted with
        ``_extract_python_code`` (tolerant of prose around the fence, unlike the
        JSON-only ``_strip_markdown_json``). ``model`` overrides the model id (used to
        point codegen at a code-specialized model while keeping the planner
        model); it defaults to ``planner_model``.
        """
        chat_url = _ollama_chat_url(self.endpoint_url)
        payload = self._codegen_payload(request, model=model, user_request=user_request)
        _LOGGER.debug(
            "Isolinear -> Ollama generate_chart_code request: model=%s url=%s body=%s",
            payload["model"],
            chat_url,
            json.dumps(payload, separators=(",", ":")),
        )
        content, response_payload, failure = self._read_chat(
            chat_url, payload, label="generate_chart_code", on_reasoning=None
        )
        if failure is not None:
            return failure
        if not isinstance(content, str) or not content.strip():
            return _provider_failure(
                "model_provider_empty_response",
                "Chart-code generation response content was empty.",
                retry_safe=True,
            )
        python_code = _extract_python_code(content)
        if not python_code.strip():
            return _provider_failure(
                "model_provider_empty_response",
                "Chart-code generation produced no code after fence stripping.",
                retry_safe=True,
            )
        response_summary = _provider_response_summary(response_payload or {})
        result = {
            "accepted": True,
            "code": "model_provider_chart_code_received",
            "provider": self._codegen_provider_metadata(model),
            "python_code": python_code,
            "provider_response": response_summary,
        }
        # Overflow produces bad-but-"accepted" content (the model, missing its
        # instructions, emits prose that fails the sandbox downstream), so the
        # flag rides the accepted result for the orchestration to act on.
        overflow = _context_overflow(response_summary, _CODEGEN_NUM_CTX)
        if overflow is not None:
            result["context_overflow"] = overflow
        return result

    def repair_chart_code(
        self,
        previous_code: str,
        sandbox_error: dict[str, Any],
        request: dict[str, Any],
        *,
        model: str | None = None,
        user_request: str | None = None,
    ) -> dict[str, Any]:
        """Ask the model to repair chart code that failed in the sandbox.

        ADR-0029 packet 4. Feeds the previous code and the sandbox error
        (``code``, ``message``, and the traceback from ``details`` when present)
        back to the model and asks for corrected freeform Python. Same
        markdown-stripped, ``_provider_failure``-on-error contract as
        ``generate_chart_code``. Per ADR-0030 every sandbox failure class is
        repairable — including ``unsafe_code`` — so the error view carries the
        static-check ``violations`` (the specific disallowed constructs) and not
        just the runtime traceback, or the model would repair blind.
        """
        chat_url = _ollama_chat_url(self.endpoint_url)
        payload = self._codegen_repair_payload(
            previous_code, sandbox_error, request, model=model, user_request=user_request
        )
        _LOGGER.debug(
            "Isolinear -> Ollama repair_chart_code request: model=%s url=%s body=%s",
            payload["model"],
            chat_url,
            json.dumps(payload, separators=(",", ":")),
        )
        content, response_payload, failure = self._read_chat(
            chat_url, payload, label="repair_chart_code", on_reasoning=None
        )
        if failure is not None:
            return failure
        if not isinstance(content, str) or not content.strip():
            return _provider_failure(
                "model_provider_empty_response",
                "Chart-code repair response content was empty.",
                retry_safe=True,
            )
        python_code = _extract_python_code(content)
        if not python_code.strip():
            return _provider_failure(
                "model_provider_empty_response",
                "Chart-code repair produced no code after fence stripping.",
                retry_safe=True,
            )
        response_summary = _provider_response_summary(response_payload or {})
        result = {
            "accepted": True,
            "code": "model_provider_chart_code_repaired",
            "provider": self._codegen_provider_metadata(model),
            "python_code": python_code,
            "provider_response": response_summary,
        }
        overflow = _context_overflow(response_summary, _CODEGEN_NUM_CTX)
        if overflow is not None:
            result["context_overflow"] = overflow
        return result

    def _codegen_model(self, model: str | None) -> str:
        return model or self.planner_model

    def _codegen_provider_metadata(self, model: str | None) -> dict[str, str]:
        return {
            "type": self.provider_type,
            "role": "codegen",
            "endpoint_url": self.endpoint_url,
            "model": self._codegen_model(model),
        }

    def _codegen_payload(
        self, request: dict[str, Any], *, model: str | None, user_request: str | None = None
    ) -> dict[str, Any]:
        # ADR-0034: the task is reframed to "fulfill user_request" (guided by the
        # ChartSpec) and user_request is disclosed alongside it, so the model
        # knows whether the ask is a plain plot or a computed analysis/answer.
        prompt_payload = {
            "task": (
                "Fulfill user_request: write Python matplotlib code that renders a chart "
                "answering the user's request from the supplied history_series data, guided "
                "by the supplied, already-validated Isolinear ChartSpec."
            ),
            "user_request": _bounded_user_request(user_request),
            "rules": _CODEGEN_PROMPT_RULES,
            "codegen_request": _codegen_request_view(request),
        }
        return {
            "model": self._codegen_model(model),
            "messages": [
                {"role": "system", "content": _CODEGEN_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(prompt_payload, separators=(",", ":")),
                },
            ],
            "stream": False,
            # Freeform Python, NOT constrained JSON: Ollama `format` is for JSON
            # only, so no `format` is set. Fenced code is stripped downstream.
            "options": {"temperature": 0, "num_ctx": _CODEGEN_NUM_CTX},
        }

    def _codegen_repair_payload(
        self,
        previous_code: str,
        sandbox_error: dict[str, Any],
        request: dict[str, Any],
        *,
        model: str | None,
        user_request: str | None = None,
    ) -> dict[str, Any]:
        error_view = _sandbox_error_view(sandbox_error)
        # ADR-0034: carry user_request into repair too, so a fix that has to
        # rewrite the analysis keeps the intent (the rules reference user_request).
        # Rules are PRUNED to the failure class (see _repair_prompt_rules): the
        # full list truncated the repair prompt at _CODEGEN_NUM_CTX, evicting the
        # contract itself. previous_code carries the surviving intent; the task
        # text below pins the change to the reported error.
        prompt_payload = {
            "task": (
                "The previous render_chart code failed in the sandbox. Return corrected "
                "Python matplotlib code that fixes the reported error, still fulfills "
                "user_request, and still implements the ChartSpec. Keep everything in "
                "previous_code that is not implicated in the error — including its data "
                "access, computed series, answer_text and claims — rather than rewriting "
                "from scratch. If sandbox_error.violations "
                "is present, each entry carries a violation 'code', a 'line' number, the "
                "sandbox 'message', and — when available — the exact offending 'source_line' "
                "from your previous code. Fix each violation on its line: 'unsafe_code' "
                "entries name a disallowed import, attribute, or call (remove or replace it, "
                "using only the allowed libraries in the rules; do not reintroduce it); "
                "'syntax_error' entries name a Python syntax error to correct on that exact line."
            ),
            "user_request": _bounded_user_request(user_request),
            "rules": _repair_prompt_rules(error_view, request if isinstance(request, Mapping) else {}),
            "previous_code": previous_code,
            "sandbox_error": error_view,
            "codegen_request": _codegen_request_view(request),
        }
        return {
            "model": self._codegen_model(model),
            "messages": [
                {"role": "system", "content": _CODEGEN_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(prompt_payload, separators=(",", ":")),
                },
            ],
            "stream": False,
            "options": {"temperature": 0, "num_ctx": _CODEGEN_NUM_CTX},
        }

    def _read_chat(
        self,
        chat_url: str,
        payload: dict[str, Any],
        *,
        label: str,
        on_reasoning: Callable[[str], None] | None,
    ) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
        """Execute one /api/chat POST and return (content, response, failure).

        Exactly one of ``failure`` (a sanitized provider-failure dict) or the
        ``(content, response)`` pair is meaningful. When ``on_reasoning`` is
        provided the body is streamed NDJSON (ADR-0025 D1); otherwise it is a
        single JSON read. Transport errors mid-stream return the same failures
        the non-streaming path returns (R4).
        """
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        http_request = urllib.request.Request(
            chat_url,
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                if on_reasoning is None:
                    response_payload = json.loads(response.read().decode("utf-8"))
                    message = (
                        response_payload.get("message")
                        if isinstance(response_payload, dict)
                        else None
                    )
                    content = message.get("content") if isinstance(message, dict) else None
                    _LOGGER.debug(
                        "Isolinear <- Ollama %s response: %s",
                        label,
                        json.dumps(response_payload, separators=(",", ":")),
                    )
                    return content, response_payload, None
                content, response_payload = self._consume_ndjson(response, on_reasoning)
                _LOGGER.debug(
                    "Isolinear <- Ollama %s streamed response: %s",
                    label,
                    json.dumps(response_payload, separators=(",", ":")),
                )
                return content, response_payload, None
        except urllib.error.HTTPError as exc:
            _LOGGER.debug("Isolinear <- Ollama %s HTTP error: %s", label, exc)
            return None, None, _provider_failure("model_provider_http_error", str(exc), retry_safe=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            _LOGGER.debug("Isolinear <- Ollama %s connection error: %s", label, exc)
            return None, None, _provider_failure("model_provider_connection_error", str(exc), retry_safe=True)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            _LOGGER.debug("Isolinear <- Ollama %s response error: %s", label, exc)
            return None, None, _provider_failure("model_provider_response_error", str(exc), retry_safe=False)

    def _consume_ndjson(
        self,
        response: Any,
        on_reasoning: Callable[[str], None],
    ) -> tuple[str, dict[str, Any]]:
        """Read an Ollama NDJSON chat stream, accumulating thinking + content.

        Calls ``on_reasoning`` with the sanitized accumulated thinking after each
        delta that carries thinking. Models that emit no separate thinking trace
        produce no reasoning callbacks at all — the D6 graceful fallback per
        ADR-0025 (nothing is shown), not a fall-through to content deltas.
        Returns the fully assembled final ``message.content`` (the
        structured-output JSON) and the last raw chunk as the response summary
        source.
        """
        thinking_parts: list[str] = []
        content_parts: list[str] = []
        last_chunk: dict[str, Any] = {}
        for raw_line in response:
            line = raw_line.decode("utf-8").strip() if isinstance(raw_line, (bytes, bytearray)) else str(raw_line).strip()
            if not line:
                continue
            chunk = json.loads(line)
            if not isinstance(chunk, dict):
                continue
            last_chunk = chunk
            message = chunk.get("message")
            if not isinstance(message, dict):
                continue
            thinking_delta = message.get("thinking")
            content_delta = message.get("content")
            saw_thinking = isinstance(thinking_delta, str) and thinking_delta != ""
            if saw_thinking:
                thinking_parts.append(thinking_delta)
            if isinstance(content_delta, str) and content_delta != "":
                content_parts.append(content_delta)
            # Surface accumulated thinking only. Non-thinking models emit no
            # reasoning (D6 graceful fallback per ADR-0025).
            if saw_thinking:
                on_reasoning(sanitize_reasoning("".join(thinking_parts)))
        return "".join(content_parts), last_chunk

    def _entity_selector_payload(
        self, request: dict[str, Any], result_schema: dict[str, Any], *, stream: bool = False
    ) -> dict[str, Any]:
        prompt_payload = {
            "task": "Select the approved Home Assistant entity (or entities) the user is asking about.",
            "rules": [
                "Choose only from the candidate_entity_ids list.",
                "Return status entity_selected with a non-empty entity_ids list if the user's intent is clear.",
                "Home Assistant climate entities represent HVAC systems (thermostats, "
                "heat pumps, mini-splits, AC units); map functional words like 'AC', "
                "'air conditioning', 'heating', or 'the cooling' to the matching climate entity.",
                "If already_selected_entity_ids is present, those entities were resolved "
                "for part of the request. Confirm them and ADD any other candidate entities "
                "the prompt also refers to (a prompt may mention several distinct concepts). "
                "Return the complete entity_ids set, keeping the already-selected ones unless "
                "one is clearly wrong for the prompt.",
                "Return status clarification_needed if you genuinely cannot determine which entity the user means.",
                "Do not guess when genuinely ambiguous.",
                "Do not include raw Home Assistant data, secrets, tokens, or prose outside JSON.",
            ],
            "entity_selector_request": deepcopy(request),
            "entity_selector_result_schema": result_schema,
        }
        return {
            "model": self.planner_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the Isolinear entity selector. Return only JSON that validates "
                        "against the supplied entity_selector_result_schema."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt_payload, separators=(",", ":")),
                },
            ],
            "stream": stream,
            # Thinking mode and Ollama structured-output format are mutually
            # exclusive: Ollama suppresses thinking when format is set.  When
            # streaming (reasoning requested) we omit format and rely on the
            # system-prompt schema guidance + _strip_markdown_json post-processing.
            # Non-streaming calls keep format for strict constrained decoding.
            **({"think": True} if stream else {"format": result_schema}),
            "options": {
                "temperature": 0,
                # Cap thinking tokens on the think pass so simple queries don't
                # spend 30-40 s generating 1500+ reasoning tokens. The result
                # pass (stream=False) is uncapped: it produces the final JSON and
                # needs enough tokens to complete the structured output.
                **({"num_predict": 512} if stream else {}),
            },
        }

    def check_health(self, request: dict[str, Any]) -> dict[str, Any]:
        """Call the Ollama tags endpoint and return provider health metadata."""
        http_request = urllib.request.Request(
            _ollama_tags_url(self.endpoint_url),
            headers={"Accept": request.get("headers", {}).get("accept", "application/json")},
            method="GET",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return _provider_failure("model_provider_health_http_error", str(exc), retry_safe=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            return _provider_failure("model_provider_health_connection_error", str(exc), retry_safe=True)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _provider_failure("model_provider_health_response_error", str(exc), retry_safe=False)

        model_names = _ollama_model_names(response_payload)
        model_ready = _planner_model_is_listed(self.planner_model, model_names)
        status = "ready" if model_ready else "not_ready"
        return {
            "accepted": True,
            "code": "model_provider_health_result_received",
            "provider": self.provider_metadata(),
            "health_result": {
                "version": 1,
                "status": status,
                "code": f"model_provider_health_{status}",
                "message": (
                    "Configured planner model is available."
                    if model_ready
                    else "Configured planner model was not listed by the provider."
                ),
                "checks": [
                    {"name": "ollama_tags_endpoint", "status": "pass"},
                    {"name": "planner_model", "status": "pass" if model_ready else "not_ready"},
                ],
                "capabilities": {
                    "planning": model_ready,
                    "structured_output": model_ready,
                },
            },
            "provider_response": {
                "model_count": len(model_names),
            },
        }

    def _chat_payload(
        self,
        request: dict[str, Any],
        result_schema: dict[str, Any],
        *,
        stream: bool = False,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        chart_type, render_as = _chart_family_from_schema(result_schema)
        # Detect multi-family envelope (ADR-0023): chart_type enum has >1 value.
        try:
            chart_type_enum: list[str] = result_schema["properties"]["chart_spec"]["properties"]["chart_type"]["enum"]
        except (KeyError, TypeError):
            chart_type_enum = [chart_type]
        is_multi_family = len(chart_type_enum) > 1
        if is_multi_family:
            chart_type_rule = (
                f"Choose chart_type from {chart_type_enum} to best match user intent: "
                "time_series for trends over time, histogram for value distributions, "
                "bar for aggregate/summary values per period. "
                "Match render_as to the chosen type: line for time_series, histogram for histogram, bar for bar. "
                "For histogram add x_axis with type 'value' and bin_count (default 8). "
                "For bar add x_axis with type 'category' and group_by ('day' or 'hour'). "
                "For bar series use source type 'aggregate' with entity_id and operation (mean/min/max/sum/count). "
                "For time_series and histogram series use source type 'entity' with entity_id and attribute null."
            )
        else:
            chart_type_rule = (
                f"Use chart_type {chart_type}, render_as {render_as}, transform operation none, "
                "x_axis type time, and overlays []."
            )
        overlay_entity_ids: list[str] = request.get("overlay_entity_ids") or []
        overlay_rule = (
            f"The integration will automatically add shaded overlays for these entities: "
            f"{overlay_entity_ids}. Do NOT include them in series and do NOT treat them as missing — "
            "they are handled by the system. For each one, add an entry to a top-level overlay_labels "
            "object mapping the entity_id to a short human label for the overlay, anchored on the user's "
            "own wording (for example \"AC running\"). Return status chart_spec_ready for the numeric series only."
        ) if overlay_entity_ids else None
        prompt_payload = {
            "task": "Return one PlannerResult JSON object for an Isolinear chart plan.",
            "rules": [
                "Use only approved_entity_ids supplied in the request.",
                "If the prompt asks about a device, sensor, appliance, or concept (such as AC, thermostat, door, alarm, etc.) "
                "that is NOT represented by any entity in approved_entity_ids, return status clarification_needed with a "
                "clarification_question explaining what could not be found. Never invent, relabel, or reuse an existing "
                "entity to stand in for a missing one.",
                "Only return status chart_spec_ready if every piece of information the user asked for can be represented "
                "using only the approved_entity_ids provided.",
                # ADR-0034: without this the planner reads an analysis prompt (a
                # correlation/average/heatmap is not itself an entity) as missing
                # data and refuses. Live-verified to flip the heatmap refusal to a
                # ready plan of the raw input series; generated code does the math.
                # ADR-0034; hardened after live e2e-18: a variance sample can try to
                # plan the computed result (an "Average"/"Deviation" series) as its
                # own series — but the result is not an entity, so constrained
                # decoding forces it onto an already-used approved entity_id →
                # duplicate-source rejection (invalid_model_provider_chart_spec),
                # the 0.1.37 relabel-reuse class through a new door.
                "A prompt asking for a computed analysis over approved entities — a correlation, an average or "
                "difference between sensors, a distribution or histogram, a deviation, a smoothed/rolling series, "
                "or a question about the data — IS satisfiable and must return status chart_spec_ready: plan one "
                "series per approved input entity the analysis needs (the raw inputs); downstream generated code "
                "computes the analysis from those series. NEVER add an extra series for the computed result itself "
                "(no 'Average', 'Difference', or 'Deviation' series) — the computed result is not an approved "
                "entity and is derived downstream. Do not return clarification_needed just because the prompt "
                "asks for math, a distribution, or a question rather than a plain chart.",
                "Each series must represent a distinct approved entity. Never create multiple series for the same entity_id.",
                "The chart_spec must use chart_type, not graph_type.",
                "Each series must include series_id, label, source, role, render_as, transform, and unit.",
                "Each entity series source must be {\"type\":\"entity\",\"entity_id\":\"<approved id>\",\"attribute\":null}.",
                "Set chart_spec.summary to one plain-language sentence describing what the chart shows — a rephrase "
                "of the user's request that names the series, optionally with a brief observation. Do not echo the "
                "prompt verbatim and do not include entity IDs.",
                chart_type_rule,
                *([overlay_rule] if overlay_rule else []),
                "Resolve the requested time window into an absolute time_range "
                "{\"type\":\"absolute\",\"start\":<ISO8601>,\"end\":<ISO8601>} using the "
                "request now and time_zone. Interpret fuzzy phrases (for example "
                "\"last weekend\", \"during the night\", \"since the spring equinox\") "
                "relative to now. Use timezone-aware ISO 8601 timestamps and never set end after now.",
                "Do not include raw Home Assistant history, secrets, worker URLs, tokens, or prose outside JSON.",
            ],
            "planner_request": deepcopy(request),
            "planner_result_schema": result_schema,
            "minimal_chart_spec_example": {
                "chart_id": f"approved_entity_{chart_type}",
                "chart_type": chart_type,
                "title": "Approved entity history",
                "summary": "The approved entity's recent history.",
                "time_range": {
                    "type": "absolute",
                    "start": "2026-06-17T00:00:00+00:00",
                    "end": "2026-06-18T00:00:00+00:00",
                },
                "series": [
                    {
                        "series_id": "approved_entity",
                        "label": "Approved Entity",
                        "source": {
                            "type": "entity",
                            "entity_id": "<one approved_entity_ids value>",
                            "attribute": None,
                        },
                        "role": "primary",
                        "render_as": render_as,
                        "transform": {"operation": "none", "window": None},
                        "unit": None,
                    }
                ],
                "overlays": [],
                "x_axis": {"type": "time"},
                "y_axis": {},
                "notes": [],
            },
        }
        return {
            "model": self.planner_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the Isolinear planner. Return only JSON that validates "
                        "against the supplied PlannerResult schema."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt_payload, separators=(",", ":")),
                },
            ],
            "stream": stream,
            # Thinking mode and Ollama structured-output format are mutually
            # exclusive: Ollama suppresses thinking when format is set.  When
            # streaming (reasoning requested) we omit format and rely on the
            # system-prompt schema guidance + _strip_markdown_json post-processing.
            # Non-streaming calls keep format for strict constrained decoding.
            **({"think": True} if stream else {"format": result_schema}),
            "options": {
                # Default temperature 0 (near-greedy) for reproducible planning;
                # the re-plan loop overrides it so a retry samples fresh.
                "temperature": 0 if temperature is None else temperature,
                # Cap thinking tokens on the think pass so simple queries don't
                # spend 30-40 s generating 1500+ reasoning tokens. The result
                # pass (stream=False) is uncapped: it produces the final JSON and
                # needs enough tokens to complete the structured output.
                **({"num_predict": 512} if stream else {}),
            },
        }


class OpenAICompatiblePlannerClient(OllamaCompatiblePlannerClient):
    """OpenAI-compatible model client (a LiteLLM proxy). ADR-0037.

    Reuses the Ollama client's prompt/schema construction — every payload
    builder's ``messages`` array is identical across providers — and overrides
    only the transport: POST ``{base}/chat/completions`` (base includes ``/v1``),
    optional ``Authorization: Bearer`` auth, ``response_format`` json_schema for
    structured output (where Ollama used ``format``), and an SSE stream.

    The ADR-0025 thinking trace is preserved and *simplified*: on this path a
    single streaming call carries BOTH ``delta.reasoning_content`` (streamed to
    the card via ``on_reasoning``, sanitized exactly as before) and
    ``delta.content`` (the structured/free output), so Ollama's two-pass
    think-then-format workaround is unnecessary. Requesting reasoning uses the
    ``reasoning_effort`` param; a model that returns no ``reasoning_content``
    degrades to the ADR-0025 D6 "nothing shown" fallback, unchanged.
    """

    provider_type = MODEL_PROVIDER_OPENAI_COMPATIBLE

    def __init__(
        self,
        *,
        endpoint_url: str,
        planner_model: str,
        api_key: str | None = None,
        reasoning_effort: str = DEFAULT_OPENAI_REASONING_EFFORT,
        timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    ) -> None:
        super().__init__(
            endpoint_url=endpoint_url,
            planner_model=planner_model,
            timeout_seconds=timeout_seconds,
        )
        self.api_key = api_key or None
        self.reasoning_effort = reasoning_effort

    # ---- transport ---------------------------------------------------------

    def _chat_completions_url(self) -> str:
        base = self.endpoint_url.rstrip("/")
        return base if base.endswith("/chat/completions") else f"{base}/chat/completions"

    def _structured_body(
        self,
        messages: list[dict[str, Any]],
        result_schema: dict[str, Any],
        *,
        stream: bool,
        temperature: float | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.planner_model,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "isolinear_result", "schema": result_schema, "strict": True},
            },
            "stream": stream,
            "temperature": 0 if temperature is None else temperature,
        }
        if stream:
            body["reasoning_effort"] = self.reasoning_effort
        return body

    def _read_openai_chat(
        self,
        body: dict[str, Any],
        *,
        label: str,
        on_reasoning: Callable[[str], None] | None,
    ) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
        """POST one /chat/completions request; return (content, response, failure).

        Streaming requests (``body['stream']``) are read as SSE, accumulating
        ``delta.reasoning_content`` → ``on_reasoning`` and ``delta.content`` →
        the assembled message. Non-streaming requests read a single JSON body.
        Transport errors return the same failure shapes as the Ollama path.
        """
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        http_request = urllib.request.Request(
            self._chat_completions_url(), data=encoded, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                if body.get("stream"):
                    content, response_payload = self._consume_sse(response, on_reasoning)
                    _LOGGER.debug("Isolinear <- LiteLLM %s streamed response summary: %s", label, response_payload)
                    return content, response_payload, None
                response_payload = json.loads(response.read().decode("utf-8"))
                _LOGGER.debug("Isolinear <- LiteLLM %s response: %s", label, json.dumps(response_payload, separators=(",", ":")))
                return _openai_message_content(response_payload), response_payload, None
        except urllib.error.HTTPError as exc:
            _LOGGER.debug("Isolinear <- LiteLLM %s HTTP error: %s", label, exc)
            return None, None, _provider_failure("model_provider_http_error", str(exc), retry_safe=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            _LOGGER.debug("Isolinear <- LiteLLM %s connection error: %s", label, exc)
            return None, None, _provider_failure("model_provider_connection_error", str(exc), retry_safe=True)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            _LOGGER.debug("Isolinear <- LiteLLM %s response error: %s", label, exc)
            return None, None, _provider_failure("model_provider_response_error", str(exc), retry_safe=False)

    def _consume_sse(
        self,
        response: Any,
        on_reasoning: Callable[[str], None] | None,
    ) -> tuple[str, dict[str, Any]]:
        """Read an OpenAI SSE chat stream, accumulating reasoning + content.

        Mirrors the Ollama NDJSON consumer's D6 posture: ``on_reasoning`` fires
        only after a delta that carries ``reasoning_content`` (models with no
        reasoning produce no callbacks). Returns the assembled ``delta.content``
        and the last chunk as the response summary source.
        """
        reasoning_parts: list[str] = []
        content_parts: list[str] = []
        last_chunk: dict[str, Any] = {}
        for raw_line in response:
            line = raw_line.decode("utf-8").strip() if isinstance(raw_line, (bytes, bytearray)) else str(raw_line).strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            if not isinstance(chunk, dict):
                continue
            last_chunk = chunk
            delta = _openai_delta(chunk)
            if delta is None:
                continue
            reasoning_delta = delta.get("reasoning_content")
            content_delta = delta.get("content")
            saw_reasoning = isinstance(reasoning_delta, str) and reasoning_delta != ""
            if saw_reasoning:
                reasoning_parts.append(reasoning_delta)
            if isinstance(content_delta, str) and content_delta != "":
                content_parts.append(content_delta)
            if saw_reasoning and on_reasoning is not None:
                on_reasoning(sanitize_reasoning("".join(reasoning_parts)))
        return "".join(content_parts), last_chunk

    # ---- structured calls (planner / entity selection) ---------------------

    def plan_chart(
        self,
        request: dict[str, Any],
        *,
        result_schema: dict[str, Any] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        schema = result_schema or load_planner_result_schema()
        messages = self._chat_payload(request, schema, stream=False)["messages"]
        body = self._structured_body(messages, schema, stream=on_reasoning is not None, temperature=temperature)
        content, response_payload, failure = self._read_openai_chat(body, label="plan_chart", on_reasoning=on_reasoning)
        if failure is not None:
            return failure
        if not isinstance(content, str) or not content.strip():
            return _provider_failure("model_provider_empty_response", "Planner response content was empty.", retry_safe=True)
        try:
            planner_result = json.loads(_strip_markdown_json(content))
        except json.JSONDecodeError as exc:
            return _provider_failure("model_provider_non_json_response", str(exc), retry_safe=False)
        return {
            "accepted": True,
            "code": "model_provider_planner_result_received",
            "provider": self.provider_metadata(),
            "planner_result": planner_result,
            "provider_response": _provider_response_summary(response_payload or {}),
        }

    def select_entity(
        self,
        request: dict[str, Any],
        *,
        result_schema: dict[str, Any] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        schema = result_schema or load_entity_selector_schema(request.get("candidate_entity_ids", []))
        messages = self._entity_selector_payload(request, schema, stream=False)["messages"]
        body = self._structured_body(messages, schema, stream=on_reasoning is not None, temperature=None)
        content, response_payload, failure = self._read_openai_chat(body, label="select_entity", on_reasoning=on_reasoning)
        if failure is not None:
            return failure
        if not isinstance(content, str) or not content.strip():
            return _provider_failure("model_provider_empty_response", "Entity selector response content was empty.", retry_safe=True)
        try:
            selection_result = json.loads(_strip_markdown_json(content))
        except json.JSONDecodeError as exc:
            return _provider_failure("model_provider_non_json_response", str(exc), retry_safe=False)
        return {
            "accepted": True,
            "code": "model_provider_entity_selection_received",
            "provider": self.provider_metadata(),
            "selection_result": selection_result,
            "provider_response": _provider_response_summary(response_payload or {}),
        }

    # ---- freeform calls (codegen generate / repair) ------------------------

    def _run_codegen(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None,
        label: str,
        code: str,
    ) -> dict[str, Any]:
        body = {"model": self._codegen_model(model), "messages": messages, "stream": False, "temperature": 0}
        content, response_payload, failure = self._read_openai_chat(body, label=label, on_reasoning=None)
        if failure is not None:
            return failure
        if not isinstance(content, str) or not content.strip():
            return _provider_failure("model_provider_empty_response", f"{label} response content was empty.", retry_safe=True)
        python_code = _extract_python_code(content)
        if not python_code.strip():
            return _provider_failure("model_provider_empty_response", f"{label} produced no code after fence stripping.", retry_safe=True)
        return {
            "accepted": True,
            "code": code,
            "provider": self._codegen_provider_metadata(model),
            "python_code": python_code,
            "provider_response": _provider_response_summary(response_payload or {}),
        }

    def generate_chart_code(
        self,
        request: dict[str, Any],
        *,
        model: str | None = None,
        user_request: str | None = None,
    ) -> dict[str, Any]:
        messages = self._codegen_payload(request, model=model, user_request=user_request)["messages"]
        return self._run_codegen(messages, model=model, label="generate_chart_code", code="model_provider_chart_code_received")

    def repair_chart_code(
        self,
        previous_code: str,
        sandbox_error: dict[str, Any],
        request: dict[str, Any],
        *,
        model: str | None = None,
        user_request: str | None = None,
    ) -> dict[str, Any]:
        messages = self._codegen_repair_payload(
            previous_code, sandbox_error, request, model=model, user_request=user_request
        )["messages"]
        return self._run_codegen(messages, model=model, label="repair_chart_code", code="model_provider_chart_code_repaired")

    # ---- health ------------------------------------------------------------

    def check_health(self, request: dict[str, Any]) -> dict[str, Any]:
        """GET /models and confirm the configured planner model is listed."""
        base = self.endpoint_url.rstrip("/")
        models_url = base if base.endswith("/models") else f"{base}/models"
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        http_request = urllib.request.Request(models_url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return _provider_failure("model_provider_health_http_error", str(exc), retry_safe=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            return _provider_failure("model_provider_health_connection_error", str(exc), retry_safe=True)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _provider_failure("model_provider_health_response_error", str(exc), retry_safe=False)

        model_names = _openai_model_names(response_payload)
        model_ready = self.planner_model in model_names
        status = "ready" if model_ready else "not_ready"
        return {
            "accepted": True,
            "code": "model_provider_health_result_received",
            "provider": self.provider_metadata(),
            "health_result": {
                "version": 1,
                "status": status,
                "code": f"model_provider_health_{status}",
                "message": (
                    "Configured planner model is available."
                    if model_ready
                    else "Configured planner model was not listed by the provider."
                ),
                "checks": [
                    {"name": "openai_models_endpoint", "status": "pass"},
                    {"name": "planner_model", "status": "pass" if model_ready else "not_ready"},
                ],
                "capabilities": {"planning": model_ready, "structured_output": model_ready},
            },
            "provider_response": {"model_count": len(model_names)},
        }


def _openai_delta(chunk: dict[str, Any]) -> dict[str, Any] | None:
    choices = chunk.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        delta = choices[0].get("delta")
        if isinstance(delta, dict):
            return delta
    return None


def _openai_message_content(response_payload: Any) -> str | None:
    choices = response_payload.get("choices") if isinstance(response_payload, dict) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    return None


def _openai_model_names(response_payload: Any) -> list[str]:
    data = response_payload.get("data") if isinstance(response_payload, dict) else None
    if not isinstance(data, list):
        return []
    return [item["id"] for item in data if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()]


def _chart_family_from_schema(result_schema: Any) -> tuple[str, str]:
    """Derive (chart_type, render_as) from a family-specific planner schema."""
    chart_type = "time_series"
    render_as = "line"
    try:
        chart_spec = result_schema["properties"]["chart_spec"]["properties"]
        chart_type = chart_spec["chart_type"]["enum"][0]
        render_as = chart_spec["series"]["items"]["properties"]["render_as"]["enum"][0]
    except (KeyError, IndexError, TypeError):
        pass
    return chart_type, render_as


def _setup_disabled(entry_id: str, code: str) -> dict[str, Any]:
    return {
        "accepted": True,
        "code": code,
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": False,
        "provider": None,
        "orchestration": model_provider_setup_side_effects(),
    }


def _has_planner_config(config_data: Any) -> bool:
    # ADR-0037: accept either supported provider type (ollama_compatible or the
    # OpenAI-compatible LiteLLM proxy). The endpoint + planner_model shape is
    # identical; only the transport differs.
    return (
        isinstance(config_data, Mapping)
        and config_data.get("model_provider_type") in (
            MODEL_PROVIDER_OLLAMA_COMPATIBLE,
            MODEL_PROVIDER_OPENAI_COMPATIBLE,
        )
        and isinstance(config_data.get("model_endpoint_url"), str)
        and config_data["model_endpoint_url"].strip().startswith(("http://", "https://"))
        and isinstance(config_data.get("planner_model"), str)
        and bool(config_data["planner_model"].strip())
    )


def _strip_markdown_json(text: str) -> str:
    """Strip markdown code fences that thinking-mode models wrap around JSON output."""
    text = text.strip()
    if text.startswith("```"):
        # Drop the opening fence line (```json or ```)
        text = text.split("\n", 1)[-1]
        # Drop the closing fence
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


# Opening fence (optional language tag) → non-greedy body → closing fence.
_CODE_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def _extract_python_code(text: str) -> str:
    """Extract Python source from a freeform (non-JSON) codegen response.

    Unlike the constrained JSON planner/selector output, freeform code replies
    routinely carry prose *around* the fenced block — a repair reply in
    particular tends to lead with "Here is the corrected code:\\n```python …".
    ``_strip_markdown_json`` only strips a fence that is the very first thing in
    the text, so any leading prose survives as line 1 and the sandbox rejects the
    whole payload with ``syntax_error`` on line 1 (observed live: repeated
    ``syntax_error@L1`` fallbacks to Pillow). This extractor pulls the body of
    the first fenced block regardless of surrounding prose, and only falls back
    to the stripped raw text when no fence is present.
    """
    if not isinstance(text, str):
        return ""
    match = _CODE_FENCE_RE.search(text)
    if match is not None:
        return match.group(1).strip()
    stripped = text.strip()
    # Opening fence with no closing fence (e.g. a truncated reply): drop the
    # opening fence line and keep whatever code followed it.
    if stripped.startswith("```"):
        parts = stripped.split("\n", 1)
        return parts[1].strip() if len(parts) > 1 else ""
    return stripped


def _ollama_chat_url(endpoint_url: str) -> str:
    if endpoint_url.rstrip("/").endswith("/api/chat"):
        return endpoint_url.rstrip("/")
    return f"{endpoint_url.rstrip('/')}/api/chat"


def _ollama_tags_url(endpoint_url: str) -> str:
    if endpoint_url.rstrip("/").endswith(MODEL_PROVIDER_HEALTH_PATH):
        return endpoint_url.rstrip("/")
    return f"{endpoint_url.rstrip('/')}{MODEL_PROVIDER_HEALTH_PATH}"


def _provider_failure(code: str, message: str, *, retry_safe: bool) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "provider_role": "planner",
        "retry_safe": retry_safe,
        "message": message,
    }


def _provider_response_summary(response_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": response_payload.get("model"),
        "done": response_payload.get("done"),
        "done_reason": response_payload.get("done_reason"),
        "prompt_eval_count": response_payload.get("prompt_eval_count"),
        "eval_count": response_payload.get("eval_count"),
    }


def _context_overflow(response_summary: Mapping[str, Any] | None, num_ctx: int) -> dict[str, Any] | None:
    """Detect a truncated (context-overflow) codegen prompt from the response.

    Ollama silently truncates a prompt that exceeds ``num_ctx`` — it drops tokens
    from the FRONT, so the system prompt and rules go first — then reports
    ``prompt_eval_count`` capped at exactly ``num_ctx``. A prompt that fits sits
    well below it. So ``prompt_eval_count >= num_ctx`` is a definitive signal that
    the model never saw the full instructions, which makes its output (and any
    repair, whose prompt is larger still) doomed. Measured against Ollama:
    overflow → ``prompt_eval_count == num_ctx`` exactly; a fitting prompt is
    strictly below. Surfaced so the integration can tell the user to raise the
    codegen model's context window, reduce the request, or use bigger hardware —
    rather than reporting a misleading downstream ``syntax_error``.
    """
    if not isinstance(response_summary, Mapping) or not isinstance(num_ctx, int):
        return None
    prompt_eval_count = response_summary.get("prompt_eval_count")
    if not isinstance(prompt_eval_count, int) or isinstance(prompt_eval_count, bool):
        return None
    if prompt_eval_count < num_ctx:
        return None
    return {"prompt_eval_count": prompt_eval_count, "num_ctx": num_ctx}


def _ollama_model_names(response_payload: Any) -> list[str]:
    if not isinstance(response_payload, dict) or not isinstance(response_payload.get("models"), list):
        return []
    names: list[str] = []
    for item in response_payload["models"]:
        if not isinstance(item, dict):
            continue
        for key in ("name", "model"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                names.append(value.strip())
    return names


def _planner_model_is_listed(planner_model: str, model_names: list[str]) -> bool:
    return any(name == planner_model or name.startswith(f"{planner_model}:") for name in model_names)
