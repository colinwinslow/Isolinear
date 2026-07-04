"""Repair prompt must surface static-check violations (unsafe_code).

Regression for a live-diagnosed bug (2026-07-04): a codegen render that failed
the sandbox's static safety check (`unsafe_code`) fell back to Pillow on every
attempt no matter how high `max_codegen_repair_attempts` was set. Root cause:
`_sandbox_error_view` fed the repair prompt only `code`/`message`/`traceback`,
and an `unsafe_code` failure has NO traceback — its specifics live in
`details.violations`, which was dropped. The model repaired blind and could
never clear the gate. The view now carries `violations`, and the repair prompt
tells the model to remove/replace each one.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear import model_provider  # noqa: E402
from custom_components.isolinear.model_provider import (  # noqa: E402
    OllamaCompatiblePlannerClient,
)

UNSAFE_ERROR = {
    "code": "unsafe_code",
    "message": "Generated code failed static sandbox safety checks.",
    "details": {
        "render_attempted": False,
        "violations": [
            {"code": "forbidden_import", "message": "os is not allowlisted", "line": 3},
            {"code": "dunder_attribute", "message": "dunder access", "line": 7},
        ],
    },
}

RUNTIME_ERROR = {
    "code": "runtime_error",
    "message": "boom",
    "details": {"traceback": "Traceback (most recent call last): ..."},
}


class SandboxErrorViewTests(unittest.TestCase):
    def test_unsafe_code_view_surfaces_the_violations(self) -> None:
        view = model_provider._sandbox_error_view(UNSAFE_ERROR)
        self.assertEqual(view["code"], "unsafe_code")
        self.assertIn("violations", view)
        self.assertEqual([v["code"] for v in view["violations"]],
                         ["forbidden_import", "dunder_attribute"])
        self.assertEqual(view["violations"][0]["line"], 3)

    def test_runtime_view_keeps_traceback_and_omits_violations(self) -> None:
        view = model_provider._sandbox_error_view(RUNTIME_ERROR)
        self.assertEqual(view["traceback"], "Traceback (most recent call last): ...")
        self.assertNotIn("violations", view)

    def test_view_is_a_copy_not_a_reference(self) -> None:
        view = model_provider._sandbox_error_view(UNSAFE_ERROR)
        view["violations"][0]["line"] = 999
        self.assertEqual(UNSAFE_ERROR["details"]["violations"][0]["line"], 3)


class RepairPromptTests(unittest.TestCase):
    def _client(self) -> OllamaCompatiblePlannerClient:
        return OllamaCompatiblePlannerClient(
            endpoint_url="http://10.0.1.39:11434", planner_model="gemma4:e4b"
        )

    def test_repair_prompt_carries_the_violations_and_instructs_removal(self) -> None:
        payload = self._client()._codegen_repair_payload(
            "def render_chart(data, output_path):\n    import os\n    return {}",
            UNSAFE_ERROR,
            {"chart_spec": {}, "history_series": []},
            model=None,
        )
        content = payload["messages"][1]["content"]
        self.assertIn("forbidden_import", content)
        self.assertIn("dunder_attribute", content)
        # the task text must direct the model to act on the violations
        parsed = json.loads(content)
        self.assertIn("violations", parsed["sandbox_error"])
        self.assertIn("remove or replace", parsed["task"].lower())


class CodegenFailureDetailTests(unittest.TestCase):
    """Diagnostics: the fallback WARNING carries a compact, log-safe detail."""

    def test_unsafe_code_detail_summarizes_violations(self) -> None:
        from custom_components.isolinear import job_orchestration

        detail = job_orchestration._compact_codegen_error_detail(UNSAFE_ERROR)
        self.assertIn("violations", detail)
        self.assertTrue(any("forbidden_import@L3" in v for v in detail["violations"]))

    def test_runtime_detail_keeps_traceback_tail(self) -> None:
        from custom_components.isolinear import job_orchestration

        detail = job_orchestration._compact_codegen_error_detail(RUNTIME_ERROR)
        self.assertIn("traceback_tail", detail)

    def test_clean_error_has_no_detail(self) -> None:
        from custom_components.isolinear import job_orchestration

        self.assertIsNone(job_orchestration._compact_codegen_error_detail({"code": "x"}))
        self.assertIsNone(job_orchestration._compact_codegen_error_detail(None))


class WorkerRenderLogTests(unittest.TestCase):
    """The worker logs each sandbox outcome (docker-logs visibility)."""

    def test_unsafe_code_logs_warning_with_violation_summary(self) -> None:
        sys.path.insert(0, str(REPO_ROOT / "worker"))
        from isolinear_worker import http_server

        with self.assertLogs("isolinear_worker.http_server", level="WARNING") as cm:
            http_server._log_render_outcome("req-1", {"status": "failed", "error": UNSAFE_ERROR})
        joined = " ".join(cm.output)
        self.assertIn("unsafe_code", joined)
        self.assertIn("forbidden_import@L3", joined)

    def test_success_logs_info(self) -> None:
        sys.path.insert(0, str(REPO_ROOT / "worker"))
        from isolinear_worker import http_server

        with self.assertLogs("isolinear_worker.http_server", level="INFO") as cm:
            http_server._log_render_outcome("req-2", {"status": "success"})
        self.assertIn("status=success", " ".join(cm.output))


if __name__ == "__main__":
    unittest.main()
