"""Contract validators and schema paths for job orchestration (ADR-0035 step 1).

The deterministic validation gates (invariants #4/#5): every major record —
artifact metadata, render plan/request/result, worker dispatch/progress/retry,
model-provider plan, planner result, chart spec — validates against its JSON
Schema in ``docs/schemas`` before storage or dispatch, plus the structural
entity-reference checks (allowlist breach vs substitution, duplicate series
sources). Also home to the pure chart-spec/source-snapshot readers those
checks walk. Layer L0 of the split: imports nothing from the orchestration
modules above it. See docs/specs/job-orchestration-split.md.
"""
from __future__ import annotations

import json
from typing import Any

from ._paths import load_schema_document, schema_path
from .history_retrieval import validate_history_series_collection_contract
from .job_state import (
    JobStateSnapshotValidationError,
    _validate_json_schema,
    validate_job_snapshot_contract,
)

ARTIFACT_METADATA_SCHEMA_PATH = (
    schema_path("integration-artifact-metadata.schema.json")
)
RENDER_PLAN_SCHEMA_PATH = (
    schema_path("integration-render-plan.schema.json")
)
MODEL_PROVIDER_PLAN_SCHEMA_PATH = (
    schema_path("integration-model-provider-plan.schema.json")
)
MODEL_PROVIDER_RETRY_POLICY_SCHEMA_PATH = (
    schema_path("integration-model-provider-retry-policy.schema.json")
)
WORKER_DISPATCH_SCHEMA_PATH = (
    schema_path("integration-worker-dispatch.schema.json")
)
WORKER_PROGRESS_SCHEMA_PATH = (
    schema_path("integration-worker-progress.schema.json")
)
WORKER_RETRY_POLICY_SCHEMA_PATH = (
    schema_path("integration-worker-retry-policy.schema.json")
)
WORKER_TRANSPORT_FAILURE_CLASSIFICATION_SCHEMA_PATH = (
    schema_path("integration-worker-transport-failure-classification.schema.json")
)
WORKER_TRANSPORT_REQUEST_SCHEMA_PATH = (
    schema_path("worker-transport-request.schema.json")
)
RENDER_REQUEST_SCHEMA_PATH = schema_path("render-request.schema.json")
RENDER_RESULT_SCHEMA_PATH = schema_path("render-result.schema.json")
PLANNER_RESULT_SCHEMA_PATH = schema_path("planner-result.schema.json")
CHART_SPEC_SCHEMA_PATH = schema_path("chart-spec.schema.json")


def _chart_spec_entity_ids(chart_spec: dict[str, Any]) -> dict[str, Any]:
    entity_ids: set[str] = set()
    unsupported_source_refs: list[dict[str, Any]] = []

    for collection_name in ("series", "overlays"):
        for index, item in enumerate(chart_spec.get(collection_name, [])):
            if not isinstance(item, dict):
                continue
            source = item.get("source")
            _collect_source_entity_ids(
                source,
                entity_ids,
                unsupported_source_refs,
                path=f"{collection_name}[{index}].source",
            )

    return {
        "entity_ids": entity_ids,
        "unsupported_source_refs": unsupported_source_refs,
    }


def _memory_proposal_entity_ids(planner_result: Any) -> set[str]:
    """Collect entity IDs from ``memory_proposals`` (a persisted, reusable path).

    Unlike free-text fields, a memory proposal persists a ``SemanticAlias`` that
    a later prompt can resolve, so an off-allowlist ``entity_id`` here is a real
    reference worth rejecting at creation time rather than relying solely on the
    use-time alias revalidation (invariant #7).
    """
    entity_ids: set[str] = set()
    if not isinstance(planner_result, dict):
        return entity_ids
    proposals = planner_result.get("memory_proposals")
    if not isinstance(proposals, list):
        return entity_ids
    for proposal in proposals:
        if isinstance(proposal, dict):
            entity_id = proposal.get("entity_id")
            if isinstance(entity_id, str) and entity_id:
                entity_ids.add(entity_id)
    return entity_ids


def _collect_source_entity_ids(
    source: Any,
    entity_ids: set[str],
    unsupported_source_refs: list[dict[str, Any]],
    *,
    path: str,
) -> None:
    if not isinstance(source, dict):
        unsupported_source_refs.append({"path": path, "reason": "missing_source"})
        return

    source_type = source.get("type")
    if source_type == "entity":
        entity_id = source.get("entity_id")
        if isinstance(entity_id, str):
            entity_ids.add(entity_id)
        return
    if source_type == "aggregate":
        for entity_id in source.get("entity_ids", []):
            if isinstance(entity_id, str):
                entity_ids.add(entity_id)
        singular = source.get("entity_id")
        if isinstance(singular, str) and singular:
            entity_ids.add(singular)
        return

    unsupported_source_refs.append(
        {
            "path": path,
            "reason": "unsupported_or_unresolved_source",
            "source_type": source_type,
        }
    )


def _source_snapshot_entity_ids(source_snapshot: dict[str, Any]) -> list[str]:
    return [entity["entity_id"] for entity in _source_snapshot_entities(source_snapshot)]


def _source_snapshot_entities(source_snapshot: dict[str, Any]) -> list[dict[str, str]]:
    result = []
    for entity in source_snapshot.get("entities", []):
        if not isinstance(entity, dict):
            continue
        entity_id = entity.get("entity_id")
        label = entity.get("label") or entity_id
        if not isinstance(entity_id, str) or not isinstance(label, str):
            continue
        result.append(
            {
                "entity_id": entity_id,
                "label": label,
            }
        )
    return result


def validate_artifact_metadata_contract(artifact: Any) -> dict[str, Any]:
    """Validate IntegrationArtifactMetadata against the repo JSON Schema."""
    try:
        schema = load_schema_document(ARTIFACT_METADATA_SCHEMA_PATH)
        _validate_json_schema(artifact, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_artifact_metadata",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(ARTIFACT_METADATA_SCHEMA_PATH),
    }


def validate_render_plan_contract(render_plan: Any) -> dict[str, Any]:
    """Validate IntegrationRenderPlan and its placeholder ChartSpec."""
    try:
        schema = load_schema_document(RENDER_PLAN_SCHEMA_PATH)
        _validate_json_schema(render_plan, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_render_plan",
            "error": str(exc),
        }

    chart_validation = validate_chart_spec_contract(render_plan.get("chart_spec") if isinstance(render_plan, dict) else None)
    if not chart_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_chart_spec",
            "chart_validation": chart_validation,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(RENDER_PLAN_SCHEMA_PATH),
        "chart_schema": str(CHART_SPEC_SCHEMA_PATH),
    }


def validate_worker_dispatch_contract(worker_dispatch: Any) -> dict[str, Any]:
    """Validate IntegrationWorkerDispatch and its nested render result."""
    try:
        schema = load_schema_document(WORKER_DISPATCH_SCHEMA_PATH)
        _validate_json_schema(worker_dispatch, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_dispatch",
            "error": str(exc),
        }

    render_result_validation = validate_render_result_contract(
        worker_dispatch.get("render_result") if isinstance(worker_dispatch, dict) else None
    )
    if not render_result_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_render_result",
            "render_result_validation": render_result_validation,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_DISPATCH_SCHEMA_PATH),
        "render_result_schema": str(RENDER_RESULT_SCHEMA_PATH),
    }


def validate_worker_progress_contract(worker_progress: Any) -> dict[str, Any]:
    """Validate IntegrationWorkerProgress and its nested job snapshot."""
    try:
        schema = load_schema_document(WORKER_PROGRESS_SCHEMA_PATH)
        _validate_json_schema(worker_progress, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_progress",
            "error": str(exc),
        }

    snapshot_validation = validate_job_snapshot_contract(
        worker_progress.get("snapshot") if isinstance(worker_progress, dict) else None
    )
    if not snapshot_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_progress_snapshot",
            "snapshot_validation": snapshot_validation,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_PROGRESS_SCHEMA_PATH),
        "snapshot_schema": str(schema_path("integration-job-snapshot.schema.json")),
    }


def validate_worker_retry_policy_contract(worker_retry_policy: Any) -> dict[str, Any]:
    """Validate IntegrationWorkerRetryPolicy against the repo JSON Schema."""
    try:
        schema = load_schema_document(WORKER_RETRY_POLICY_SCHEMA_PATH)
        _validate_json_schema(worker_retry_policy, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_retry_policy",
            "error": str(exc),
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_RETRY_POLICY_SCHEMA_PATH),
    }


def validate_model_provider_retry_policy_contract(model_provider_retry_policy: Any) -> dict[str, Any]:
    """Validate IntegrationModelProviderRetryPolicy against the repo JSON Schema."""
    try:
        schema = load_schema_document(MODEL_PROVIDER_RETRY_POLICY_SCHEMA_PATH)
        _validate_json_schema(model_provider_retry_policy, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_model_provider_retry_policy",
            "error": str(exc),
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(MODEL_PROVIDER_RETRY_POLICY_SCHEMA_PATH),
    }


def validate_worker_transport_failure_classification_contract(classification: Any) -> dict[str, Any]:
    """Validate IntegrationWorkerTransportFailureClassification against the repo JSON Schema."""
    try:
        schema = load_schema_document(WORKER_TRANSPORT_FAILURE_CLASSIFICATION_SCHEMA_PATH)
        _validate_json_schema(classification, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_transport_failure_classification",
            "error": str(exc),
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_TRANSPORT_FAILURE_CLASSIFICATION_SCHEMA_PATH),
    }


def validate_worker_transport_request_contract(request: Any) -> dict[str, Any]:
    """Validate WorkerTransportRequest and its nested RenderRequest."""
    try:
        schema = load_schema_document(WORKER_TRANSPORT_REQUEST_SCHEMA_PATH)
        _validate_json_schema(request, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_worker_transport_request",
            "error": str(exc),
        }

    body = request.get("body") if isinstance(request, dict) else None
    render_request_validation = validate_render_request_contract(
        body.get("render_request") if isinstance(body, dict) else None
    )
    if not render_request_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_render_request",
            "render_request_validation": render_request_validation,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_TRANSPORT_REQUEST_SCHEMA_PATH),
        "render_request_schema": str(RENDER_REQUEST_SCHEMA_PATH),
    }


def validate_render_request_contract(render_request: Any) -> dict[str, Any]:
    """Validate RenderRequest, ChartSpec, and HistorySeries before worker dispatch."""
    try:
        schema = load_schema_document(RENDER_REQUEST_SCHEMA_PATH)
        _validate_json_schema(render_request, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_worker_render_request",
            "error": str(exc),
        }

    chart_validation = validate_chart_spec_contract(
        render_request.get("chart_spec") if isinstance(render_request, dict) else None
    )
    if not chart_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_chart_spec",
            "chart_validation": chart_validation,
        }

    history_validation = validate_history_series_collection_contract(
        render_request.get("history_series") if isinstance(render_request, dict) else None
    )
    if not history_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_history_series",
            "history_validation": history_validation,
        }

    history_entity_ids = {
        item.get("entity_id")
        for item in render_request.get("history_series", [])
        if isinstance(item, dict)
    }
    render_plan_entity_ids = _chart_spec_entity_ids(render_request.get("chart_spec", {}))["entity_ids"]
    missing_entity_ids = sorted(
        entity_id
        for entity_id in render_plan_entity_ids
        if entity_id not in history_entity_ids
    )
    if missing_entity_ids:
        return {
            "accepted": False,
            "code": "missing_worker_history_series",
            "missing_entity_ids": missing_entity_ids,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(RENDER_REQUEST_SCHEMA_PATH),
        "chart_schema": str(CHART_SPEC_SCHEMA_PATH),
        "history_schema": str(schema_path("history-series.schema.json")),
    }


def validate_render_result_contract(render_result: Any) -> dict[str, Any]:
    """Validate RenderResult before worker dispatch metadata storage."""
    try:
        schema = load_schema_document(RENDER_RESULT_SCHEMA_PATH)
        _validate_json_schema(render_result, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_worker_render_result",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(RENDER_RESULT_SCHEMA_PATH),
    }


def validate_model_provider_plan_contract(provider_plan: Any) -> dict[str, Any]:
    """Validate IntegrationModelProviderPlan and its nested planner output."""
    try:
        schema = load_schema_document(MODEL_PROVIDER_PLAN_SCHEMA_PATH)
        _validate_json_schema(provider_plan, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_model_provider_plan",
            "error": str(exc),
        }

    planner_validation = validate_planner_result_contract(
        provider_plan.get("planner_result") if isinstance(provider_plan, dict) else None
    )
    if not planner_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_planner_result",
            "planner_validation": planner_validation,
        }

    chart_validation = validate_chart_spec_contract(
        provider_plan.get("chart_spec") if isinstance(provider_plan, dict) else None
    )
    if not chart_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_model_provider_chart_spec",
            "chart_validation": chart_validation,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(MODEL_PROVIDER_PLAN_SCHEMA_PATH),
        "planner_schema": str(PLANNER_RESULT_SCHEMA_PATH),
        "chart_schema": str(CHART_SPEC_SCHEMA_PATH),
    }


def validate_planner_result_contract(planner_result: Any) -> dict[str, Any]:
    """Validate PlannerResult against the repo JSON Schema."""
    try:
        schema = load_schema_document(PLANNER_RESULT_SCHEMA_PATH)
        _validate_json_schema(planner_result, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_planner_result",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(PLANNER_RESULT_SCHEMA_PATH),
    }


def validate_chart_spec_contract(chart_spec: Any) -> dict[str, Any]:
    """Validate a placeholder ChartSpec against the repo JSON Schema."""
    try:
        schema = load_schema_document(CHART_SPEC_SCHEMA_PATH)
        _validate_json_schema(chart_spec, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_chart_spec",
            "error": str(exc),
        }
    duplicate_error = _check_chart_spec_no_duplicate_series_sources(chart_spec)
    if duplicate_error:
        return duplicate_error
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(CHART_SPEC_SCHEMA_PATH),
    }


def _check_chart_spec_no_duplicate_series_sources(chart_spec: Any) -> dict[str, Any] | None:
    """Return an error if two series reference the same (type, entity_id, attribute) source.

    A planner that returns two series from the same source is always wrong — the
    renderer would draw two identical lanes (or a hallucinated label over real
    data). This catches that class of model error before the chart reaches the
    renderer.
    """
    if not isinstance(chart_spec, dict):
        return None
    series_list = chart_spec.get("series", [])
    if not isinstance(series_list, list):
        return None
    seen: dict[tuple, int] = {}
    for i, series in enumerate(series_list):
        if not isinstance(series, dict):
            continue
        source = series.get("source")
        if not isinstance(source, dict):
            continue
        key = (source.get("type"), source.get("entity_id"), source.get("attribute"))
        if key in seen:
            return {
                "accepted": False,
                "code": "invalid_chart_spec",
                "error": (
                    f"series[{i}] duplicates the source of series[{seen[key]}]: "
                    f"type={key[0]!r} entity_id={key[1]!r} attribute={key[2]!r}"
                ),
            }
        seen[key] = i
    return None


def validate_model_provider_chart_spec_entities(
    chart_spec: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Ensure provider-produced chart specs reference only approved source entities."""
    return validate_model_provider_output_entities(chart_spec, chart_spec, source_snapshot)


def validate_model_provider_output_entities(
    planner_result: dict[str, Any],
    chart_spec: dict[str, Any],
    source_snapshot: dict[str, Any],
    approved_catalog_entity_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Ensure provider output references only approved, disclosed entity IDs.

    Validation is *structural*: it inspects the fields that actually mean "use
    this entity" — chart-spec ``series``/``overlays`` sources and persisted
    ``memory_proposals`` entity references — not free-text fields such as
    ``chart_id``, ``title``, ``notes``, ``reasoning_summary``, or axis
    metadata. An entity-shaped token in those inert fields cannot reach a data
    path (the renderer only fetches from structured sources), so flagging them
    only produced false positives — e.g. a timeline a small model named
    ``binary_sensor.kitchen_door_timeline`` after its own entity.

    Disambiguates the failure (ADR-0022): a reference to an entity absent from
    the approved catalog is a true allowlist breach
    (``model_provider_referenced_unapproved_entity``); a reference to an entity
    that is approved but was not disclosed for this job is a substitution
    (``model_provider_substituted_entity``).
    """
    approved_entity_ids = set(_source_snapshot_entity_ids(source_snapshot))
    catalog_entity_ids = set(approved_catalog_entity_ids or []) | approved_entity_ids
    structured_refs = _chart_spec_entity_ids(chart_spec)
    memory_proposal_entity_ids = _memory_proposal_entity_ids(planner_result)
    referenced_entity_ids = structured_refs["entity_ids"] | memory_proposal_entity_ids
    rejected_entity_ids = sorted(referenced_entity_ids - approved_entity_ids)
    if rejected_entity_ids or structured_refs["unsupported_source_refs"]:
        unapproved_entity_ids = sorted(set(rejected_entity_ids) - catalog_entity_ids)
        substituted_entity_ids = sorted(set(rejected_entity_ids) & catalog_entity_ids)
        if unapproved_entity_ids or structured_refs["unsupported_source_refs"]:
            code = "model_provider_referenced_unapproved_entity"
        else:
            code = "model_provider_substituted_entity"
        return {
            "accepted": False,
            "code": code,
            "approved_entity_ids": sorted(approved_entity_ids),
            "referenced_entity_ids": sorted(referenced_entity_ids),
            "rejected_entity_ids": rejected_entity_ids,
            "unapproved_entity_ids": unapproved_entity_ids,
            "substituted_entity_ids": substituted_entity_ids,
            "unsupported_source_refs": structured_refs["unsupported_source_refs"],
        }
    return {
        "accepted": True,
        "code": "accepted",
        "approved_entity_ids": sorted(approved_entity_ids),
        "referenced_entity_ids": sorted(referenced_entity_ids),
    }
