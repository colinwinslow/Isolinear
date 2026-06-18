import json
from pathlib import Path

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


REPO_ROOT = Path(__file__).resolve().parents[1]

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


def test_repository_is_hacs_shaped() -> None:
    hacs = json.loads((REPO_ROOT / "hacs.json").read_text(encoding="utf-8"))
    integration_dirs = [
        path.name
        for path in (REPO_ROOT / "custom_components").iterdir()
        if path.is_dir()
    ]

    assert hacs["name"] == "Isolinear"
    assert integration_dirs == ["isolinear"]
    assert PACKAGE_DIR == REPO_ROOT / "custom_components" / "isolinear"


def test_manifest_has_hacs_required_metadata() -> None:
    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))

    for key in ("domain", "name", "version", "documentation", "issue_tracker", "codeowners"):
        assert key in manifest
    assert manifest["domain"] == "isolinear"
    assert manifest["issue_tracker"].endswith("/issues")
    assert "lovelace" in manifest["dependencies"]
    assert manifest["requirements"] == ["matplotlib>=3.7,<4"]


def test_brand_icons_are_packaged() -> None:
    repository_brand_dir = REPO_ROOT / "brand"
    repository_icon = repository_brand_dir / "icon.png"
    repository_high_density_icon = repository_brand_dir / "icon@2x.png"
    brand_dir = PACKAGE_DIR / "brand"
    icon = brand_dir / "icon.png"
    high_density_icon = brand_dir / "icon@2x.png"

    assert repository_brand_dir.is_dir()
    assert repository_icon.is_file()
    assert repository_high_density_icon.is_file()
    assert brand_dir.is_dir()
    assert icon.is_file()
    assert high_density_icon.is_file()
    assert repository_icon.read_bytes() == icon.read_bytes()
    assert repository_high_density_icon.read_bytes() == high_density_icon.read_bytes()
    assert icon.stat().st_size > 0
    assert high_density_icon.stat().st_size > icon.stat().st_size


def test_runtime_schema_paths_are_packaged_and_in_sync() -> None:
    root_schemas = REPO_ROOT / "docs" / "schemas"
    packaged_schema_names = sorted(path.name for path in SCHEMAS_DIR.glob("*.json"))
    root_schema_names = sorted(path.name for path in root_schemas.glob("*.json"))

    assert packaged_schema_names == root_schema_names
    for schema_name in root_schema_names:
        assert (SCHEMAS_DIR / schema_name).read_bytes() == (root_schemas / schema_name).read_bytes()

    for schema_path in SCHEMA_PATH_CONSTANTS:
        assert schema_path.is_file()
        assert schema_path.is_relative_to(SCHEMAS_DIR)


def test_dashboard_card_bundle_is_packaged() -> None:
    bundle_path = FRONTEND_DIST_DIR / dashboard_resource.CARD_BUNDLE_FILENAME
    root_bundle = REPO_ROOT / "frontend" / "dist" / dashboard_resource.CARD_BUNDLE_FILENAME

    assert dashboard_resource.frontend_dist_path() == FRONTEND_DIST_DIR
    assert dashboard_resource.frontend_dist_path(REPO_ROOT) == FRONTEND_DIST_DIR
    assert bundle_path.is_file()
    assert bundle_path.read_bytes() == root_bundle.read_bytes()
    assert dashboard_resource.dashboard_resource_metadata() == {
        "url": f"/api/isolinear/static/isolinear-card.js?v={INTEGRATION_VERSION}",
        "type": "module",
    }


def test_frontend_build_refreshes_packaged_card() -> None:
    script = (REPO_ROOT / "scripts" / "frontend.ps1").read_text(encoding="utf-8")

    assert "custom_components\\isolinear\\frontend\\dist" in script
    assert "Copy-Item" in script
    assert "isolinear-card.js" in script
