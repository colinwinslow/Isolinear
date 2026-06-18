---
id: 0019
title: Pillow in-process renderer
status: accepted
date: 2026-06-17
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - renderer
  - packaging
  - vertical-slice
---

# ADR-0019: Pillow in-process renderer

## Context

ADR-0017 made the first real vertical slice render trusted `time_series`
ChartSpecs in-process through matplotlib. Live HACS installs then proved
matplotlib cannot be delivered into a stock Home Assistant Python environment:

- `0.1.16` declared `matplotlib==3.11.0` as a manifest `requirements` entry.
  Home Assistant installs manifest requirements *before* loading the
  integration, and the strict pin failed to resolve, returning
  `Config flow could not be loaded: 500 Internal Server Error`.
- `0.1.19` relaxed the requirement to `matplotlib>=3.7,<4`, betting that pip's
  resolver would pick an installable wheel. The live install instead resolved
  to the newest match (`matplotlib==3.11.0`), found **no prebuilt wheel for the
  runtime CPython (3.14)**, fell back to building from source, and failed with
  `PermissionError: [Errno 13] Permission denied: 'meson'`. The Home Assistant
  package-install sandbox cannot execute the meson build backend.

Because a failed requirement install makes the integration fail to load, the
integration showed **"not loaded"** in Settings → Devices & Services and the
dashboard resource stayed pinned to the previous version (setup never reached
the resource-registration step).

The conclusion is not version tuning: matplotlib's manifest-requirement
delivery is a dead end in this environment. The in-process renderer needs a
backend that does not require installing or compiling a heavy dependency.

## Decision

**The trusted in-process renderer draws with Pillow (PIL) instead of
matplotlib.** Pillow is already shipped by Home Assistant core, so the
integration declares no renderer `requirements` in its manifest. The renderer
imports Pillow lazily and fails closed with a sanitized
`renderer_dependency_unavailable` chart-rendering job failure if Pillow is
somehow unavailable.

The renderer's public contract is unchanged: `render_in_process_chart` returns
the same accepted/failure shape, the same `render_metadata` keys
(`series_plotted`, `x_min`, `x_max`, `warnings`, `codegen_attempts`), the same
PNG artifact contract, and the same supported scope (safe-mode numeric
`time_series` line charts, entity-backed sources, `transform: none`, no
overlays). The renderer identifier changes from `in_process_matplotlib` to
`in_process_pillow` in the `IntegrationArtifactMetadata` schema enum.

The manifest scaffold guard now forbids **any** `matplotlib` requirement
(regardless of version pin), not just exact pins.

## Rationale

- Pillow is a core Home Assistant dependency, so it is present without a manifest
  requirement and without a compile step — removing the failure mode entirely.
- Drawing `time_series` line charts (axes, gridlines, polylines, legend, title,
  axis labels) is well within Pillow's 2D drawing primitives.
- Keeping the renderer interface, supported scope, failure codes, and PNG
  artifact contract unchanged means orchestration, artifact serving, the
  dashboard card, and existing schemas are unaffected apart from the renderer
  enum value.
- The matplotlib-based sandboxed codegen path (ADR-0004, worker sandbox spec)
  is unaffected: that matplotlib lives in the isolated worker image, never in
  Home Assistant core.

## Consequences

**Enables:**
- A first-slice install that actually loads on a stock Home Assistant (Python
  3.14) without any compiled-dependency install.
- A real rendered PNG in the dashboard card without `RENDERER_DEPENDENCY_UNAVAILABLE`.

**Constrains:**
- The in-process renderer's visual fidelity is bounded by Pillow's drawing
  primitives (no matplotlib styling, ticking, or layout engine). The first
  supported family stays numeric `time_series` line charts.
- Follow-up trusted renderer families (state-interval timeline, aggregate bar,
  heatmap, markers, histogram, scatter) that are rendered in-process must be
  implemented against Pillow, or routed to the worker renderer.

**Open:**
- Whether richer chart families render in-process with Pillow or move to the
  worker renderer image (which may still bundle matplotlib).
- Live confirmation on the target hardware that `0.1.20` loads, registers the
  `?v=0.1.20` resource, and renders a chart end-to-end.

## Acceptance evidence

Accepted on 2026-06-17. The Pillow renderer produces a valid PNG (correct
signature, reopenable at the requested dimensions) for a two-series numeric
`time_series` ChartSpec, verified on disk. The full Python suite passes
(`351 passed`) under the canonical venv (Python 3.14.5, Pillow 12.2.0), which
matches the live Home Assistant runtime. Live HACS end-to-end confirmation of
`0.1.20` is tracked as the next packet.

## References

- ADR-0004: Chart spec first rendering with codegen option
- ADR-0008: Read-only MVP and sandbox security
- ADR-0017: First real vertical slice
- ADR-0018: Production artifact serving
- [First real vertical slice spec](../specs/home-assistant-first-real-vertical-slice.md)
- [HACS install packaging spec](../specs/home-assistant-hacs-install-packaging.md)
