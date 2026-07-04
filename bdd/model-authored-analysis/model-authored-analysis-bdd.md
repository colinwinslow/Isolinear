# Model-authored analysis: grounded answers + supporting charts — BDD

## Status

Accepted. Paired with [docs/specs/model-authored-analysis.md](../../docs/specs/model-authored-analysis.md).
ADR-0031 tranche 1. Pins the user-visible behavior of the answer channel, the
grounding guarantee, the data-boundary timestamp normalization, the two-part
quality validation with progressive-verification UX, and the scipy/seaborn +
transforms capability.

## Why this BDD exists

Isolinear now answers a question in words with a computed number in it, alongside
a supporting chart. These scenarios pin down that (1) the answer is *grounded* —
computed in the sandbox, never hallucinated; (2) a broken **number** is caught
before the user sees it, while a broken **picture** is caught and revised while
the chart is already on screen (never a blank wait); (3) the model never parses
raw HA timestamps; and (4) the fallback path degrades gracefully.

## Scenarios

### Scenario A — happy path: grounded answer ships with the supporting chart

**Given** codegen is active (`render_path: auto`) and a worker is configured (a
packet-2 worker booted in-process on an ephemeral port)
**And** the resolved output modality is `both` and two approved numeric sensors
are disclosed
**And** the model returns a `render_chart(data, output_path)` body that computes
`corr = df[a].corr(df[b])` and returns `{"answer_text": f"The correlation
coefficient is {corr:.2f}.", ...}`
**When** a render job runs
**Then** the worker renders a real PNG (valid signature on disk) **and** the
complete snapshot carries `chart.answer_text == "The correlation coefficient is
0.42."` (the number computed in the sandbox, not asserted by the model), and the
card renders the answer under the caption.

### Scenario B — grounding: the verdict is computed, not asserted

**Given** codegen is active and the prompt asks a yes/no question ("are they
correlated?")
**And** the generated code computes `verdict = "Yes" if abs(corr) > 0.3 else
"Not really"` and formats `f"{verdict} — r={corr:.2f}"`
**When** the render job runs
**Then** the answer's verdict word matches the computed threshold over the actual
data (an honest number never rides a contradicting verdict), and the answer is
assembled inside the sandbox at execution time — no second free-text model pass
over raw data occurs.

### Scenario C — data-boundary timestamp normalization (ADR-0031 D9)

**Given** approved history whose HA `points[].ts` are mixed-precision ISO strings
(first row on-the-second, later rows with microseconds)
**When** the codegen render request is built
**Then** the timestamps handed to the worker are **epoch-integer milliseconds**,
not raw ISO strings — the model never receives a `to_datetime`-ambiguous
timestamp, and a regression guard asserts no raw ISO `ts` crosses on the codegen
path. (The Pillow fallback and `render_mode: safe` paths still consume the
existing `ts` shape.)

### Scenario D — deterministic grounding check gates the FIRST display

**Given** codegen returns an `answer_text` containing a degenerate value (`r=nan`
from a single-point "regression", or a literal `0.00 °F/hr`)
**When** the render job runs
**Then** the deterministic answer-grounding check flags it **before** the chart +
answer is shown, the codegen repair loop is invoked with the grounding failure as
the feedback signal (bounded by `max_codegen_repair_attempts`), and a corrected
grounded answer is shown — or, on exhaustion, the result fails soft with a caveat
(never a confident broken number displayed as final).

### Scenario E — visual validator runs while the chart is already on screen

**Given** the configured `visual_validator_model` advertises `vision` (probed via
Ollama `/api/show` `capabilities`)
**And** the deterministic check passed, so the chart + answer is already displayed
with `verification_status: "verifying"` and a "Checking our work…" indicator
**When** the visual validator reviews the rendered PNG with the structured
checklist prompt (`think:false`) and returns PASS
**Then** the snapshot transitions to `verification_status: "verified"` and the
indicator drops — the card kept polling through the non-terminal `verifying`
state (never a blank wait).

### Scenario F — visual REVISE repairs a broken picture in place

**Given** the visual validator reviews a rendered chart with a flat-zero
"Seasonal" panel (execution + answer-text both missed it)
**When** the validator returns REVISE with a critique
**Then** the snapshot moves to `verification_status: "revising"`, the card shows a
user-facing *"found something off — revising it now"* message (the specific
critique goes to diagnostics, not the user), the visual-repair loop re-renders in
place reusing the codegen repair machinery (image + critique as the feedback
signal), and the corrected chart replaces the provisional one — bounded by
`max_visual_revise_attempts`, fail-soft to the last render with a soft caveat.

### Scenario G — capability gate: no-vision model skips the visual validator

**Given** the configured model has **no** vision capability (e.g.
`qwen2.5-coder:7b`, per `/api/show`)
**When** an answer-bearing render completes and passes the deterministic check
**Then** the visual validator is **silently skipped**, the result is delivered as
`verified` on the deterministic check alone, and no `/api/show`-gated visual pass
is attempted (default-on-when-supported, off otherwise).

### Scenario H — scipy + seaborn import together under the sandbox cap

**Given** the worker image with scipy + seaborn added to requirements + the
sandbox import allowlist
**When** the in-container check imports `matplotlib`, `pandas`, `numpy`, `scipy`,
and `seaborn` together under the `-I` sandbox
**Then** they all import successfully under the **1024MB `RLIMIT_AS`** cap (with
the OpenBLAS thread pins applied), and a `scipy.stats` correlation +
`seaborn.heatmap` render produces a valid PNG — proven live on CT103.

### Scenario I — Pillow fallback carries no answer, surfaced

**Given** codegen cannot complete (generation failure / repair exhaustion /
worker transport fault) and the job falls back to the trusted Pillow renderer
**When** the render job completes via fallback
**Then** the served chart carries `render_path: "pillow"` +
`render_fallback_reason` (ADR-0030, surfaced) and **no** `answer_text` (the
trusted Pillow renderer does not compute answers) — the card shows the chart
without an answer line, never a fabricated one.

### Scenario J — modality normalizes to `both` (first-slice constraint)

**Given** the planner emits `output_modality: "answer"` (or omits it)
**When** the integration validates the modality against the render envelope
**Then** it is normalized to `both` for the first slice — every answer ships with
a supporting chart (invariant #9 intact: the chart family is still
deterministically routed from entity kinds regardless of modality), and
answer-only remains out of scope.

## Evidence

The implementing slice(s) produce an evidence file at
`bdd/model-authored-analysis/model-authored-analysis-evidence.md` containing raw
outputs (not summaries) for each scenario: the served PNG signatures + snapshot
JSON for the answer channel; the epoch-ms request projection; raw grounding-check
verdicts; raw `/api/show` capability probes and validator checklist outputs; and
the live CT103 in-container import + render logs for Scenario H.
