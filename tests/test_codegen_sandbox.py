"""Real tests for the promoted codegen sandbox worker module (ADR-0029 packet 1).

Drives `isolinear_worker.codegen_sandbox` entirely through its public API and
proves parity with the accepted sandbox-codegen BDD (scenarios A-G) plus the
promotion scenarios (self-containment, timeout, injected-repair callable).

Environment note: the sandbox runs generated code under `python -I` (isolated
mode), which excludes user site-packages. Scenarios that need matplotlib *inside*
the sandbox are skipped when the `-I` subprocess cannot import matplotlib (true
on a dev box where matplotlib is only in the user site); they run on a worker
container where matplotlib is in the system site-packages. The non-matplotlib
paths — including a real PNG written through the fixed output path — always run.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = REPO_ROOT / "worker"
sys.path.insert(0, str(WORKER_DIR))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from isolinear_worker.codegen_sandbox import (  # noqa: E402
    default_codegen_sandbox_policy,
    invoke_codegen_sandbox,
    invoke_codegen_with_repair,
    static_safety_check,
)
from isolinear_worker._schema_validation import validate_contract  # noqa: E402

from codegen_sandbox_fixtures import (  # noqa: E402
    PNG_SIGNATURE,
    broken_generated_python,
    matplotlib_arbitrary_read_python,
    matplotlib_generated_python,
    oversized_generated_python,
    safe_generated_python,
    sample_codegen_render_request,
    sandbox_can_import_matplotlib,
    timeout_generated_python,
    unsafe_generated_python_examples,
)


_SANDBOX_HAS_MATPLOTLIB = sandbox_can_import_matplotlib()
_NO_MATPLOTLIB_REASON = (
    "sandbox `python -I` cannot import matplotlib in this environment "
    "(user-site install excluded by isolated mode); runs on a worker container"
)


class CodegenSandboxModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (REPO_ROOT / ".test-output").mkdir(exist_ok=True)

    def _run_dir(self):
        return tempfile.TemporaryDirectory(dir=REPO_ROOT / ".test-output")

    # Scenario A — policy is Raspberry-Pi compatible and schema-valid.
    def test_default_policy_is_pi_compatible_and_schema_valid(self):
        policy = default_codegen_sandbox_policy()

        validate_contract("codegen-sandbox-policy", policy)
        self.assertEqual(policy["execution_model"], "isolated_subprocess")
        self.assertEqual(policy["entry_point"], "render_chart")
        self.assertEqual(policy["entry_point_args"], ["data", "output_path"])
        self.assertEqual(policy["network_access"], "denied")
        self.assertEqual(policy["filesystem"]["write_policy"], "fixed_output_path_only")
        self.assertFalse(policy["environment"]["inherit_parent_environment"])
        self.assertLessEqual(policy["memory_limit_mb"], 256)
        self.assertIn("-I", policy["python_flags"])
        self.assertIn("matplotlib.pyplot", policy["allowed_imports"])

    # Scenario B (sandbox-codegen) — safe code renders a real PNG through the
    # fixed output path, with no matplotlib dependency.
    def test_safe_code_writes_real_png_through_fixed_output_path(self):
        with self._run_dir() as run_directory:
            result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=safe_generated_python()),
                work_root=Path(run_directory),
            )
            output_files = sorted(path.name for path in Path(run_directory).iterdir())
            image_bytes = Path(result["image_path"]).read_bytes()

        self.assertEqual(result["status"], "success", result.get("error"))
        self.assertEqual(result["image_id"], "codegen-sandbox-anchor.png")
        self.assertEqual(output_files, ["codegen-sandbox-anchor.png"])
        self.assertEqual(image_bytes[:8], PNG_SIGNATURE)
        self.assertEqual(result["render_metadata"]["title"], "Sandboxed Temperature")
        self.assertEqual(result["render_metadata"]["series_plotted"], ["upstairs_temperature"])
        self.assertEqual(result["render_metadata"]["codegen_attempts"], 1)
        validate_contract("render-result", result)

    # Scenario C (sandbox-codegen) — allowlisted matplotlib.pyplot renders a PNG
    # with the Agg backend reported.
    @unittest.skipUnless(_SANDBOX_HAS_MATPLOTLIB, _NO_MATPLOTLIB_REASON)
    def test_matplotlib_pyplot_renders_png_with_agg_backend(self):
        with self._run_dir() as run_directory:
            result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=matplotlib_generated_python()),
                work_root=Path(run_directory),
            )
            output_files = sorted(path.name for path in Path(run_directory).iterdir())
            image_bytes = Path(result["image_path"]).read_bytes()

        self.assertEqual(result["status"], "success", result.get("error"))
        self.assertEqual(output_files, ["codegen-sandbox-anchor.png"])
        self.assertEqual(image_bytes[:8], PNG_SIGNATURE)
        self.assertEqual(result["render_metadata"]["series_plotted"], ["upstairs_temperature"])
        self.assertIn("matplotlib_backend:Agg", result["render_metadata"]["warnings"])
        validate_contract("render-result", result)

    # Scenario D (sandbox-codegen) — unsafe code is rejected statically, before
    # any execution, with the inherited `unsafe_code` code.
    def test_unsafe_code_is_rejected_before_execution(self):
        for name, python_code in unsafe_generated_python_examples().items():
            with self.subTest(name=name):
                safety_result = static_safety_check(python_code)
                self.assertFalse(safety_result["accepted"])
                self.assertEqual(safety_result["code"], "unsafe_code")

                with self._run_dir() as run_directory:
                    result = invoke_codegen_sandbox(
                        sample_codegen_render_request(python_code=python_code),
                        work_root=Path(run_directory),
                    )
                    self.assertEqual(list(Path(run_directory).iterdir()), [])

                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["error"]["code"], "unsafe_code")
                self.assertFalse(result["error"]["details"]["render_attempted"])
                self.assertEqual(result["render_metadata"]["codegen_attempts"], 0)
                validate_contract("render-result", result)

    def test_missing_entry_point_and_forbidden_from_import_are_unsafe(self):
        missing_entry = "def draw_chart(data, output_path):\n    return {}"
        result = static_safety_check(missing_entry)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["violations"][0]["code"], "missing_fixed_entry_point")

        # A from-import whose module is forbidden is still rejected: the module
        # named after `from` is what actually executes.
        forbidden = (
            "from os import getcwd\n\n\n"
            "def render_chart(data, output_path):\n"
            "    return {\"warnings\": [getcwd()]}"
        )
        result = static_safety_check(forbidden)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "unsafe_code")
        self.assertEqual(result["violations"][0]["module"], "os")

    def test_from_imports_of_allowlisted_modules_are_accepted(self):
        # A from-import that targets an allowlisted module is accepted, whether
        # the imported name is a class/attribute (`datetime.datetime`) or a
        # submodule of a trusted package (`matplotlib.backends`). The check keys
        # on the module named after `from`, not the constructed qualified name.
        for snippet in (
            "from datetime import datetime",
            "from matplotlib import pyplot, backends",
            "from json import loads",
            "from statistics import mean",
        ):
            code = (
                f"{snippet}\n\n\n"
                "def render_chart(data, output_path):\n"
                "    return {\"warnings\": []}"
            )
            with self.subTest(snippet=snippet):
                result = static_safety_check(code)
                self.assertTrue(result["accepted"], result.get("violations"))

        # Still-forbidden forms remain rejected.
        for snippet in ("import os", "from os import path", "from os.path import join"):
            code = (
                f"{snippet}\n\n\n"
                "def render_chart(data, output_path):\n"
                "    return {\"warnings\": []}"
            )
            with self.subTest(snippet=snippet):
                result = static_safety_check(code)
                self.assertFalse(result["accepted"])
                self.assertEqual(result["code"], "unsafe_code")

    # Scenario E (sandbox-codegen) — an arbitrary file read routed through an
    # allowlisted rendering library is denied at runtime by the audit hook.
    @unittest.skipUnless(_SANDBOX_HAS_MATPLOTLIB, _NO_MATPLOTLIB_REASON)
    def test_matplotlib_arbitrary_read_is_denied_by_audit_hook(self):
        forbidden_path = (REPO_ROOT / "STATUS.md").resolve()
        python_code = matplotlib_arbitrary_read_python(forbidden_path)

        # The read is not statically detectable — it passes the static gate and
        # must be stopped at runtime.
        self.assertTrue(static_safety_check(python_code)["accepted"])

        with self._run_dir() as run_directory:
            result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=python_code),
                work_root=Path(run_directory),
            )
            self.assertEqual(list(Path(run_directory).iterdir()), [])

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "runtime_error")
        self.assertIn(
            "sandbox allows reads only from worker runtime roots",
            result["error"]["message"],
        )
        validate_contract("render-result", result)

    # Scenario F (sandbox-codegen) — oversized output fails closed after
    # execution with `output_too_large`.
    def test_oversized_output_fails_closed(self):
        policy = {**default_codegen_sandbox_policy(), "max_output_bytes": 1024}

        with self._run_dir() as run_directory:
            result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=oversized_generated_python(2048)),
                policy=policy,
                work_root=Path(run_directory),
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "output_too_large")
        self.assertEqual(result["error"]["details"]["max_output_bytes"], 1024)
        self.assertEqual(result["render_metadata"]["codegen_attempts"], 1)
        validate_contract("render-result", result)

    # Promotion Scenario D — runaway code fails closed with `timeout`.
    def test_runaway_code_times_out(self):
        policy = {**default_codegen_sandbox_policy(), "timeout_seconds": 1, "cpu_seconds": 30}

        with self._run_dir() as run_directory:
            result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=timeout_generated_python()),
                policy=policy,
                work_root=Path(run_directory),
            )
            self.assertEqual(list(Path(run_directory).iterdir()), [])

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "timeout")
        validate_contract("render-result", result)

    # Scenario G / Promotion Scenario E — capped repair loop with an injected
    # (non-model) repair callable that keeps failing.
    def test_capped_repair_loop_exhausts_with_injected_repair(self):
        repair_calls = []

        def repair(previous_code, error):
            repair_calls.append(error["code"])
            return broken_generated_python(f"repair {len(repair_calls)} still fails")

        with self._run_dir() as run_directory:
            outcome = invoke_codegen_with_repair(
                sample_codegen_render_request(python_code=broken_generated_python("initial")),
                repair=repair,
                max_attempts=2,
                work_root=Path(run_directory),
            )

        final_result = outcome["render_result"]
        self.assertEqual(final_result["status"], "failed")
        self.assertEqual(final_result["error"]["code"], "runtime_error")
        self.assertEqual(final_result["render_metadata"]["codegen_attempts"], 3)
        self.assertEqual(outcome["max_attempts"], 2)
        self.assertEqual(len(outcome["repair_requests"]), 2)
        self.assertEqual(len(repair_calls), 2)  # retries no more than max_attempts
        self.assertTrue(all(item["stack_trace_included"] for item in outcome["repair_requests"]))
        self.assertEqual(outcome["static_safety_checks_run"], 3)
        self.assertEqual(final_result["error"]["details"]["repair_attempts"], 2)
        validate_contract("render-result", final_result)

    # Promotion Scenario E — repair that fixes the code stops the loop early and
    # re-runs the static safety check for the repaired attempt.
    def test_repair_loop_stops_when_a_repair_succeeds(self):
        def repair(previous_code, error):
            return safe_generated_python()

        with self._run_dir() as run_directory:
            outcome = invoke_codegen_with_repair(
                sample_codegen_render_request(python_code=broken_generated_python("initial")),
                repair=repair,
                max_attempts=2,
                work_root=Path(run_directory),
            )

        self.assertEqual(outcome["render_result"]["status"], "success")
        self.assertEqual(outcome["render_result"]["render_metadata"]["codegen_attempts"], 2)
        self.assertEqual(len(outcome["repair_requests"]), 1)
        self.assertEqual(outcome["static_safety_checks_run"], 2)

    # Drift guard — the schemas bundled into the worker package are a deliberate
    # copy (the worker must not read docs/schemas/ at deploy time). Keep the two
    # sources of truth byte-identical so the copy cannot silently drift.
    def test_bundled_worker_schemas_match_canonical_docs_schemas(self):
        bundled_dir = WORKER_DIR / "isolinear_worker" / "schemas"
        canonical_dir = REPO_ROOT / "docs" / "schemas"
        bundled_names = sorted(path.name for path in bundled_dir.glob("*.schema.json"))
        self.assertTrue(bundled_names, "no bundled worker schemas found")
        for name in bundled_names:
            with self.subTest(schema=name):
                self.assertEqual(
                    (bundled_dir / name).read_bytes(),
                    (canonical_dir / name).read_bytes(),
                    f"{name} drifted from docs/schemas/{name}",
                )

    # Promotion Scenario B — the worker module is self-contained: importing it
    # pulls in nothing from custom_components/isolinear or src/Isolinear, and it
    # validates against a schema bundled inside the worker package.
    def test_worker_module_is_self_contained(self):
        bundled_schema = WORKER_DIR / "isolinear_worker" / "schemas" / "codegen-sandbox-policy.schema.json"
        self.assertTrue(bundled_schema.is_file())

        probe = (
            "import sys, json\n"
            "import isolinear_worker.codegen_sandbox as m\n"
            "from isolinear_worker import _schema_validation as v\n"
            "leaked = sorted(\n"
            "    name for name in sys.modules\n"
            "    if name == 'Isolinear' or name.startswith('Isolinear.')\n"
            "    or name.startswith('src.') or name.startswith('custom_components')\n"
            ")\n"
            "print(json.dumps({\n"
            "    'leaked': leaked,\n"
            "    'validator_file': v.__file__,\n"
            "    'module_file': m.__file__,\n"
            "}))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=str(WORKER_DIR),  # makes `isolinear_worker` importable; src/ is NOT on the path
            env={"PATH": "/usr/bin:/bin", "HOME": str(REPO_ROOT / ".test-output")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["leaked"], [])
        self.assertIn(str(WORKER_DIR), payload["validator_file"])
        self.assertIn(str(WORKER_DIR), payload["module_file"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
