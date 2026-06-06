import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.codegen_sandbox_anchor import verify_codegen_sandbox_anchor  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_codegen_sandbox_anchor(REPO_ROOT)

    assert_true(result["passed"], f"Sandbox anchor verification failed: {result['failures']!r}")

    print_case(
        "codegen_policy_is_pi_compatible",
        given={
            "run_timestamp": run_timestamp,
            "schema": "docs/schemas/codegen-sandbox-policy.schema.json",
        },
        when={
            "operation": "validate_default_codegen_sandbox_policy",
        },
        then={
            "execution_model": result["policy"]["execution_model"],
            "python_flags": result["policy"]["python_flags"],
            "network_access": result["policy"]["network_access"],
            "filesystem": result["policy"]["filesystem"],
            "environment": result["policy"]["environment"],
            "resource_limits": result["policy"]["resource_limits"],
            "timeout_seconds": result["policy"]["timeout_seconds"],
            "memory_limit_mb": result["policy"]["memory_limit_mb"],
            "allowed_imports": result["policy"]["allowed_imports"],
        },
    )

    print_case(
        "fixed_entry_point_renders_fixed_output",
        given={
            "entry_point": "render_chart(data, output_path)",
            "render_mode": "codegen",
        },
        when={
            "operation": "invoke_codegen_sandbox",
        },
        then={
            "safe_result": result["safe_result"],
            "safe_output_files": result["safe_output_files"],
        },
    )

    print_case(
        "matplotlib_pyplot_renders_with_agg_backend",
        given={
            "allowed_imports": [
                "matplotlib",
                "matplotlib.pyplot",
            ],
            "backend": "Agg",
        },
        when={
            "operation": "invoke_codegen_sandbox_with_matplotlib_pyplot",
        },
        then={
            "matplotlib_result": result["matplotlib_result"],
            "matplotlib_output_files": result["matplotlib_output_files"],
            "matplotlib_image_signature": result["matplotlib_image_signature"],
        },
    )

    print_case(
        "unsafe_code_rejected_before_execution",
        given={
            "unsafe_examples": list(result["unsafe_results"]),
        },
        when={
            "operation": "run_static_safety_checks",
        },
        then={
            "unsafe_results": result["unsafe_results"],
        },
    )

    print_case(
        "output_size_limit_is_enforced",
        given={
            "max_output_bytes": 1024,
        },
        when={
            "operation": "invoke_codegen_sandbox_with_oversized_output",
        },
        then={
            "oversized_result": result["oversized_result"],
        },
    )

    print_case(
        "runtime_error_uses_capped_repair_loop",
        given={
            "max_repair_attempts": result["repair_result"]["max_repair_attempts"],
        },
        when={
            "operation": "invoke_codegen_with_repair",
        },
        then={
            "render_result": result["repair_result"]["render_result"],
            "repair_requests": result["repair_result"]["repair_requests"],
            "static_safety_checks_run": result["repair_result"]["static_safety_checks_run"],
        },
    )

    print("PASS codegen_sandbox")


if __name__ == "__main__":
    main()
