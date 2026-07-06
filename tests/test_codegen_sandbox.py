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
    _coerce_claims,
    _normalize_render_metadata,
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
        self.assertEqual(policy["memory_limit_mb"], 1024)
        self.assertIn("-I", policy["python_flags"])
        self.assertIn("matplotlib.pyplot", policy["allowed_imports"])
        self.assertIn("pandas", policy["allowed_imports"])
        # ADR-0031 D6: the analysis libraries, exact-match alongside numpy/pandas.
        self.assertIn("scipy", policy["allowed_imports"])
        self.assertIn("scipy.stats", policy["allowed_imports"])
        self.assertIn("scipy.signal", policy["allowed_imports"])
        self.assertIn("scipy.optimize", policy["allowed_imports"])
        self.assertIn("seaborn", policy["allowed_imports"])
        # Pure-plotting matplotlib submodules, exact-match like matplotlib.dates.
        # The ADR-0033 legend hint ("e.g. a Patch") steers models to
        # `import matplotlib.patches`; without these entries every such
        # generation burned a repair attempt on import_not_allowlisted.
        self.assertIn("matplotlib.patches", policy["allowed_imports"])
        self.assertIn("matplotlib.lines", policy["allowed_imports"])
        self.assertIn("matplotlib.ticker", policy["allowed_imports"])
        self.assertIn("matplotlib.colors", policy["allowed_imports"])

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

    def test_violations_carry_the_offending_source_line(self):
        # Every line-numbered violation is decorated with source_line — the exact
        # offending text from the code — so a repairing model acts on the line
        # without having to count. Generic across violation classes.

        # 1. syntax_error: a bare non-ASCII token (the live 0.2.12 fallback).
        syntax = (
            "def render_chart(data, output_path):\n"
            "    ax.set_ylabel(Temperature °F)\n"
        )
        result = static_safety_check(syntax)
        self.assertEqual(result["code"], "invalid_code")
        violation = result["violations"][0]
        self.assertEqual(violation["code"], "syntax_error")
        self.assertEqual(violation["source_line"], "ax.set_ylabel(Temperature °F)")

        # 2. unsafe_code: the source_line names the disallowed construct in place.
        forbidden = (
            "from os import getcwd\n\n\n"
            "def render_chart(data, output_path):\n"
            "    return {\"warnings\": [getcwd()]}"
        )
        result = static_safety_check(forbidden)
        self.assertEqual(result["code"], "unsafe_code")
        self.assertEqual(result["violations"][0]["source_line"], "from os import getcwd")

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

    def test_from_import_of_allowed_module_cannot_reach_forbidden_toplevel(self):
        # `from matplotlib import os` is accepted (base module `matplotlib` is
        # allowlisted; `matplotlib.os` is not forbidden), and that is SAFE because
        # CPython resolves a fromlist item only as an attribute/submodule of the
        # base package — it never imports the top-level stdlib `os`.
        code = (
            "from matplotlib import os\n\n\n"
            "def render_chart(data, output_path):\n"
            "    return {\"warnings\": []}"
        )
        self.assertTrue(static_safety_check(code)["accepted"])
        # Prove the CPython fromlist semantics the safety argument relies on: a
        # `from <module> import <name>` where <name> is not an attribute/submodule
        # of <module> raises ImportError — it never falls back to a top-level
        # module, so the forbidden stdlib `subprocess` is unreachable this way.
        with self.assertRaises(ImportError):
            exec("from json import subprocess", {})

    def test_safe_builtins_and_from_import_execute_in_sandbox(self):
        # `next`/`iter`/`map`/`filter`/`set` and a from-import of an allowlisted
        # stdlib module all run inside the `-I` sandbox, writing a real PNG
        # through the fixed output path (no matplotlib needed → runs everywhere).
        code = (
            "from datetime import datetime\n"
            "def render_chart(data, output_path):\n"
            "    picked = next(iter([1, 2, 3]))\n"
            "    labels = set(map(str, filter(lambda x: x >= picked, [1, 2, 3])))\n"
            "    _ = datetime(2026, 1, 1)\n"
            "    png = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6360000002000100ffff03000006000557bfab0000000049454e44ae426082')\n"
            "    with open(output_path, 'wb') as handle:\n"
            "        handle.write(png)\n"
            "    return {'title': 't', 'series_plotted': sorted(labels), 'warnings': []}\n"
        )
        with self._run_dir() as run_directory:
            result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=code),
                work_root=Path(run_directory),
            )
        self.assertEqual(result["status"], "success", result.get("error"))

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


class RenderMetadataCoercionTests(unittest.TestCase):
    """The generated code authors render_metadata freely; every model-supplied
    field must be coerced to its contract type so an off-type value degrades
    inside the normal result flow instead of failing the worker's own response
    validation (observed live: a dict warnings entry -> unhandled
    ContractValidationError -> HTTP 500 -> the integration treats it as an
    unrepairable transport fault and falls back to Pillow with zero repairs)."""

    def _request(self):
        return sample_codegen_render_request()

    def _success_envelope(self, metadata):
        return {
            "request_id": "req-meta",
            "status": "success",
            "image_id": "img-1",
            "image_mime_type": "image/png",
            "image_path": "/tmp/img.png",
            "error": None,
            "render_metadata": metadata,
        }

    def test_off_type_model_metadata_is_coerced_to_contract(self):
        request = self._request()
        chart_title = request["chart_spec"].get("title")
        first_ts = request["history_series"][0]["points"][0].get("ts")
        metadata = _normalize_render_metadata(
            {
                "title": {"unexpected": "dict"},
                "series_plotted": "not-a-list",
                "overlays_plotted": [{"overlay": 1}],
                "warnings": [{"detail": "non-string entry"}, "plain warning", 7],
                "x_min": 1751500800000,
                "x_max": None,
            },
            render_request=request,
            codegen_attempts=1,
        )

        self.assertEqual(metadata["title"], chart_title)
        self.assertEqual(metadata["series_plotted"], [])
        self.assertTrue(all(isinstance(w, str) for w in metadata["warnings"]))
        self.assertEqual(len(metadata["warnings"]), 3)
        self.assertTrue(all(isinstance(o, str) for o in metadata["overlays_plotted"]))
        self.assertEqual(metadata["x_min"], first_ts)
        # The full success envelope must validate — the exact check whose
        # unhandled failure was the live 500.
        validate_contract("render-result", self._success_envelope(metadata))

    def test_malformed_claims_degrade_softly_never_break_the_contract(self):
        request = self._request()
        metadata = _normalize_render_metadata(
            {
                "warnings": [],
                "claims": [
                    {"metric": "mean", "inputs": ["sensor.a"], "value": 71.5,
                     "verdict": "Yes", "rule": {"bands": [[0.3, "Yes"], [None, "No"]],
                                                "basis": "value"}},
                    # Stringified numeric value (measured live, 8th-session
                    # benchmark): plainly numeric -> converted.
                    {"metric": "delta", "inputs": ["sensor.a"], "value": "3.5"},
                    # Unit-bearing string can't be honestly recovered -> dropped.
                    {"metric": "delta", "inputs": ["sensor.a"], "value": "3.0°F"},
                    # Structural garbage -> dropped.
                    "not-a-dict",
                    {"inputs": ["sensor.a"], "value": 1.0},
                    # Off-type optional fields are removed, claim kept.
                    {"metric": "mean", "inputs": "sensor.a", "value": 2,
                     "verdict": 5, "rule": "not-a-dict"},
                ],
            },
            render_request=request,
            codegen_attempts=1,
        )

        claims = metadata["claims"]
        self.assertEqual(len(claims), 3)
        self.assertEqual(claims[1]["value"], 3.5)
        self.assertNotIn("verdict", claims[2])
        self.assertNotIn("rule", claims[2])
        self.assertEqual(claims[2]["inputs"], [])
        validate_contract("render-result", self._success_envelope(metadata))

    def test_coerce_claims_non_list_is_absent(self):
        self.assertIsNone(_coerce_claims("not-a-list"))
        self.assertIsNone(_coerce_claims(None))
        metadata = _normalize_render_metadata(
            {"claims": {"metric": "mean"}}, render_request=self._request(), codegen_attempts=0
        )
        self.assertNotIn("claims", metadata)


if __name__ == "__main__":
    unittest.main(verbosity=2)
