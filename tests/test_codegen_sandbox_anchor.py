import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.codegen_sandbox_anchor import (  # noqa: E402
    PNG_SIGNATURE,
    broken_generated_python,
    default_codegen_sandbox_policy,
    invoke_codegen_sandbox,
    invoke_codegen_with_repair,
    matplotlib_arbitrary_read_python,
    matplotlib_generated_python,
    oversized_generated_python,
    sample_codegen_render_request,
    safe_generated_python,
    static_safety_check,
    unsafe_generated_python_examples,
    verify_codegen_sandbox_anchor,
)
from Isolinear.contracts import validate_contract  # noqa: E402


class CodegenSandboxAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (REPO_ROOT / ".test-output").mkdir(exist_ok=True)

    def test_default_policy_documents_raspberry_pi_compatible_constraints(self):
        policy = default_codegen_sandbox_policy()

        validate_contract("codegen-sandbox-policy", policy, repo_root=REPO_ROOT)
        self.assertEqual(policy["execution_model"], "isolated_subprocess")
        self.assertEqual(policy["entry_point"], "render_chart")
        self.assertEqual(policy["entry_point_args"], ["data", "output_path"])
        self.assertEqual(policy["network_access"], "denied")
        self.assertEqual(policy["filesystem"]["write_policy"], "fixed_output_path_only")
        self.assertFalse(policy["environment"]["inherit_parent_environment"])
        self.assertLessEqual(policy["memory_limit_mb"], 256)
        self.assertIn("-I", policy["python_flags"])
        self.assertIn("matplotlib.pyplot", policy["allowed_imports"])

    def test_safe_generated_code_runs_through_fixed_entry_point(self):
        render_request = sample_codegen_render_request(python_code=safe_generated_python())

        with tempfile.TemporaryDirectory(dir=REPO_ROOT / ".test-output") as run_directory:
            result = invoke_codegen_sandbox(
                render_request=render_request,
                output_directory=Path(run_directory),
                repo_root=REPO_ROOT,
            )
            output_files = sorted(path.name for path in Path(run_directory).iterdir())
            image_path = Path(result["image_path"])
            image_bytes = image_path.read_bytes()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["image_id"], "codegen-sandbox-anchor.png")
        self.assertEqual(output_files, ["codegen-sandbox-anchor.png"])
        self.assertEqual(image_bytes[:8], PNG_SIGNATURE)
        self.assertEqual(result["render_metadata"]["title"], "Sandboxed Temperature")
        self.assertEqual(result["render_metadata"]["series_plotted"], ["upstairs_temperature"])
        self.assertEqual(result["render_metadata"]["codegen_attempts"], 1)
        validate_contract("render-result", result, repo_root=REPO_ROOT)

    def test_allowlisted_matplotlib_pyplot_code_renders_png_in_sandbox(self):
        render_request = sample_codegen_render_request(
            python_code=matplotlib_generated_python(),
        )

        with tempfile.TemporaryDirectory(dir=REPO_ROOT / ".test-output") as run_directory:
            result = invoke_codegen_sandbox(
                render_request=render_request,
                output_directory=Path(run_directory),
                repo_root=REPO_ROOT,
            )
            output_files = sorted(path.name for path in Path(run_directory).iterdir())
            image_path = Path(result["image_path"])
            image_bytes = image_path.read_bytes()

        self.assertEqual(result["status"], "success")
        self.assertEqual(output_files, ["codegen-sandbox-anchor.png"])
        self.assertEqual(image_bytes[:8], PNG_SIGNATURE)
        self.assertEqual(result["render_metadata"]["series_plotted"], ["upstairs_temperature"])
        self.assertIn(
            "matplotlib_backend:Agg",
            result["render_metadata"]["warnings"],
        )
        validate_contract("render-result", result, repo_root=REPO_ROOT)

    def test_allowlisted_matplotlib_pyplot_cannot_read_arbitrary_files(self):
        forbidden_path = (REPO_ROOT / "STATUS.md").resolve()
        python_code = matplotlib_arbitrary_read_python(forbidden_path)

        safety_result = static_safety_check(python_code)
        self.assertTrue(safety_result["accepted"], safety_result["violations"])

        with tempfile.TemporaryDirectory(dir=REPO_ROOT / ".test-output") as run_directory:
            result = invoke_codegen_sandbox(
                render_request=sample_codegen_render_request(python_code=python_code),
                output_directory=Path(run_directory),
                repo_root=REPO_ROOT,
            )
            self.assertEqual(list(Path(run_directory).iterdir()), [])

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "runtime_error")
        self.assertEqual(result["render_metadata"]["codegen_attempts"], 1)
        self.assertIn(
            "sandbox allows reads only from worker runtime roots",
            result["error"]["message"],
        )
        validate_contract("render-result", result, repo_root=REPO_ROOT)

    def test_unsafe_import_file_network_and_environment_paths_fail_before_execution(self):
        for name, python_code in unsafe_generated_python_examples().items():
            with self.subTest(name=name):
                safety_result = static_safety_check(python_code)
                self.assertFalse(safety_result["accepted"])
                self.assertEqual(safety_result["code"], "unsafe_code")

                with tempfile.TemporaryDirectory(dir=REPO_ROOT / ".test-output") as run_directory:
                    result = invoke_codegen_sandbox(
                        render_request=sample_codegen_render_request(python_code=python_code),
                        output_directory=Path(run_directory),
                        repo_root=REPO_ROOT,
                    )
                    self.assertEqual(list(Path(run_directory).iterdir()), [])

                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["error"]["code"], "unsafe_code")
                self.assertFalse(result["error"]["details"]["render_attempted"])
                self.assertEqual(result["render_metadata"]["codegen_attempts"], 0)
                validate_contract("render-result", result, repo_root=REPO_ROOT)

    def test_missing_or_wrong_entry_point_is_rejected(self):
        python_code = """
def draw_chart(data, output_path):
    return {}
""".strip()

        result = static_safety_check(python_code)

        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "unsafe_code")
        self.assertEqual(
            result["violations"][0]["code"],
            "missing_fixed_entry_point",
        )

    def test_non_allowlisted_matplotlib_submodule_import_is_rejected(self):
        python_code = """
from matplotlib import backends


def render_chart(data, output_path):
    return {"warnings": [str(backends)]}
""".strip()

        safety_result = static_safety_check(python_code)
        self.assertFalse(safety_result["accepted"])
        self.assertEqual(safety_result["code"], "unsafe_code")
        self.assertEqual(safety_result["violations"][0]["module"], "matplotlib.backends")

        with tempfile.TemporaryDirectory(dir=REPO_ROOT / ".test-output") as run_directory:
            result = invoke_codegen_sandbox(
                render_request=sample_codegen_render_request(python_code=python_code),
                output_directory=Path(run_directory),
                repo_root=REPO_ROOT,
            )
            self.assertEqual(list(Path(run_directory).iterdir()), [])

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "unsafe_code")
        self.assertFalse(result["error"]["details"]["render_attempted"])

    def test_oversized_output_fails_after_sandbox_execution(self):
        policy = {**default_codegen_sandbox_policy(), "max_output_bytes": 1024}

        with tempfile.TemporaryDirectory(dir=REPO_ROOT / ".test-output") as run_directory:
            result = invoke_codegen_sandbox(
                render_request=sample_codegen_render_request(
                    python_code=oversized_generated_python(extra_bytes=2048),
                ),
                output_directory=Path(run_directory),
                policy=policy,
                repo_root=REPO_ROOT,
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "output_too_large")
        self.assertEqual(result["render_metadata"]["codegen_attempts"], 1)
        self.assertEqual(result["error"]["details"]["max_output_bytes"], 1024)
        validate_contract("render-result", result, repo_root=REPO_ROOT)

    def test_runtime_error_triggers_capped_repair_loop(self):
        render_request = sample_codegen_render_request(
            python_code=broken_generated_python("initial matplotlib error"),
            max_repair_attempts=2,
        )

        with tempfile.TemporaryDirectory(dir=REPO_ROOT / ".test-output") as run_directory:
            result = invoke_codegen_with_repair(
                render_request=render_request,
                output_directory=Path(run_directory),
                repaired_python_codes=[
                    broken_generated_python("first repair failed"),
                    broken_generated_python("second repair failed"),
                ],
                repo_root=REPO_ROOT,
            )

        final_result = result["render_result"]
        self.assertEqual(final_result["status"], "failed")
        self.assertEqual(final_result["error"]["code"], "runtime_error")
        self.assertEqual(final_result["render_metadata"]["codegen_attempts"], 3)
        self.assertEqual(result["max_repair_attempts"], 2)
        self.assertEqual(len(result["repair_requests"]), 2)
        self.assertTrue(all(item["stack_trace_included"] for item in result["repair_requests"]))
        self.assertEqual(result["static_safety_checks_run"], 3)
        self.assertEqual(
            final_result["error"]["details"]["repair_attempts"],
            2,
        )
        validate_contract("render-result", final_result, repo_root=REPO_ROOT)

    def test_codegen_sandbox_anchor_verification_passes(self):
        result = verify_codegen_sandbox_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
