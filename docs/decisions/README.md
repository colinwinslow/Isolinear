# Architecture Decision Records

One file per decision: `NNNN-<slug>.md`, zero-padded, monotonic. Scaffold with
`/adr <slug>` (see `codex/adr.md`).

## Lifecycle

- ADRs are authored as `status: draft`.
- A `draft` is promoted to `accepted` once the decision is made (and usually
  once an implementation slice lands behind it). Promotion happens at
  `/closeout`.
- Accepted ADRs are **immutable**. To change a decision, write a NEW ADR that
  names the old one in its `supersedes:` frontmatter and set the old one's
  `superseded-by:`. Never edit an accepted decision in place.
- Deprecated ADRs move to `archive/` with their status edited in place. (The
  2026-07-02 consolidation applied this as a human-approved exception to
  immutability; see ADR-0030 for the accompanying direction change.)

## Index-label convention

In the list below, `accepted` is the silent default (no label). Other states
carry a label:

- `(draft)` — not yet accepted
- `(deprecated YYYY-MM-DD)` — withdrawn
- `(superseded by NNNN)` — replaced by a later ADR

Keep this list in sync at `/closeout` whenever an ADR's status changes.

## Current ADRs

- 0001 — `Home Assistant integration plus isolated worker`
- 0002 — `Dashboard card first UI`
- 0003 — `Entity allowlist, semantic resolution, memory`
- 0005 — `Schema-driven contracts and history normalization`
- 0006 — `Validation and repair loop`
- 0007 — `Local-first Ollama-compatible model provider`
- 0008 — `Read-only MVP and sandbox security`
- 0009 — `Semantic memory storage`
- 0010 — `Semantic memory store envelope`
- 0011 — `Dashboard card implementation technology`
- 0012 — `Worker transport and authentication`
- 0013 — `Dashboard resource auto-registration`
- 0014 — `Worker health/readiness endpoint`
- 0017 — `First real vertical slice` (historical — milestone completed)
- 0018 — `Production artifact serving`
- 0019 — `Pillow in-process renderer` (role narrowed by 0030 — now the fallback renderer)
- 0020 — `Model-resolved chart time window`
- 0021 — `Tiered history data source (recorder states + long-term statistics)`
- 0022 — `Categorical timeline render family via the model-driven path`
- 0023 — `Model-proposed render family within a deterministic capability envelope`
- 0024 — `Model-driven entity selection with a deterministic disambiguation fast-path`
- 0025 — `Live planner reasoning as in-place wait feedback in the card`
- 0026 — `Model entity selection runs in the pollable planning phase, not in blocking job/start`
- 0027 — `Card-owned legend with a renderer color manifest and model-authored summary`
- 0028 — `Model-validated composition membership for overlay/timeline selection`
- 0029 — `Revive isolated worker to evaluate sandboxed model-generated chart codegen` (outcome: KEEP — see 0030)
- 0030 — `Matplotlib codegen is the primary render path; Pillow becomes the fallback` (supersedes 0004)
- 0031 — `Model-authored analysis — Isolinear answers questions, not just charts` (accepted)
- 0032 — `Deployment-configured worker token; retire the ADR-0015/0016 durability machinery` (accepted)
- 0033 — `Integration-precomputed shaded overlay bands for codegen` (accepted — deterministic overlay bands via derived_intervals, revertible)
- 0034 — `The user's request reaches the codegen model — the analysis-intent conduit` (accepted)
- 0035 — `v0.3 north star: the product is saved, re-runnable analysis code — plus the demolition plan` (accepted)
- 0036 — `In-sandbox analysis helper library — ship the idiom as a callable` (draft)

## Archived ADRs (`archive/`)

- 0004 — `Chart spec first rendering with codegen option` (superseded by 0030 —
  archived 2026-07-06; the ChartSpec-as-planning-contract half carries forward,
  the trusted-renderer-default half is inverted)
- 0015 — `Durable worker health polling` (deprecated 2026-07-02 — designed for
  the pre-reality simulated worker; the real worker (ADR-0029) is a simple HTTP
  service with `GET /v1/health`. The runtime polling machinery was
  removed by ADR-0032 on 2026-07-04.)
- 0016 — `Durable worker token lifecycle` (deprecated 2026-07-02, never left
  draft — same rationale; the real worker uses a static bearer token from
  config/secrets. Its runtime machinery was removed by ADR-0032 on 2026-07-04.)
