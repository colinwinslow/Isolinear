Feature: Sandboxed code generation
  Advanced rendering can use generated matplotlib code only inside a constrained sandbox.

  Scenario: Sandbox policy is compatible with Raspberry Pi worker hardware
    Given codegen mode is enabled for the worker
    When the worker loads the default sandbox policy
    Then the policy should use an isolated Python subprocess
    And the policy should require a noninteractive rendering backend
    And the policy should enforce timeout, fixed output path, import allowlist, and output size limits
    And Linux workers should request CPU and memory limits where the platform supports them

  Scenario: Generated code renders through fixed entry point
    Given a valid chart spec
    And generated Python defines "render_chart(data, output_path)"
    When the worker runs codegen mode
    Then the code should run in the sandbox
    And the output image should be written only to the fixed output path
    And the render result should include metadata returned by the function

  Scenario: Allowlisted matplotlib code renders with Agg backend
    Given generated Python imports "matplotlib.pyplot"
    When the worker runs codegen mode
    Then the code should render a PNG through the sandbox
    And the render metadata should report the "Agg" backend
    And the output image should be written only to the fixed output path

  Scenario: Unsafe generated code is rejected before execution
    Given generated Python attempts to import "requests"
    When the worker performs static safety checks
    Then the worker should reject the code as "unsafe_code"
    And the code should not execute

  Scenario: Secret, filesystem, and network access fail closed
    Given generated Python attempts to read secrets, inspect environment variables, or open a local network socket
    When the worker performs sandbox safety checks
    Then the worker should reject the code as "unsafe_code"
    And the code should not execute

  Scenario: Oversized output fails after execution
    Given generated Python writes an output larger than the sandbox policy allows
    When the worker runs codegen mode
    Then the worker should return "output_too_large"
    And the render result should not expose the oversized image as a successful artifact

  Scenario: Runtime error triggers capped repair loop
    Given generated Python raises a matplotlib exception
    When codegen repair is enabled with max attempts 2
    Then the system should send the stack trace to the repair model
    And it should retry no more than 2 times
    And it should return a failure if all attempts fail
