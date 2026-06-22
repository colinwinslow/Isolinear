Feature: Live planner reasoning as in-place wait feedback
  While the local model works (entity selection then chart planning), the card
  streams the model's sanitized, length-capped reasoning into the chart slot as
  ephemeral wait-feedback, then replaces it with the chart or the failure card.
  (ADR-0025; spec: docs/specs/live-planner-reasoning-streaming-spec.md)

  Scenario: Reasoning appears during the planning phase on each poll
    Given a streaming planner that emits thinking deltas while it plans
    And a job is in the planning phase
    When the card polls "isolinear/v1/job/snapshot" while the model is thinking
    Then the in-progress planning snapshot should carry "progress.reasoning"
    And the reasoning should reflect the accumulated thinking so far
    And a later poll should show more accumulated reasoning than an earlier poll

  Scenario: Reasoning spans both model calls with coarse phase labels
    Given a streaming planner used for entity selection and then chart planning
    When the model is selecting entities
    Then the planning snapshot stage should read "Selecting entities…"
    And the reasoning should reflect the selection thinking
    When the model is planning the chart
    Then the planning snapshot stage should read "Planning chart…"
    And the reasoning should reflect the planning thinking

  Scenario: Reasoning is replaced by the PNG on completion
    Given a job whose planning polls showed live reasoning
    When the model phase completes and the chart renders
    Then the complete snapshot should show the chart image
    And the complete snapshot should not contain "progress.reasoning"
    And the live reasoning slot for the job should be cleared

  Scenario: Reasoning is replaced by the failure card on error
    Given a job whose planning polls showed live reasoning
    When the model phase fails during planning
    Then the failed snapshot should show the failure stage and code
    And the failed snapshot should not contain "progress.reasoning"
    And the live reasoning slot for the job should be cleared

  Scenario: Off-limit content is sanitized and the trace is length-capped
    Given a streaming planner whose thinking contains a worker URL, a bearer token, and a local file path
    And the thinking trace is longer than the 2000 character cap
    When the reasoning is written onto the planning snapshot
    Then the reasoning should not contain the worker URL, the bearer token, or the file path
    And the reasoning should be at most 2000 characters
    And the reasoning should keep the most recent (tail) thinking with a leading ellipsis

  Scenario: Mid-stream transport error falls straight to the failure card
    Given a streaming planner whose NDJSON stream errors after one thinking delta
    When the card polls during planning
    Then the job should produce the failure card with a transport error code
    And no partial reasoning should be persisted on the failed snapshot

  Scenario: Non-streaming provider falls back with no reasoning shown
    Given a planner that does not support streaming or emits no thinking
    When the card polls during planning
    Then the planning snapshot should show the plain planning state
    And the planning snapshot should not contain "progress.reasoning"
    And the chart should still render on completion

  Scenario: The card renders reasoning in the chart slot during the wait
    Given a mounted card polling a planning snapshot with "progress.reasoning"
    When the card renders the planning state
    Then the chart slot should show a monospace reasoning block anchored to its tail
    And the heading should show the coarse phase label
    When the job completes
    Then the chart slot should show the chart image and no reasoning block
