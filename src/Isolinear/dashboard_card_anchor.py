from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REQUIRED_SNAPSHOT_STATES = [
    "idle",
    "planning",
    "clarification_needed",
    "complete",
    "failed",
]

VALID_CARD_CONFIG = {
    "type": "custom:isolinear-card",
    "config_entry_id": "auto",
    "title": "Isolinear",
}

PROMPT_TEXT = "Compare upstairs and downstairs temperatures"

FORBIDDEN_BOUNDARY_PATTERNS = {
    "direct_network_client": re.compile(r"\b(fetch|XMLHttpRequest|EventSource|WebSocket)\s*\("),
    "direct_worker_or_model_endpoint": re.compile(
        r"(worker_url|workerEndpoint|model_url|modelEndpoint|ollama|openai)",
        re.IGNORECASE,
    ),
    "home_assistant_history_api": re.compile(
        r"(/api/history|history/period|getHistory|historyApi)",
        re.IGNORECASE,
    ),
    "mutation_service_call": re.compile(r"\bcallService\s*\("),
    "semantic_memory_file_access": re.compile(
        r"(semantic-memory|semantic_memory|semanticMemoryStore|aliases\.json)",
        re.IGNORECASE,
    ),
    "browser_local_state": re.compile(r"\b(localStorage|sessionStorage|indexedDB)\b"),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def frontend_root(root: Path | None = None) -> Path:
    return (root or repo_root()) / "frontend"


def load_job_snapshots(root: Path | None = None) -> dict[str, Any]:
    fixture_path = frontend_root(root) / "fixtures" / "job-snapshots.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def load_frontend_texts(root: Path | None = None) -> dict[str, str]:
    base = frontend_root(root)
    paths = {
        "typescript_card": base / "src" / "isolinear-card.ts",
        "typescript_api": base / "src" / "isolinear-api.ts",
        "typescript_types": base / "src" / "types.ts",
        "bundle": base / "dist" / "isolinear-card.js",
        "harness": base / "harness" / "index.html",
        "fake_hass": base / "harness" / "fake-hass.js",
    }
    return {
        name: path.read_text(encoding="utf-8")
        for name, path in paths.items()
    }


def validate_card_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if not config or config.get("type") != "custom:isolinear-card":
        raise ValueError("Isolinear card config requires type custom:isolinear-card.")
    config_entry_id = config.get("config_entry_id", "auto")
    if not isinstance(config_entry_id, str) or config_entry_id.strip() == "":
        raise ValueError("Isolinear card config requires config_entry_id.")

    return {
        "type": "custom:isolinear-card",
        "config_entry_id": config_entry_id,
        "title": config.get("title", "Isolinear"),
        "density": config.get("density", "comfortable"),
        "render_preference": config.get("render_preference", "trusted"),
    }


def observed_config_behavior() -> dict[str, Any]:
    invalid_configs: list[dict[str, Any] | None] = [
        None,
        {},
        {"type": "custom:wrong-card", "config_entry_id": "fake-config-entry"},
        {"type": "custom:isolinear-card", "config_entry_id": ""},
    ]
    invalid_results = []
    for config in invalid_configs:
        try:
            validate_card_config(config)
        except ValueError as exc:
            invalid_results.append(
                {
                    "config": config,
                    "accepted": False,
                    "error": str(exc),
                }
            )
        else:
            invalid_results.append(
                {
                    "config": config,
                    "accepted": True,
                    "error": None,
                }
            )

    return {
        "valid_config": validate_card_config(VALID_CARD_CONFIG),
        "valid_default_config": validate_card_config({"type": "custom:isolinear-card"}),
        "invalid_configs": invalid_results,
    }


def observed_registration(root: Path | None = None) -> dict[str, Any]:
    texts = load_frontend_texts(root)
    bundle = texts["bundle"]
    typescript_card = texts["typescript_card"]

    return {
        "custom_element_defined": (
            'customElements.define("isolinear-card"' in bundle
            or 'mt("isolinear-card")' in bundle
            or '@customElement("isolinear-card")' in typescript_card
        ),
        "editor_element_defined": (
            'customElements.define("isolinear-card-editor"' in bundle
            or 'mt("isolinear-card-editor")' in bundle
            or '@customElement("isolinear-card-editor")' in typescript_card
        ),
        "lit_source_custom_element": '@customElement("isolinear-card")' in typescript_card,
        "card_picker_metadata": {
            "window_custom_cards": "window.customCards" in bundle,
            "type": "isolinear-card" if 'type: "isolinear-card"' in bundle else None,
            "name": "Isolinear" if 'name: "Isolinear"' in bundle else None,
            "preview": True if "preview: true" in f"{typescript_card}\n{bundle}" else False,
        },
        "configuration_surface": {
            "get_config_element": "getConfigElement" in bundle or "getConfigElement" in typescript_card,
            "editor_defined": "IsolinearCardEditor" in bundle or "IsolinearCardEditor" in typescript_card,
        },
        "card_sizing_hooks": {
            "get_card_size": "getCardSize" in bundle or "getCardSize" in typescript_card,
            "get_grid_options": "getGridOptions" in bundle or "getGridOptions" in typescript_card,
        },
    }


def observed_layout(root: Path | None = None) -> dict[str, Any]:
    texts = load_frontend_texts(root)
    bundle = texts["bundle"]
    typescript_card = texts["typescript_card"]
    snapshots = load_job_snapshots(root)
    combined = f"{typescript_card}\n{bundle}"
    return {
        "idle_prompt_first": {
            "fixture_status": snapshots["idle"]["status"],
            "layout_marker": '"prompt-first"' in combined,
            "prompt_input_marker": 'data-testid="prompt-input"' in combined,
            "submit_button_marker": 'data-testid="submit-button"' in combined,
        },
        "active_planning": {
            "fixture_status": snapshots["planning"]["status"],
            "job_state_marker": 'data-testid="job-state"' in combined,
            "disabled_duplicate_submit_marker": (
                'activeSnapshot.status === "planning"' in combined
                or 'this.snapshot.status === "planning"' in combined
                or '.status === "planning"' in combined
            ),
        },
        "clarification": {
            "fixture_status": snapshots["clarification_needed"]["status"],
            "panel_marker": 'data-testid="clarification-panel"' in combined,
            "use_once_marker": "Use once" in combined,
            "use_and_remember_marker": "Use and remember" in combined,
        },
        "complete_chart_first": {
            "fixture_status": snapshots["complete"]["status"],
            "layout_marker": '"chart-first"' in combined,
            "chart_image_marker": 'data-testid="chart-image"' in combined,
            "chart_dominant_rows": 'grid-template-rows: auto minmax(280px, 1fr) auto' in combined,
            "bottom_composer_marker": 'data-testid="composer"' in combined,
            "compact_complete_composer_rows": (
                'activeSnapshot.status === "complete" ? 1 : 3' in combined
                or 'snapshot.status === "complete" ? 1 : 3' in combined
                or 'status === "complete" ? 1 : 3' in combined
            ),
        },
        "failed": {
            "fixture_status": snapshots["failed"]["status"],
            "failure_marker": 'data-testid="failure-details"' in combined,
            "retry_marker": 'data-testid="retry-button"' in combined,
            "revise_marker": 'data-testid="revise-button"' in combined,
        },
    }


def recorded_fake_websocket_messages(root: Path | None = None) -> list[dict[str, Any]]:
    snapshots = load_job_snapshots(root)
    clarification = snapshots["clarification_needed"]
    option = clarification["clarification"]["options"][0]
    failed = snapshots["failed"]

    return [
        {
            "type": "isolinear/v1/job/start",
            "version": 1,
            "config_entry_id": VALID_CARD_CONFIG["config_entry_id"],
            "prompt": PROMPT_TEXT,
        },
        {
            "type": "isolinear/v1/clarification/answer",
            "version": 1,
            "config_entry_id": VALID_CARD_CONFIG["config_entry_id"],
            "job_id": clarification["job_id"],
            "question_id": clarification["clarification"]["question_id"],
            "option_id": option["option_id"],
            "remember": False,
        },
        {
            "type": "isolinear/v1/clarification/answer",
            "version": 1,
            "config_entry_id": VALID_CARD_CONFIG["config_entry_id"],
            "job_id": clarification["job_id"],
            "question_id": clarification["clarification"]["question_id"],
            "option_id": option["option_id"],
            "remember": True,
        },
        {
            "type": "isolinear/v1/job/retry",
            "version": 1,
            "config_entry_id": VALID_CARD_CONFIG["config_entry_id"],
            "job_id": failed["job_id"],
        },
    ]


def observed_adapter(root: Path | None = None) -> dict[str, Any]:
    texts = load_frontend_texts(root)
    combined = "\n".join(texts.values())
    messages = recorded_fake_websocket_messages(root)
    return {
        "all_commands_versioned": all(
            message["type"].startswith("isolinear/v1/")
            and message["version"] == 1
            for message in messages
        ),
        "fake_hass_records_calls": "calls.push(message)" in texts["fake_hass"],
        "card_uses_send_message_promise": "sendMessagePromise" in texts["bundle"],
        "command_markers_present": {
            message["type"]: message["type"] in combined
            for message in messages
        },
        "recorded_messages": messages,
    }


def boundary_check(root: Path | None = None) -> dict[str, Any]:
    base = frontend_root(root)
    scanned_files = [
        base / "src" / "types.ts",
        base / "src" / "isolinear-api.ts",
        base / "src" / "isolinear-card.ts",
        base / "dist" / "isolinear-card.js",
    ]
    matches = []

    for path in scanned_files:
        text = path.read_text(encoding="utf-8")
        for name, pattern in FORBIDDEN_BOUNDARY_PATTERNS.items():
            for match in pattern.finditer(text):
                matches.append(
                    {
                        "file": path.relative_to(root or repo_root()).as_posix(),
                        "check": name,
                        "match": match.group(0),
                    }
                )

    return {
        "passed": not matches,
        "scanned_files": [
            path.relative_to(root or repo_root()).as_posix()
            for path in scanned_files
        ],
        "matches": matches,
    }


def anchor_file_inventory(root: Path | None = None) -> dict[str, Any]:
    base = frontend_root(root)
    paths = [
        base / "package.json",
        base / "tsconfig.json",
        base / "vite.config.ts",
        base / "src" / "types.ts",
        base / "src" / "isolinear-api.ts",
        base / "src" / "isolinear-card.ts",
        base / "dist" / "isolinear-card.js",
        base / "fixtures" / "job-snapshots.json",
        base / "fixtures" / "fake-temperature-chart.svg",
        base / "harness" / "fake-hass.js",
        base / "harness" / "index.html",
    ]
    root_path = root or repo_root()
    return {
        "files": [
            {
                "path": path.relative_to(root_path).as_posix(),
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
            }
            for path in paths
        ],
    }


def verify_dashboard_card_anchor(root: Path | None = None) -> dict[str, Any]:
    snapshots = load_job_snapshots(root)
    missing_states = [
        state
        for state in REQUIRED_SNAPSHOT_STATES
        if state not in snapshots
    ]
    state_status_mismatches = [
        state
        for state in REQUIRED_SNAPSHOT_STATES
        if state in snapshots and snapshots[state]["status"] != state
    ]

    registration = observed_registration(root)
    layout = observed_layout(root)
    adapter = observed_adapter(root)
    boundary = boundary_check(root)
    inventory = anchor_file_inventory(root)
    config_behavior = observed_config_behavior()

    failures = []
    if missing_states:
        failures.append(f"Missing fixture states: {missing_states!r}.")
    if state_status_mismatches:
        failures.append(f"Fixture status mismatches: {state_status_mismatches!r}.")
    if not all(item["exists"] and item["bytes"] > 0 for item in inventory["files"]):
        failures.append("Expected frontend anchor files are missing or empty.")
    if not all(
        [
            registration["custom_element_defined"],
            registration["editor_element_defined"],
            registration["lit_source_custom_element"],
            registration["card_picker_metadata"]["window_custom_cards"],
            registration["card_picker_metadata"]["type"] == "isolinear-card",
            registration["configuration_surface"]["get_config_element"],
            registration["card_sizing_hooks"]["get_card_size"],
            registration["card_sizing_hooks"]["get_grid_options"],
        ]
    ):
        failures.append("Custom-card registration or Home Assistant hooks are incomplete.")
    if not all(
        value is True
        for group in layout.values()
        for key, value in group.items()
        if key.endswith("_marker") or key in {"chart_dominant_rows", "compact_complete_composer_rows"}
    ):
        failures.append("Expected state rendering or layout markers are missing.")
    if not adapter["all_commands_versioned"]:
        failures.append("Recorded Isolinear messages are not versioned.")
    if not adapter["fake_hass_records_calls"]:
        failures.append("Fake Home Assistant harness does not record adapter calls.")
    if not adapter["card_uses_send_message_promise"]:
        failures.append("Card bundle does not use the Home Assistant message adapter.")
    if not all(adapter["command_markers_present"].values()):
        failures.append("Card or harness source is missing expected command markers.")
    if not boundary["passed"]:
        failures.append("Boundary scan found forbidden direct access markers.")
    if any(result["accepted"] for result in config_behavior["invalid_configs"]):
        failures.append("Invalid card config was accepted.")

    return {
        "passed": not failures,
        "failures": failures,
        "inventory": inventory,
        "snapshots": snapshots,
        "registration": registration,
        "config_behavior": config_behavior,
        "layout": layout,
        "adapter": adapter,
        "boundary": boundary,
    }
