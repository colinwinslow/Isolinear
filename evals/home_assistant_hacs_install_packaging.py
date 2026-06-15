from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear import dashboard_resource
from custom_components.isolinear import entity_catalog
from custom_components.isolinear import history_retrieval
from custom_components.isolinear import job_orchestration
from custom_components.isolinear import job_state
from custom_components.isolinear import model_provider
from custom_components.isolinear import model_provider_health
from custom_components.isolinear import worker_health
from custom_components.isolinear import worker_health_polling_constants
from custom_components.isolinear import worker_readiness
from custom_components.isolinear import worker_token_lifecycle
from custom_components.isolinear._paths import FRONTEND_DIST_DIR, PACKAGE_DIR, SCHEMAS_DIR
from custom_components.isolinear.const import INTEGRATION_VERSION

SCHEMA_PATH_CONSTANTS = (
    entity_catalog.ENTITY_CATALOG_SCHEMA_PATH,
    history_retrieval.HISTORY_SERIES_SCHEMA_PATH,
    job_orchestration.ARTIFACT_METADATA_SCHEMA_PATH,
    job_orchestration.RENDER_PLAN_SCHEMA_PATH,
    job_orchestration.MODEL_PROVIDER_PLAN_SCHEMA_PATH,
    job_orchestration.MODEL_PROVIDER_RETRY_POLICY_SCHEMA_PATH,
    job_orchestration.WORKER_DISPATCH_SCHEMA_PATH,
    job_orchestration.WORKER_PROGRESS_SCHEMA_PATH,
    job_orchestration.WORKER_RETRY_POLICY_SCHEMA_PATH,
    job_orchestration.WORKER_TRANSPORT_FAILURE_CLASSIFICATION_SCHEMA_PATH,
    job_orchestration.WORKER_TRANSPORT_REQUEST_SCHEMA_PATH,
    job_orchestration.RENDER_REQUEST_SCHEMA_PATH,
    job_orchestration.RENDER_RESULT_SCHEMA_PATH,
    job_orchestration.PLANNER_RESULT_SCHEMA_PATH,
    job_orchestration.CHART_SPEC_SCHEMA_PATH,
    job_state.SNAPSHOT_SCHEMA_PATH,
    model_provider.PLANNER_RESULT_SCHEMA_PATH,
    model_provider_health.MODEL_PROVIDER_HEALTH_SCHEMA_PATH,
    model_provider_health.MODEL_PROVIDER_HEALTH_REQUEST_SCHEMA_PATH,
    worker_health.WORKER_HEALTH_SCHEMA_PATH,
    worker_health.WORKER_HEALTH_REQUEST_SCHEMA_PATH,
    worker_health_polling_constants.WORKER_HEALTH_POLLING_SCHEMA_PATH,
    worker_readiness.WORKER_READINESS_SCHEMA_PATH,
    worker_token_lifecycle.WORKER_TOKEN_LIFECYCLE_SCHEMA_PATH,
)


def main() -> int:
    cases = [
        repository_is_hacs_shaped(),
        manifest_is_hacs_ready(),
        runtime_schemas_are_bundled(),
        dashboard_card_is_bundled(),
        frontend_build_refreshes_packaged_card(),
    ]
    failed = False
    for case in cases:
        print(f"CASE {case['case_id']}")
        print(json.dumps(case, indent=2, sort_keys=True))
        passed = bool(case["then"]["passed"])
        print(("PASS" if passed else "FAIL") + f" {case['case_id']}")
        failed = failed or not passed
    if failed:
        return 1
    print("PASS home_assistant_hacs_install_packaging")
    return 0


def repository_is_hacs_shaped() -> dict[str, Any]:
    hacs = json.loads((REPO_ROOT / "hacs.json").read_text(encoding="utf-8"))
    integration_dirs = [
        path.name
        for path in (REPO_ROOT / "custom_components").iterdir()
        if path.is_dir()
    ]
    return {
        "case_id": "repository_is_hacs_shaped",
        "given": {"repository_root": str(REPO_ROOT)},
        "when": {"operation": "inspect_hacs_custom_repository_shape"},
        "then": {
            "hacs_name": hacs.get("name"),
            "integration_dirs": integration_dirs,
            "package_dir": str(PACKAGE_DIR),
            "passed": hacs.get("name") == "Isolinear" and integration_dirs == ["isolinear"],
        },
    }


def manifest_is_hacs_ready() -> dict[str, Any]:
    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    required = ("domain", "name", "version", "documentation", "issue_tracker", "codeowners")
    missing = [key for key in required if key not in manifest]
    return {
        "case_id": "manifest_is_hacs_ready",
        "given": {"manifest": str(PACKAGE_DIR / "manifest.json")},
        "when": {"operation": "inspect_manifest_metadata"},
        "then": {
            "missing": missing,
            "domain": manifest.get("domain"),
            "issue_tracker": manifest.get("issue_tracker"),
            "passed": not missing and manifest.get("domain") == "isolinear",
        },
    }


def runtime_schemas_are_bundled() -> dict[str, Any]:
    root_schemas = REPO_ROOT / "docs" / "schemas"
    root_schema_names = sorted(path.name for path in root_schemas.glob("*.json"))
    packaged_schema_names = sorted(path.name for path in SCHEMAS_DIR.glob("*.json"))
    mismatched = [
        name
        for name in root_schema_names
        if (SCHEMAS_DIR / name).read_bytes() != (root_schemas / name).read_bytes()
    ]
    non_package_paths = [
        str(path)
        for path in SCHEMA_PATH_CONSTANTS
        if not path.is_file() or not path.is_relative_to(SCHEMAS_DIR)
    ]
    return {
        "case_id": "runtime_schemas_are_bundled",
        "given": {
            "root_schemas": str(root_schemas),
            "packaged_schemas": str(SCHEMAS_DIR),
        },
        "when": {"operation": "compare_schema_payloads_and_runtime_paths"},
        "then": {
            "root_schema_count": len(root_schema_names),
            "packaged_schema_count": len(packaged_schema_names),
            "mismatched": mismatched,
            "non_package_paths": non_package_paths,
            "passed": packaged_schema_names == root_schema_names and not mismatched and not non_package_paths,
        },
    }


def dashboard_card_is_bundled() -> dict[str, Any]:
    bundle_path = FRONTEND_DIST_DIR / dashboard_resource.CARD_BUNDLE_FILENAME
    root_bundle = REPO_ROOT / "frontend" / "dist" / dashboard_resource.CARD_BUNDLE_FILENAME
    expected_resource_url = f"/api/isolinear/static/isolinear-card.js?v={INTEGRATION_VERSION}"
    return {
        "case_id": "dashboard_card_is_bundled",
        "given": {"root_bundle": str(root_bundle)},
        "when": {"operation": "resolve_dashboard_resource_bundle"},
        "then": {
            "packaged_bundle": str(bundle_path),
            "bundle_exists": bundle_path.is_file(),
            "bundle_matches_root": bundle_path.is_file() and bundle_path.read_bytes() == root_bundle.read_bytes(),
            "resource": dashboard_resource.dashboard_resource_metadata(),
            "expected_resource_url": expected_resource_url,
            "passed": (
                bundle_path.is_file()
                and bundle_path.read_bytes() == root_bundle.read_bytes()
                and dashboard_resource.frontend_dist_path() == FRONTEND_DIST_DIR
                and dashboard_resource.dashboard_resource_metadata()["url"] == expected_resource_url
            ),
        },
    }


def frontend_build_refreshes_packaged_card() -> dict[str, Any]:
    script = (REPO_ROOT / "scripts" / "frontend.ps1").read_text(encoding="utf-8")
    checks = {
        "packaged_dist_path": "custom_components\\isolinear\\frontend\\dist" in script,
        "copy_item": "Copy-Item" in script,
        "bundle_name": "isolinear-card.js" in script,
    }
    return {
        "case_id": "frontend_build_refreshes_packaged_card",
        "given": {"script": str(REPO_ROOT / "scripts" / "frontend.ps1")},
        "when": {"operation": "inspect_frontend_build_helper"},
        "then": {
            "checks": checks,
            "passed": all(checks.values()),
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
