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
- 0004 — `Chart spec first rendering with codegen option`
- 0005 — `Schema-driven contracts and history normalization`
- 0006 — `Validation and repair loop`
- 0007 — `Local-first Ollama-compatible model provider`
- 0008 — `Read-only MVP and sandbox security`
- 0009 — `Semantic memory storage`
- 0010 — `Semantic memory store envelope`
- 0011 — `Dashboard card implementation technology`
- 0012 — `Worker transport and authentication` (draft)
