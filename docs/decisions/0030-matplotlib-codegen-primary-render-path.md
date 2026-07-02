---
id: 0030
title: Matplotlib codegen is the primary render path; Pillow becomes the fallback
status: accepted
date: 2026-07-02
supersedes:
  - 0004
superseded-by: null
tags:
  - renderer
  - codegen
  - worker
  - sandbox
  - flexibility
  - model-empowerment
---

# ADR-0030: Matplotlib codegen is the primary render path; Pillow becomes the fallback

## Context

ADR-0029 revived the isolated worker as an **experiment with a kill condition**:
if 3060-class local models could not produce good-enough matplotlib code, the
worker subsystem would be removed. The packet-5 reliability eval
(`evals/codegen_reliability.py`, gallery in `evals/prompts/reliability_report.md`)
produced the decision data:

- Both `gemma4:e4b` and `qwen2.5-coder:7b` accepted **33/35 chartable prompts**
  (3 recovered via repair each) against the live CT103 worker sandbox — **~94%
  accept with repair**.
- **No sandbox false positives**: all 4 remaining rejects were legitimate (one
  forbidden `locals()` call caught by the security gate, two genuine numpy type
  bugs, one output-missing).
- The two models fail in characteristically different, largely repairable ways
  (gemma trips static checks; qwen trips runtime limits).
- Qualitatively, the matplotlib renders match or beat the Pillow renderer's
  output (date-formatted axes, gridlines, markers vs. hand-drawn primitives).

Meanwhile the trusted-renderer-first architecture (ADR-0004) has become the
project's flexibility ceiling:

- The ChartSpec `transform` vocabulary is a **closed enum**
  (`rolling_mean`/`resample_mean`/`resample_sum`/`difference`), and the Pillow
  renderer rejects every one of them (`transform_not_supported`) — only
  `none` renders.
- **Cross-series operations cannot even be expressed** in the contract: "average
  these two sensors together" has no ChartSpec representation. Growing the enum
  and implementing each operation deterministically is exactly the hard-coded
  rigidity the project has been steering away from (ADR-0023, ADR-0024,
  ADR-0028 all moved judgment into the model within deterministic envelopes).

The human called the experiment on 2026-07-02: **keep the worker, lean into
matplotlib codegen, empower the model.**

## Decision

1. **ADR-0029's kill condition resolves to KEEP.** The worker subsystem and the
   codegen render path are permanent architecture, not an experiment.

2. **Sandboxed matplotlib codegen becomes the primary render path** when a
   worker is configured and healthy. The Pillow in-process renderer (ADR-0019)
   remains fully supported as:
   - the **fallback** when no worker is configured, the worker is unhealthy, or
     the codegen path exhausts its repair attempts (fallback is **surfaced in
     render metadata and the card** — never silent), and
   - an **explicit option** for users who prefer the deterministic renderer.

3. **The ChartSpec remains the validated planning contract and the data
   boundary.** Nothing about entity allowlisting (invariant #1), sandbox
   isolation (#3), schema validation (#4), or plan validation (#5) changes.
   Only allowlisted, normalized history and the validated ChartSpec cross into
   the codegen prompt (`_codegen_request_view` projection).

4. **The model is empowered to transform data in generated code.** On-demand
   transforms — averaging sensors together, resampling, differences, derived
   series — are implemented by the model in matplotlib/numpy/pandas code, not
   by growing the ChartSpec transform enum. The closed enum stops being the
   capability ceiling; a follow-up spec defines how transform intent is carried
   from the prompt/planner into the codegen prompt.

5. **pandas is added to the worker image.** The eval showed models reaching for
   it naturally; the image-size cost is accepted (the worker is a standalone
   amd64 container, not constrained by HA packaging).

6. **The sandbox address-space cap is raised from 256 MB to 1024 MB.** The
   256 MB cap produced the only runtime-limit rejects in the eval and required
   OpenBLAS thread pinning to work at all. 1 GB comfortably fits
   matplotlib+numpy+pandas while remaining a hard bound on a 6-core/12 GB host.
   The test asserting `memory_limit_mb <= 256` is updated to the new bound.

7. **All sandbox failure classes are repairable, including static security
   rejections.** The packet-4 loop treated `unsafe_code` as terminal; the eval
   showed static rejects are usually casual model mistakes (a stray `locals()`,
   a disallowed import), not adversarial code. The repair loop now feeds
   *every* failure class back to the model, bounded by `max_repair_attempts`.
   **The security boundary is unchanged**: every attempt re-runs the full
   static safety check and executes only inside the sandbox — repair gets the
   model another try at the gate; it never bypasses the gate.

## Consequences

Positive:

- Chart flexibility is no longer bounded by hand-implemented primitives; the
  renderer's capability grows with the model, not with Pillow drawing code.
- Cross-series and on-demand transforms become expressible for the first time.
- Matplotlib output quality (axes, dates, legends) exceeds the hand-drawn
  Pillow primitives.
- The Pillow renderer stops needing new families (its histogram/aggregate_bar
  growth path ends; it is maintained as a stable fallback).

Negative / risks:

- The best render path now depends on a deployed worker; HA-only installs get
  the Pillow fallback.
- Codegen adds model latency and a repair loop to the render phase.
- "It rendered without error" is a weak quality signal (the eval showed a
  first-try accept with a mangled axis and a twice-repaired accept with the
  best chart). The `visual_validator_model` direction — repair driven by "does
  the chart match the prompt intent" — becomes the natural next quality
  investment, not an optional extra.

Invariant #6 in `CLAUDE.md` is rewritten to match this decision.

## Relation to prior ADRs

- **ADR-0004 (superseded):** its lasting half — ChartSpec as the central
  validated contract — is carried forward unchanged in Decision 3. Its default
  — trusted renderer primary, codegen an advanced option — is inverted.
- **ADR-0019 (stands, role narrowed):** Pillow remains *the* in-process
  renderer and its reasoning (matplotlib cannot install in HA's Python) remains
  true — which is exactly why the primary path lives in the worker. Only its
  "default renderer" role ends.
- **ADR-0029 (accepted, outcome recorded):** the experiment this decision
  resolves.
- **ADR-0023 (stands):** deterministic render-family routing and the
  capability envelope still govern *what* is planned; this ADR changes *who
  renders it*.
