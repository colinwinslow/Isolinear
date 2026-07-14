---
title: LiteLLM / OpenAI-compatible provider option (and the fate of thinking streaming)
status: open
date: 2026-07-14
---

# Research: routing Isolinear's model calls through a LiteLLM proxy

## Question

Colin is moving the homelab so LLM use goes through a **LiteLLM proxy** that
exposes an OpenAI-compatible API (and can forward to cloud-hosted models via
POE for easy model comparison), instead of Isolinear talking to Ollama's
`/api/chat` directly. Two things to answer before building it:

1. Can Isolinear add a provider option that routes through LiteLLM?
2. **Do we keep the live "thinking" stream** (ADR-0025) on that path, or is it
   Ollama-specific?

## Context

- Today `SUPPORTED_MODEL_PROVIDER_TYPES = ("ollama_compatible",)`
  (`const.py`). The single client `OllamaCompatiblePlannerClient` posts to
  `endpoint_url + /api/chat` (`_ollama_chat_url`).
- ADR-0025 streams the model's thinking trace to the card's live slot during
  the long planner/select phases. The `on_reasoning` callback and the card
  plumbing (`apply_live_reasoning`, the snapshot `progress.reasoning` field)
  are **provider-agnostic** — only the transport/parse layer is Ollama-shaped.
- A LiteLLM provider unblocks A/B'ing local vs POE-hosted cloud models without
  code changes, which is directly useful for the floor-model-capability work
  (the recurring theme behind the codegen prompt-rule packets).

## Findings — the thinking stream is Ollama-specific, but recoverable via LiteLLM

**How it works today (Ollama-only in both directions):**

- **Request:** `_chat_payload` sets `"think": true` — an Ollama-native
  `/api/chat` flag, not OpenAI. The two-pass design (a streaming think pass
  with no `format`, then a non-streaming `format`-constrained pass) exists
  *because* Ollama suppresses thinking when `format` is set — an Ollama quirk,
  not a general one.
- **Response:** `_consume_ndjson` reads Ollama **NDJSON** and pulls
  `message.thinking` as a field **separate from** `message.content`
  (`model_provider.py:1319`).

**On a generic OpenAI-compatible endpoint none of that shape holds:** the
stream is **SSE** (`data: {...}` lines, `[DONE]` terminator), content deltas
are at `choices[0].delta.content`, structured output is
`response_format: {type: "json_schema", ...}`, and **standard OpenAI exposes
no reasoning field** in the stream (o1/o3 hide reasoning tokens).

**LiteLLM specifically is the favorable case.** It normalizes reasoning across
providers into **`choices[0].delta.reasoning_content`** on the streamed delta
(plus `thinking_blocks` for Anthropic). So the thinking stream survives the
move — with caveats:

1. **Different field + format** → a second streaming parser (SSE +
   `delta.reasoning_content`) alongside the existing Ollama NDJSON one. The
   `on_reasoning` interface above it is unchanged.
2. **Model-dependent** → usually needs an enabling param (`reasoning_effort`,
   or Anthropic `thinking`). A non-reasoning model (gpt-4o, or a plain gemma
   forwarded via LiteLLM) emits no `reasoning_content`, which lands in the
   existing ADR-0025 **D6 graceful fallback** (nothing shown) — no breakage.
3. **POE-forwarded cloud models: uncertain** → many providers hide reasoning
   tokens; whether any `reasoning_content` comes back depends on what POE +
   LiteLLM surface for that model. **Probe this against the live proxy before
   committing to a design.** (Least-certain finding here.)

**Likely simplification:** on OpenAI-compat, `response_format` json_schema can
coexist with a single streaming call, so the two-pass Ollama workaround
probably collapses to ONE streaming call carrying both `reasoning_content` and
the structured `content`.

## Design sketch (when it promotes to an ADR + spec)

- New provider type (e.g. `openai_compatible` / `litellm`) added to
  `SUPPORTED_MODEL_PROVIDER_TYPES`; config-flow `model_provider_type` selector
  already exists (`vol.In(SUPPORTED_MODEL_PROVIDER_TYPES)`).
- A sibling client (or a strategy inside the existing one) that: posts to
  `/v1/chat/completions`, builds OpenAI-shaped payloads (`response_format`
  json_schema instead of `format`; `reasoning_effort`/`thinking` to request
  reasoning), and parses the SSE stream mapping `delta.reasoning_content` →
  the existing `on_reasoning` callback and `delta.content` → assembled content.
- An **API-key credential** for the proxy (LiteLLM virtual keys) — note the
  ADR-0032 write-only secret posture and the `FORBIDDEN_CONFIG_KEYS` /
  secret-vocabulary fail-closed checks in `config_schema.py`; a proxy key is a
  new secret surface that must follow that pattern (never persisted in options,
  never printed — [[feedback-secrets-inline]]).
- Keep Ollama as a supported type; this is additive.

## Open sub-questions

- Does the LiteLLM proxy (as Colin will configure it) actually surface
  `reasoning_content` for the models he cares about? Probe first.
- Structured output: does every target model behind the proxy honor
  `response_format` json_schema, or do some need the tool-call / prompt-JSON
  fallback? (Ollama's `format` is reliable; OpenAI-compat varies by backend.)
- Auth: LiteLLM virtual key handling vs the existing ADR-0032 worker-token
  pattern — one key for the whole proxy, or per-role?
- Is this one ADR ("second model provider: OpenAI-compatible / LiteLLM") or
  does the reasoning-stream parser difference warrant its own decision note?

## Resolution

Open. Blocked on a quick live probe of the proxy's `reasoning_content` behavior
before an ADR is worth writing. Logged in `STATUS.md` open queue as (dd).
