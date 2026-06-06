import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import ContractValidationError, validate_contract  # noqa: E402
from Isolinear.transport_auth_anchor import (  # noqa: E402
    INTEGRATION_COMMAND_TYPES,
    TEST_WORKER_TOKEN,
    sample_integration_ws_commands,
    sample_worker_transport_request,
    validate_integration_ws_command,
    validate_worker_transport_request,
    verify_transport_auth_anchor,
    worker_rejection_examples,
)


class TransportAuthAnchorTests(unittest.TestCase):
    def test_sample_integration_commands_cover_required_websocket_contract(self):
        commands = sample_integration_ws_commands()

        self.assertEqual(list(commands), list(INTEGRATION_COMMAND_TYPES))
        self.assertEqual(
            [command["type"] for command in commands.values()],
            list(INTEGRATION_COMMAND_TYPES.values()),
        )

        for command in commands.values():
            validate_contract("integration-ws-command", command, repo_root=REPO_ROOT)
            result = validate_integration_ws_command(command, root=REPO_ROOT)
            self.assertTrue(result["accepted"], result)
            self.assertTrue(command["type"].startswith("isolinear/v1/"))

    def test_integration_command_schema_rejects_unknown_or_leaky_commands(self):
        unknown_command = {
            "type": "isolinear/v1/job/delete",
            "version": 1,
            "config_entry_id": "fake-config-entry",
            "job_id": "job-001",
        }
        with self.assertRaises(ContractValidationError):
            validate_contract("integration-ws-command", unknown_command, repo_root=REPO_ROOT)

        leaky_command = sample_integration_ws_commands()["start_job"]
        leaky_command = {**leaky_command, "worker_url": "http://worker.local:8765"}
        result = validate_integration_ws_command(leaky_command, root=REPO_ROOT)

        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "forbidden_card_boundary_content")
        self.assertEqual(result["forbidden_matches"][0]["path"], "$.worker_url")

    def test_worker_transport_accepts_only_expected_bearer_token(self):
        request = sample_worker_transport_request()
        result = validate_worker_transport_request(request, root=REPO_ROOT)

        self.assertTrue(result["accepted"], result)
        self.assertTrue(result["render_attempted"])
        self.assertEqual(result["authorization"], "Bearer <redacted>")
        self.assertNotIn(TEST_WORKER_TOKEN, str(result))

    def test_worker_transport_rejects_bad_auth_version_and_secret_leakage(self):
        examples = worker_rejection_examples()
        expected_codes = {
            "missing_auth": "missing_worker_authorization",
            "bad_token": "unauthorized_worker_request",
            "wrong_version": "unsupported_worker_api_version",
            "leaked_home_assistant_token": "forbidden_worker_boundary_content",
        }

        for name, example in examples.items():
            result = validate_worker_transport_request(example, root=REPO_ROOT)
            self.assertFalse(result["accepted"], result)
            self.assertFalse(result["render_attempted"], result)
            self.assertEqual(result["code"], expected_codes[name])

        leak_result = validate_worker_transport_request(
            examples["leaked_home_assistant_token"],
            root=REPO_ROOT,
        )
        self.assertEqual(
            leak_result["forbidden_matches"],
            [{"path": "$.body.render_request.theme.home_assistant_token", "reason": "forbidden_key"}],
        )

    def test_transport_auth_anchor_verification_passes_and_redacts_evidence(self):
        result = verify_transport_auth_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])
        self.assertTrue(result["evidence_redaction"]["worker_token_redacted"])
        self.assertTrue(result["evidence_redaction"]["home_assistant_token_redacted"])
        self.assertNotIn(TEST_WORKER_TOKEN, str(result["valid_worker_request"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
