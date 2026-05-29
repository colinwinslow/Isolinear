Feature: Sandboxed code generation
  Advanced rendering can use generated matplotlib code only inside a constrained sandbox.

  Scenario: Generated code renders through fixed entry point
    Given a valid chart spec
    And generated Python defines "render_chart(data, output_path)"
    When the worker runs codegen mode
    Then the code should run in the sandbox
    And the output image should be written only to the fixed output path
    And the render result should include metadata returned by the function

  Scenario: Unsafe generated code is rejected before execution
    Given generated Python attempts to import "requests"
    When the worker performs static safety checks
    Then the worker should reject the code as "unsafe_code"
    And the code should not execute

  Scenario: Runtime error triggers capped repair loop
    Given generated Python raises a matplotlib exception
    When codegen repair is enabled with max attempts 2
    Then the system should send the stack trace to the repair model
    And it should retry no more than 2 times
    And it should return a failure if all attempts fail
