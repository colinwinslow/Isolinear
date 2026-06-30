import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "worker"))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from isolinear_worker.codegen_sandbox import (  # noqa: E402
    default_codegen_sandbox_policy,
    invoke_codegen_sandbox,
    invoke_codegen_with_repair,
    static_safety_check,
)

from codegen_sandbox_fixtures import (  # noqa: E402
    PNG_SIGNATURE,
    broken_generated_python,
    matplotlib_generated_python,
    oversized_generated_python,
    safe_generated_python,
    sample_codegen_render_request,
    sandbox_can_import_matplotlib,
    unsafe_generated_python_examples,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    policy = default_codegen_sandbox_policy()
    output_root = REPO_ROOT / ".test-output"
    output_root.mkdir(exist_ok=True)

    print_case(
        "codegen_policy_is_pi_compatible",
        given={
            "run_timestamp": run_timestamp,
            "schema": "worker/isolinear_worker/schemas/codegen-sandbox-policy.schema.json",
        },
        when={"operation": "validate_default_codegen_sandbox_policy"},
        then={
            "execution_model": policy["execution_model"],
            "python_flags": policy["python_flags"],
            "network_access": policy["network_access"],
            "filesystem": policy["filesystem"],
            "environment": policy["environment"],
            "resource_limits": policy["resource_limits"],
            "timeout_seconds": policy["timeout_seconds"],
            "memory_limit_mb": policy["memory_limit_mb"],
            "allowed_imports": policy["allowed_imports"],
        },
    )

    # Safe sample: a real PNG through the fixed output path, no matplotlib needed.
    with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
        safe_result = invoke_codegen_sandbox(
            sample_codegen_render_request(python_code=safe_generated_python()),
            policy=policy,
            work_root=Path(run_directory),
        )
        safe_output_files = sorted(path.name for path in Path(run_directory).iterdir())
        safe_signature = Path(safe_result["image_path"]).read_bytes()[:8].hex()

    assert_true(safe_result["status"] == "success", f"safe render failed: {safe_result!r}")
    assert_true(safe_output_files == [safe_result["image_id"]], "safe render wrote stray files")
    assert_true(safe_signature == PNG_SIGNATURE.hex(), "safe render did not write a PNG")

    print_case(
        "fixed_entry_point_renders_fixed_output",
        given={"entry_point": "render_chart(data, output_path)", "render_mode": "codegen"},
        when={"operation": "invoke_codegen_sandbox"},
        then={"safe_result": safe_result, "safe_output_files": safe_output_files},
    )

    # Static safety denials (no execution).
    unsafe_results = {}
    for name, python_code in unsafe_generated_python_examples().items():
        unsafe_results[name] = static_safety_check(python_code, policy=policy)
    assert_true(
        all(not result["accepted"] for result in unsafe_results.values()),
        "an unsafe example was accepted",
    )
    assert_true(
        all(result["code"] == "unsafe_code" for result in unsafe_results.values()),
        "an unsafe example used the wrong code",
    )

    print_case(
        "unsafe_code_rejected_before_execution",
        given={"unsafe_examples": list(unsafe_results)},
        when={"operation": "run_static_safety_checks"},
        then={"unsafe_results": unsafe_results},
    )

    # Oversized output fails closed after execution.
    small_output_policy = {**policy, "max_output_bytes": 1024}
    with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
        oversized_result = invoke_codegen_sandbox(
            sample_codegen_render_request(python_code=oversized_generated_python(2048)),
            policy=small_output_policy,
            work_root=Path(run_directory),
        )
    assert_true(
        oversized_result["error"]["code"] == "output_too_large",
        f"oversized output not caught: {oversized_result!r}",
    )

    print_case(
        "output_size_limit_is_enforced",
        given={"max_output_bytes": 1024},
        when={"operation": "invoke_codegen_sandbox_with_oversized_output"},
        then={"oversized_result": oversized_result},
    )

    # Capped repair loop with an injected (non-model) repair callable.
    repair_calls = []

    def repair(previous_code, error):
        repair_calls.append(error["code"])
        return broken_generated_python(f"repair {len(repair_calls)} still fails")

    with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
        repair_result = invoke_codegen_with_repair(
            sample_codegen_render_request(python_code=broken_generated_python("initial failure")),
            repair=repair,
            max_attempts=2,
            work_root=Path(run_directory),
        )
    final_repair = repair_result["render_result"]
    assert_true(
        final_repair["error"]["code"] == "runtime_error",
        "repair loop did not end with runtime_error",
    )
    assert_true(len(repair_result["repair_requests"]) == 2, "repair loop did not retry twice")
    assert_true(
        repair_result["static_safety_checks_run"] == 3,
        "static checks were not rerun for every attempt",
    )

    print_case(
        "runtime_error_uses_capped_repair_loop",
        given={"max_attempts": repair_result["max_attempts"]},
        when={"operation": "invoke_codegen_with_repair"},
        then={
            "render_result": final_repair,
            "repair_requests": repair_result["repair_requests"],
            "static_safety_checks_run": repair_result["static_safety_checks_run"],
        },
    )

    # Allowlisted matplotlib.pyplot rendering: only runs where the `-I` sandbox
    # can import matplotlib (system site-packages); skipped on dev boxes where it
    # is only in the user site, which `-I` excludes.
    if sandbox_can_import_matplotlib():
        with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
            matplotlib_result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=matplotlib_generated_python()),
                policy=policy,
                work_root=Path(run_directory),
            )
            matplotlib_signature = (
                Path(matplotlib_result["image_path"]).read_bytes()[:8].hex()
                if matplotlib_result["status"] == "success"
                else None
            )
        assert_true(
            matplotlib_result["status"] == "success",
            f"matplotlib render failed: {matplotlib_result!r}",
        )
        assert_true(
            matplotlib_signature == PNG_SIGNATURE.hex(), "matplotlib render did not write a PNG"
        )
        print_case(
            "matplotlib_pyplot_renders_with_agg_backend",
            given={"allowed_imports": ["matplotlib", "matplotlib.pyplot"], "backend": "Agg"},
            when={"operation": "invoke_codegen_sandbox_with_matplotlib_pyplot"},
            then={
                "matplotlib_result": matplotlib_result,
                "matplotlib_image_signature": matplotlib_signature,
            },
        )
    else:
        print_case(
            "matplotlib_pyplot_renders_with_agg_backend",
            given={"allowed_imports": ["matplotlib", "matplotlib.pyplot"], "backend": "Agg"},
            when={"operation": "invoke_codegen_sandbox_with_matplotlib_pyplot"},
            then={
                "skipped": True,
                "reason": "sandbox `python -I` cannot import matplotlib in this environment",
            },
        )

    print("PASS codegen_sandbox")


if __name__ == "__main__":
    main()
