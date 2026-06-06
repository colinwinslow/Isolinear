import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.transport_auth_anchor import verify_transport_auth_anchor  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_transport_auth_anchor(REPO_ROOT)

    assert_true(result["passed"], f"Transport/auth anchor verification failed: {result['failures']!r}")

    print_case(
        "integration_ws_commands_are_versioned",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "fake-config-entry",
            "schema": "docs/schemas/integration-ws-command.schema.json",
        },
        when={
            "operation": "validate_start_answer_retry_snapshot_and_subscribe_commands",
        },
        then={
            "commands": result["commands"],
            "command_results": result["command_results"],
            "snapshot_results": result["snapshot_results"],
        },
    )

    print_case(
        "worker_render_request_uses_integration_owned_auth",
        given={
            "worker_path": "/v1/render",
            "schema": "docs/schemas/worker-transport-request.schema.json",
            "nested_schema": "docs/schemas/render-request.schema.json",
        },
        when={
            "operation": "validate_worker_transport_request",
        },
        then={
            "redacted_worker_request": result["valid_worker_request"],
            "valid_worker_result": result["valid_worker_result"],
            "evidence_redaction": result["evidence_redaction"],
        },
    )

    print_case(
        "worker_rejects_bad_auth_or_version_before_rendering",
        given={
            "invalid_examples": [
                "missing_auth",
                "bad_token",
                "wrong_version",
                "leaked_home_assistant_token",
            ],
        },
        when={
            "operation": "validate_invalid_worker_transport_requests",
        },
        then={
            "rejection_results": result["rejection_results"],
        },
    )

    print_case(
        "card_does_not_receive_worker_boundary_material",
        given={
            "forbidden_boundary_material": [
                "worker_url",
                "worker_token",
                "model_endpoint",
                "entity_allowlist",
                "raw_history",
                "semantic_memory",
                "generated_code",
            ],
        },
        when={
            "operation": "validate_leaky_card_command",
        },
        then={
            "invalid_card_command_result": result["invalid_card_command_result"],
            "evidence_redaction": result["evidence_redaction"],
        },
    )

    print("PASS integration_api_transport_auth")


if __name__ == "__main__":
    main()
