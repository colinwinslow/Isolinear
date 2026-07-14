# Research Notes

Exploratory scratch space: `docs/research/<slug>.md`. Scaffold with
`/research <slug>` (see `codex/research.md`).

## What a research note is

A place to think before committing to a decision or a contract. Research notes
are **not load-bearing** — they may or may not promote to a spec or ADR.

## Lifecycle

- Authored as `status: open`.
- When the thinking stabilizes, **promote**: write a spec (`/spec`) or an ADR
  (`/adr`), then update the note's `Resolution` section and flip `status` to
  `promoted-to-spec`, `promoted-to-adr`, or `abandoned`.
- A note that's been `open` for a long time with no movement is a signal —
  either the question doesn't matter, or it's blocked on something.

## Current research notes

- `answer-verdict-grounding-check.md` — deterministic verdict verification via a claims ledger; the design rationale behind `docs/specs/answer-grounding-check.md` (promoted-to-spec, 2026-07-03)
- `codegen-card-level-legend.md` — the ADR-0027 card-level legend wiring is intact and renderer-agnostic; the codegen path just never populates `artifact["legend"]` — three additive pieces needed (open, 2026-07-14)
- `litellm-openai-provider.md` — routing model calls through a LiteLLM/OpenAI-compatible proxy; the ADR-0025 thinking stream is Ollama-specific but recoverable via LiteLLM's `reasoning_content` (a second SSE parser; model-dependent) — probe the proxy before an ADR (open, 2026-07-14)
