"""Snapshot assembly for job orchestration (ADR-0035 step 1).

Everything that composes a validated job snapshot for the card: the failure/
progress/clarification/complete appender family, the failure-message
composers, and the fail-closed failure-code/message sanitizers (with the
forbidden-text regexes) that keep secrets and unbounded model text out of
card-facing snapshots. Driver-only consumers: the facade's WS handlers and
pipeline drivers call these; no seam module below depends on them. Layer L1.
See docs/specs/job-orchestration-split.md.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .in_process_renderer import IN_PROCESS_RENDERER_NAME
from .job_state import append_validated_job_snapshot
from .orchestration_contracts import _source_snapshot_entities
from .semantic_memory import (
    _entity_id_to_alias_id,
    derive_alias_natural_names,
)

FORBIDDEN_WORKER_PROGRESS_TEXT = re.compile(
    r"\bBearer\s+\S+|access_token|home_assistant_token|long_lived_access_token|worker_token",
    re.IGNORECASE,
)


FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT = re.compile(
    r"\bBearer\s+\S+|access_token|home_assistant_token|long_lived_access_token|"
    r"worker_token|model_provider_token|ollama_api_key",
    re.IGNORECASE,
)


WORKER_RENDERER_NAME = "worker_renderer"


def _append_fetching_history_snapshot(job: dict[str, Any], entity_ids: list[str]) -> dict[str, Any]:
    return append_validated_job_snapshot(
        job,
        status="fetching_history",
        state_label="Fetching History",
        message="Approved entity history is being retrieved by the scaffold boundary.",
        progress_stage="approved_history_retrieval",
        progress_message="Retrieving approved fake Home Assistant history.",
        validation_status="in_progress",
        validation_summary="The scaffold is retrieving approved history before future planning.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "pass"},
            {"name": "approved_history_retrieval", "status": "in_progress"},
            {"name": "model_provider", "status": "not_called"},
            {"name": "worker", "status": "not_called"},
        ],
        entities=[{"entity_id": entity_id, "label": entity_id} for entity_id in entity_ids],
        warnings=["job_orchestration_scaffold", "approved_history_retrieval_scaffold"],
    )


def _append_clarification_answer_accepted_snapshot(
    job: dict[str, Any],
    *,
    entity_id: str,
    remember: bool,
) -> dict[str, Any]:
    warnings = [
        "job_orchestration_clarification_continuation_scaffold",
        "clarification_answer_accepted",
    ]
    if remember:
        warnings.append("semantic_memory_not_persisted_in_scaffold")
    return append_validated_job_snapshot(
        job,
        status="planning",
        state_label="Clarification Accepted",
        message="Approved clarification option accepted; approved history retrieval will continue.",
        progress_stage="clarification_answer_accepted",
        progress_message=f"Continuing with approved entity {entity_id}.",
        validation_status="pass",
        validation_summary="The returned clarification option matched an approved entity option.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "pass"},
            {"name": "clarification_answer", "status": "pass"},
            {"name": "approved_history_retrieval", "status": "not_run"},
            {"name": "model_provider", "status": "not_called"},
            {"name": "worker", "status": "not_called"},
        ],
        entities=[{"entity_id": entity_id, "label": entity_id}],
        warnings=warnings,
    )


def _append_retry_accepted_snapshot(
    job: dict[str, Any],
    *,
    failed_snapshot: dict[str, Any],
) -> dict[str, Any]:
    failure_code = failed_snapshot.get("failure", {}).get("code", "failed")
    return append_validated_job_snapshot(
        job,
        status="planning",
        state_label="Retry Accepted",
        message="Retry accepted for a failed scaffold job; approved history retrieval will run again.",
        progress_stage="job_orchestration_retry_accepted",
        progress_message=f"Retrying after scaffold failure {failure_code}.",
        validation_status="pass",
        validation_summary="The retry command targeted a failed retryable scaffold job.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "retry_command", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "not_run"},
            {"name": "approved_history_retrieval", "status": "not_run"},
            {"name": "model_provider", "status": "not_called"},
            {"name": "worker", "status": "not_called"},
        ],
        warnings=[
            "job_orchestration_retry_continuation_scaffold",
            "retry_accepted",
        ],
    )


def _append_failed_snapshot(
    job: dict[str, Any],
    *,
    code: str,
    stage: str,
    message: str,
    checks: list[dict[str, str]],
) -> dict[str, Any]:
    return append_validated_job_snapshot(
        job,
        status="failed",
        state_label="Failed",
        message=message,
        progress_stage="job_orchestration_scaffold_failed",
        progress_message=message,
        validation_status="fail",
        validation_summary="The orchestration scaffold stopped at a deterministic gate.",
        validation_checks=checks,
        failure={
            "stage": stage,
            "code": code,
            "message": message,
        },
        retry_allowed=True,
        warnings=["job_orchestration_scaffold", code, "orchestration_stopped_before_model_worker"],
    )


def _append_worker_failure_snapshot_from_planning_result(
    job: dict[str, Any],
    planning_result: dict[str, Any],
) -> dict[str, Any] | None:
    retry_policy = planning_result.get("worker_retry_policy")
    if isinstance(retry_policy, dict):
        return _append_worker_failure_snapshot(
            job,
            code=retry_policy.get("failure", {}).get("code", "worker_render_failed"),
            stage="worker_render",
            message=retry_policy.get("failure", {}).get(
                "message",
                "Worker render failed before a chart artifact was accepted.",
            ),
            retry_allowed=retry_policy.get("decision", {}).get("manual_retry_allowed") is True,
            validation_check_name="worker_failure_metadata",
            warning="worker_failure_metadata_recorded",
        )

    classification = planning_result.get("worker_transport_failure_classification")
    if isinstance(classification, dict):
        return _append_worker_failure_snapshot(
            job,
            code=classification.get("failure", {}).get("code", "worker_transport_failed"),
            stage="worker_transport",
            message=classification.get("failure", {}).get(
                "message",
                "Worker transport failed before a render result was accepted.",
            ),
            retry_allowed=classification.get("classification", {}).get("manual_retry_allowed") is True,
            validation_check_name="worker_failure_metadata",
            warning="worker_failure_metadata_recorded",
        )

    return None


def _append_codegen_failure_snapshot_from_planning_result(
    job: dict[str, Any],
    planning_result: dict[str, Any],
) -> dict[str, Any] | None:
    """Convert a fail-closed codegen result into a card-facing failed snapshot.

    ADR-0029 packet 4: codegen fails closed with a dedicated
    ``codegen_render_failed`` code (no silent trusted fallback). The failure card
    carries the final sandbox/model error code as context for the packet-5 eval.
    """
    if planning_result.get("code") != CODEGEN_RENDER_FAILED_CODE:
        return None
    codegen_failure = planning_result.get("codegen_failure")
    codegen_failure = codegen_failure if isinstance(codegen_failure, dict) else {}
    final_error_code = codegen_failure.get("final_error_code")
    stage = codegen_failure.get("stage")
    return _append_failed_snapshot(
        job,
        code=CODEGEN_RENDER_FAILED_CODE,
        stage="codegen_render",
        message=_codegen_failure_message(stage, final_error_code),
        checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "pass"},
            {"name": "model_provider", "status": "pass"},
            {"name": "approved_history_retrieval", "status": "pass"},
            {"name": "codegen_render", "status": "fail"},
        ],
    )


def _codegen_failure_message(stage: Any, final_error_code: Any) -> str:
    if final_error_code == CODEGEN_CONTEXT_OVERFLOW_CODE:
        return (
            "This request was too large for the analysis model's context window, so "
            "the chart was drawn by the built-in renderer instead. To enable the "
            "advanced renderer for large requests, increase the codegen model's "
            "context size in Ollama (raise num_ctx / OLLAMA_CONTEXT_LENGTH), ask for "
            "fewer series, or run a model/GPU with a larger context window. (The time "
            "range does not affect this — the model is sent a per-series summary, not "
            "the individual data points.)"
        )
    if stage == "generate":
        return "The model could not generate chart code for this request."
    if stage == "repair":
        return "The model could not repair the generated chart code after a sandbox error."
    if final_error_code == "unsafe_code":
        return (
            "The generated chart code still failed the sandbox safety checks "
            "after the allowed repair attempts and was rejected."
        )
    return "The generated chart code failed to render after the allowed repair attempts."


def _append_history_failure_snapshot_from_planning_result(
    job: dict[str, Any],
    planning_result: dict[str, Any],
) -> dict[str, Any] | None:
    if not planning_result.get("history_failure"):
        return None
    code = planning_result.get("code", "approved_history_unavailable")
    history_result = planning_result.get("history_result", {})
    return _append_failed_snapshot(
        job,
        code=code,
        stage="approved_history_retrieval",
        message=_history_failure_message(code, history_result),
        checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "pass"},
            {"name": "model_provider", "status": "pass"},
            {"name": "approved_history_retrieval", "status": "fail"},
            {"name": "chart_rendering", "status": "not_called"},
        ],
    )


def _history_failure_message(code: str, history_result: dict[str, Any]) -> str:
    entity_ids = []
    if isinstance(history_result, dict):
        for key in ("missing_entity_ids", "rejected_entity_ids"):
            value = history_result.get(key)
            if isinstance(value, list):
                entity_ids.extend(str(item) for item in value if isinstance(item, str))
    entity_suffix = f" ({', '.join(sorted(set(entity_ids)))})" if entity_ids else ""
    messages = {
        "no_long_term_statistics": (
            "No long-term statistics are available to chart this time range"
            f"{entity_suffix}. Statistics require an entity with a measurement state class."
        ),
        "missing_approved_history": (
            f"No approved history was found for the requested time range{entity_suffix}."
        ),
        "entity_not_in_approved_catalog": (
            f"The requested entity is not in the approved catalog{entity_suffix}."
        ),
    }
    return messages.get(
        code,
        f"Approved history could not be retrieved for the requested time range{entity_suffix}.",
    )


def _append_model_provider_failure_snapshot_from_planning_result(
    job: dict[str, Any],
    planning_result: dict[str, Any],
) -> dict[str, Any] | None:
    if planning_result.get("code") == "model_provider_planner_not_configured":
        return _append_model_provider_failure_snapshot(
            job,
            code="model_provider_planner_not_configured",
            message="Model provider planner is not configured for this Isolinear entry.",
            retry_allowed=False,
        )

    retry_policy = planning_result.get("model_provider_retry_policy")
    if not isinstance(retry_policy, dict):
        if _is_model_provider_output_failure_code(planning_result.get("code")):
            return _append_model_provider_failure_snapshot(
                job,
                code=planning_result.get("code", "model_provider_planning_failed"),
                message=_model_provider_planning_failure_message(planning_result),
                retry_allowed=False,
            )
        return None

    return _append_model_provider_failure_snapshot(
        job,
        code=retry_policy.get("failure", {}).get("code", "model_provider_planning_failed"),
        message=retry_policy.get("failure", {}).get(
            "message",
            "Model provider planning failed before a chart spec was accepted.",
        ),
        retry_allowed=retry_policy.get("decision", {}).get("manual_retry_allowed") is True,
    )


def _append_in_process_renderer_failure_snapshot_from_planning_result(
    job: dict[str, Any],
    planning_result: dict[str, Any],
) -> dict[str, Any] | None:
    if not _is_in_process_renderer_failure_code(planning_result.get("code")):
        return None
    return _append_in_process_renderer_failure_snapshot(
        job,
        code=planning_result.get("code", "in_process_renderer_failed"),
        message=_in_process_renderer_failure_message(planning_result),
    )


def _is_model_provider_output_failure_code(code: Any) -> bool:
    return code in {
        "invalid_integration_model_provider_plan",
        "invalid_model_provider_chart_spec",
        "invalid_planner_result",
        "model_provider_chart_spec_hidden_entity",
        "model_provider_referenced_unapproved_entity",
        "model_provider_substituted_entity",
        "mixed_chart_composition_unsupported",
        "model_provider_planner_not_chart_spec_ready",
        "model_provider_planning_failed",
    }


def _is_in_process_renderer_failure_code(code: Any) -> bool:
    return code in {
        "artifact_directory_unavailable",
        "artifact_png_too_large",
        "artifact_write_failed",
        "in_process_renderer_failed",
        "in_process_renderer_output_too_large",
        "invalid_artifact_id",
        "invalid_artifact_png_payload",
        "invalid_in_process_render_request",
        "invalid_in_process_render_result",
        "renderer_dependency_unavailable",
        "unsupported_chart_spec",
    }


def _model_provider_planning_failure_message(planning_result: dict[str, Any]) -> str:
    code = planning_result.get("code")
    messages = {
        "invalid_planner_result": "The model provider returned a planner result that failed schema validation.",
        "model_provider_planner_not_chart_spec_ready": (
            "The model provider did not return a chart-ready planner result."
        ),
        "invalid_model_provider_chart_spec": (
            "The model provider returned a chart spec that failed schema validation."
        ),
        "model_provider_chart_spec_hidden_entity": (
            "The model provider returned a chart spec that referenced an entity outside the approved allowlist."
        ),
        "model_provider_referenced_unapproved_entity": (
            "The model provider referenced an entity that is not on the approved allowlist."
        ),
        "model_provider_substituted_entity": (
            "The model provider substituted an entity that was not selected for this question."
        ),
        "mixed_chart_composition_unsupported": (
            "Charting numeric and binary entities together is not supported yet; ask about them separately."
        ),
        "invalid_integration_model_provider_plan": (
            "The model provider plan failed integration metadata validation."
        ),
        "model_provider_planning_failed": "Model provider planning failed before a chart spec was accepted.",
    }
    if isinstance(code, str) and code in messages:
        return messages[code]
    return "Model provider planning failed before a chart spec was accepted."


def _in_process_renderer_failure_message(planning_result: dict[str, Any]) -> str:
    code = planning_result.get("code")
    messages = {
        "artifact_directory_unavailable": "Isolinear could not open the chart artifact directory.",
        "artifact_png_too_large": "The trusted chart renderer produced an artifact that was too large.",
        "artifact_write_failed": "Isolinear could not write the rendered chart artifact.",
        "in_process_renderer_failed": "The trusted chart renderer failed before a chart artifact was accepted.",
        "in_process_renderer_output_too_large": "The trusted chart renderer produced an artifact that was too large.",
        "invalid_artifact_id": "Isolinear could not prepare a valid chart artifact target.",
        "invalid_artifact_png_payload": "The trusted chart renderer returned an invalid PNG payload.",
        "invalid_in_process_render_request": "Isolinear could not prepare a valid request for the trusted chart renderer.",
        "invalid_in_process_render_result": "The trusted chart renderer returned an invalid render result.",
        "renderer_dependency_unavailable": (
            "The trusted chart renderer dependency is not installed in this Home Assistant environment."
        ),
        "unsupported_chart_spec": "The trusted chart renderer does not support this chart spec yet.",
    }
    if isinstance(code, str) and code in messages:
        return messages[code]
    return "The trusted chart renderer failed before a chart artifact was accepted."


def _append_model_provider_failure_snapshot(
    job: dict[str, Any],
    *,
    code: str,
    message: str,
    retry_allowed: bool,
) -> dict[str, Any]:
    safe_code = _safe_model_provider_failure_code(code)
    safe_message = _safe_model_provider_failure_message(message)
    return append_validated_job_snapshot(
        job,
        status="failed",
        state_label="Failed",
        message=safe_message,
        progress_stage="model_provider_failure_snapshot_ready",
        progress_message=safe_message,
        validation_status="fail",
        validation_summary="A validated model-provider failure was converted to a card-facing failed snapshot.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "model_provider", "status": "fail"},
            {"name": "model_provider_failure_metadata", "status": "pass"},
            {"name": "manual_retry_affordance", "status": "pass" if retry_allowed else "not_allowed"},
            {"name": "automatic_retry", "status": "not_scheduled"},
        ],
        failure={
            "stage": "model_provider_planning",
            "code": safe_code,
            "message": safe_message,
        },
        retry_allowed=retry_allowed,
        warnings=[
            "model_provider_retry_backoff_policy_scaffold",
            "model_provider_metadata_not_exposed_to_card",
            "automatic_retry_not_scheduled",
        ],
    )


def _append_in_process_renderer_failure_snapshot(
    job: dict[str, Any],
    *,
    code: str,
    message: str,
) -> dict[str, Any]:
    safe_code = _safe_renderer_failure_code(code)
    safe_message = _safe_renderer_failure_message(message)
    return append_validated_job_snapshot(
        job,
        status="failed",
        state_label="Failed",
        message=safe_message,
        progress_stage="in_process_renderer_failure_snapshot_ready",
        progress_message=safe_message,
        validation_status="fail",
        validation_summary="A trusted renderer failure was converted to a card-facing failed snapshot.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "model_provider", "status": "pass"},
            {"name": "chart_rendering", "status": "fail"},
            {"name": "artifact_metadata", "status": "not_written"},
            {"name": "manual_retry_affordance", "status": "pass"},
            {"name": "automatic_retry", "status": "not_scheduled"},
        ],
        failure={
            "stage": "chart_rendering",
            "code": safe_code,
            "message": safe_message,
        },
        retry_allowed=True,
        warnings=[
            "in_process_renderer_failure_snapshot",
            "renderer_metadata_not_exposed_to_card",
            "automatic_retry_not_scheduled",
        ],
    )


def _append_worker_failure_snapshot(
    job: dict[str, Any],
    *,
    code: str,
    stage: str,
    message: str,
    retry_allowed: bool,
    validation_check_name: str,
    warning: str,
) -> dict[str, Any]:
    safe_code = _safe_worker_snapshot_failure_code(code, stage=stage)
    safe_message = _safe_worker_snapshot_failure_message(message, stage=stage)
    return append_validated_job_snapshot(
        job,
        status="failed",
        state_label="Failed",
        message=safe_message,
        progress_stage="worker_failure_snapshot_ready",
        progress_message=safe_message,
        validation_status="fail",
        validation_summary="A validated worker failure was converted to a card-facing failed snapshot.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "worker", "status": "fail"},
            {"name": validation_check_name, "status": "pass"},
            {"name": "worker_authorization_redacted", "status": "pass"},
            {"name": "manual_retry_affordance", "status": "pass" if retry_allowed else "not_allowed"},
            {"name": "automatic_retry", "status": "not_scheduled"},
        ],
        failure={
            "stage": stage,
            "code": safe_code,
            "message": safe_message,
        },
        retry_allowed=retry_allowed,
        warnings=[
            "worker_failure_snapshot_manual_retry_integration_scaffold",
            warning,
            "worker_authorization_not_exposed_to_card",
            "worker_metadata_not_exposed_to_card",
            "automatic_retry_not_scheduled",
        ],
    )


def _append_clarification_snapshot(
    job: dict[str, Any],
    *,
    message: str,
    options: list[dict[str, Any]],
    candidate_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    # Tranche 2: precompute the alias each option would save if answered with
    # "remember", keyed by option_id. Internal job state only — never serialised
    # to the card-facing snapshot. (docs/specs/semantic-alias-save-tranche2.md §2)
    suggestions: dict[str, Any] = {}
    prompt = job.get("prompt", "")
    for item in candidate_items or []:
        entity_id = item["entity_id"]
        label = item.get("friendly_name") or entity_id
        suggestions[_option_id_for_entity(entity_id)] = {
            "alias_id": _entity_id_to_alias_id(entity_id),
            "natural_names": derive_alias_natural_names(prompt, entity_id, label),
            "entity_id": entity_id,
        }
    job["alias_suggestions"] = suggestions
    return append_validated_job_snapshot(
        job,
        status="clarification_needed",
        state_label="Clarification Needed",
        message=message,
        progress_stage="entity_selection_clarification",
        progress_message=message,
        validation_status="blocked",
        validation_summary="The orchestration scaffold refused to guess an entity from an ambiguous prompt.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "clarification_needed"},
            {"name": "approved_history_retrieval", "status": "not_run"},
            {"name": "model_provider", "status": "not_called"},
            {"name": "worker", "status": "not_called"},
        ],
        clarification={
            "question_id": "select_approved_entity",
            "message": message,
            "reason": "The prompt did not name a specific approved entity.",
            "options": options,
        },
        warnings=[
            "job_orchestration_scaffold",
            "entity_selection_requires_clarification",
            "history_not_read_before_clarification",
        ],
    )


CODEGEN_RENDER_FAILED_CODE = "codegen_render_failed"


# The codegen prompt was truncated by the model's context window (ADR-0031 D9
# prompt-summary discipline keeps normal requests well under it; this is the
# safety net for pathological requests / a shrunk num_ctx / a small model).
CODEGEN_CONTEXT_OVERFLOW_CODE = "codegen_context_overflow"


def _append_artifact_complete_snapshot(
    job: dict[str, Any],
    artifact: dict[str, Any],
    *,
    worker_dispatch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chart = {
        "title": artifact["title"],
        "image_url": artifact["image_url"],
        "time_range": artifact["time_range"],
        "series": deepcopy(artifact["series"]),
        "overlays": deepcopy(artifact["overlays"]),
    }
    # Optional ADR-0027 fields: caption summary and renderer color manifest.
    if isinstance(artifact.get("summary"), str) and artifact["summary"].strip():
        chart["summary"] = artifact["summary"].strip()
    # Optional ADR-0031 field: the grounded analysis answer, rendered by the card
    # under the caption.
    if isinstance(artifact.get("answer_text"), str) and artifact["answer_text"].strip():
        chart["answer_text"] = artifact["answer_text"].strip()
    # ADR-0031 D8a: grounding check result threaded to the card.
    if artifact.get("answer_verification") in ("verified", "unverified"):
        chart["answer_verification"] = artifact["answer_verification"]
    if isinstance(artifact.get("legend"), list) and artifact["legend"]:
        chart["legend"] = deepcopy(artifact["legend"])
    # Optional ADR-0030 fields: how the chart was rendered + surfaced fallback.
    if isinstance(artifact.get("render_path"), str):
        chart["render_path"] = artifact["render_path"]
    if isinstance(artifact.get("render_fallback_reason"), str):
        chart["render_fallback_reason"] = artifact["render_fallback_reason"]
    worker_rendered = worker_dispatch is not None
    worker_artifact_rendered = artifact.get("render_metadata", {}).get("renderer") == WORKER_RENDERER_NAME
    in_process_rendered = artifact.get("render_metadata", {}).get("renderer") == IN_PROCESS_RENDERER_NAME
    return append_validated_job_snapshot(
        job,
        status="complete",
        state_label="Complete",
        message=(
            (
                "Worker-rendered chart artifact is ready for the dashboard card."
                if worker_artifact_rendered
                else (
                    "Worker render result is recorded and placeholder chart artifact metadata is ready for the "
                    "dashboard card."
                )
            )
            if worker_rendered
            else (
                "In-process trusted Pillow render is ready for the dashboard card."
                if in_process_rendered
                else "Placeholder chart artifact metadata is ready for the dashboard card."
            )
        ),
        progress_stage="job_orchestration_artifact_storage_ready",
        progress_message=(
            (
                "Worker dispatch metadata and served chart artifact metadata are stored."
                if worker_artifact_rendered
                else "Worker dispatch metadata is stored with the scaffold artifact metadata."
            )
            if worker_rendered
            else (
                "Rendered chart artifact metadata is stored for the first real slice."
                if in_process_rendered
                else "Scaffold artifact metadata is stored for future rendering."
            )
        ),
        validation_status="pass",
        validation_summary=(
            (
                "The worker dispatch recorded a schema-valid render result and served PNG artifact."
                if worker_artifact_rendered
                else (
                    "The worker dispatch scaffold recorded a schema-valid worker render result and placeholder chart "
                    "metadata."
                )
            )
            if worker_rendered
            else (
                "The first real vertical slice rendered a schema-valid PNG chart in process."
                if in_process_rendered
                else "The artifact storage scaffold created schema-valid placeholder chart metadata."
            )
        ),
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "integration_artifact_metadata", "status": "pass"},
            {"name": "worker", "status": "pass" if worker_rendered else "not_called"},
            {
                "name": "chart_rendering",
                "status": "pass" if worker_rendered or in_process_rendered else "not_called",
            },
        ],
        chart=chart,
        entities=[
            {"entity_id": item["entity_id"], "label": item["label"]}
            for item in artifact["series"]
        ],
        aliases=job.get("alias_display") or None,
        warnings=(
            (
                [
                    "first_real_vertical_slice",
                    "worker_renderer",
                    "worker_rendered_artifact_serving",
                    "worker_render_result_recorded",
                    "chart_artifact_served_url",
                ]
                if worker_artifact_rendered
                else [
                    "artifact_storage_scaffold",
                    "placeholder_chart_artifact",
                    "worker_dispatch_rendering_scaffold",
                    "worker_render_result_recorded",
                    "integration_chart_artifact_file_not_written",
                ]
            )
            if worker_rendered
            else (
                [
                    "first_real_vertical_slice",
                    "in_process_pillow_renderer",
                    "chart_artifact_served_url",
                    "worker_not_called",
                ]
                if in_process_rendered
                else [
                    "artifact_storage_scaffold",
                    "placeholder_chart_artifact",
                    "worker_not_called",
                    "chart_rendering_not_started",
                ]
            )
        ),
    )


def _worker_failure_code(render_result: Any) -> str:
    if isinstance(render_result, dict):
        error = render_result.get("error")
        if isinstance(error, dict) and isinstance(error.get("code"), str) and error["code"].strip():
            return _safe_worker_failure_code(error["code"])
    return "worker_render_failed"


def _model_provider_failure_contains_forbidden_material(provider_response: dict[str, Any]) -> bool:
    return any(
        FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT.search(value)
        for value in (
            provider_response.get("code"),
            provider_response.get("message"),
        )
        if isinstance(value, str)
    )


def _safe_model_provider_failure_code(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "model_provider_planning_failed"
    stripped = value.strip()
    if FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT.search(stripped):
        return "model_provider_planning_failed"
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stripped).strip("_")
    return normalized[:80] if normalized else "model_provider_planning_failed"


def _safe_model_provider_failure_message(value: Any) -> str:
    fallback = "Model provider planning failed before a chart spec was accepted."
    if not isinstance(value, str) or not value.strip():
        return fallback
    stripped = re.sub(r"\s+", " ", value.strip())
    if FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT.search(stripped):
        return fallback
    return stripped[:240] if stripped else fallback


def _safe_worker_failure_code(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "worker_render_failed"
    stripped = value.strip()
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(stripped):
        return "worker_render_failed"
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stripped).strip("_")
    return normalized[:80] if normalized else "worker_render_failed"


def _safe_worker_transport_failure_code(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "worker_transport_failed"
    stripped = value.strip()
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(stripped):
        return "worker_transport_failed"
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stripped).strip("_")
    return normalized[:80] if normalized else "worker_transport_failed"


def _safe_worker_transport_failure_message(value: Any) -> str:
    fallback = "Worker transport failed before a render result was accepted."
    if not isinstance(value, str) or not value.strip():
        return fallback
    stripped = re.sub(r"\s+", " ", value.strip())
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(stripped):
        return fallback
    return stripped[:240] if stripped else fallback


def _safe_worker_snapshot_failure_code(value: Any, *, stage: str) -> str:
    if stage == "worker_transport":
        return _safe_worker_transport_failure_code(value)
    return _safe_worker_failure_code(value)


def _safe_worker_snapshot_failure_message(value: Any, *, stage: str) -> str:
    fallback = (
        "Worker transport failed before a render result was accepted."
        if stage == "worker_transport"
        else "Worker render failed before a chart artifact was accepted."
    )
    if not isinstance(value, str) or not value.strip():
        return fallback
    stripped = re.sub(r"\s+", " ", value.strip())
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(stripped):
        return fallback
    return stripped[:240] if stripped else fallback


def _safe_renderer_failure_code(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "in_process_renderer_failed"
    stripped = value.strip()
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(stripped) or FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT.search(stripped):
        return "in_process_renderer_failed"
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stripped).strip("_")
    return normalized[:80] if normalized else "in_process_renderer_failed"


def _safe_renderer_failure_message(value: Any) -> str:
    fallback = "The trusted chart renderer failed before a chart artifact was accepted."
    if not isinstance(value, str) or not value.strip():
        return fallback
    stripped = re.sub(r"\s+", " ", value.strip())
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(stripped) or FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT.search(stripped):
        return fallback
    return stripped[:240] if stripped else fallback


def _worker_transport_failure_family(code: str) -> str:
    if code == "worker_connection_error":
        return "connection"
    if code == "worker_http_error":
        return "http"
    if code == "worker_response_error":
        return "malformed_response"
    if code == "worker_renderer_unavailable":
        return "unavailable"
    return "unknown"


def _snapshot_entities(catalog_items: list[dict[str, Any]], entity_ids: list[str]) -> list[dict[str, str]]:
    by_entity = {item["entity_id"]: item for item in catalog_items}
    entities = []
    for entity_id in entity_ids:
        item = by_entity.get(entity_id, {})
        entities.append(
            {
                "entity_id": entity_id,
                "label": item.get("friendly_name") or entity_id,
            }
        )
    return entities


def _clarification_option_for_item(
    item: dict[str, Any], *, can_remember: bool = False
) -> dict[str, Any]:
    # ``can_remember`` is opt-in per clarification type (Tranche 2): only the
    # select_approved_entity flow has a defined save path, so it passes True
    # explicitly. Future clarification types (threshold/state-interval) get the
    # safe default until their save flow is specified, rather than silently
    # inheriting a rememberable option from this shared builder.
    entity_id = item["entity_id"]
    label = item.get("friendly_name") or entity_id
    return {
        "option_id": _option_id_for_entity(entity_id),
        "label": label,
        "description": f"Use {entity_id}.",
        "can_remember": can_remember,
    }


def _option_id_for_entity(entity_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", entity_id).strip("_")


def _pending_clarification_for_job(job: dict[str, Any]) -> dict[str, Any]:
    snapshot = job.get("latest_snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("status") != "clarification_needed":
        return {
            "accepted": False,
            "code": "job_not_awaiting_clarification",
        }
    clarification = snapshot.get("clarification")
    if not isinstance(clarification, dict) or not isinstance(clarification.get("options"), list):
        return {
            "accepted": False,
            "code": "job_not_awaiting_clarification",
        }
    return {
        "accepted": True,
        "code": "accepted",
        "snapshot": snapshot,
        "clarification": clarification,
    }


def _retryable_failure_for_job(job: dict[str, Any]) -> dict[str, Any]:
    snapshot = job.get("latest_snapshot")
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("status") != "failed"
        or snapshot.get("retry_allowed") is not True
    ):
        return {
            "accepted": False,
            "code": "job_not_retryable",
        }
    return {
        "accepted": True,
        "code": "accepted",
        "snapshot": snapshot,
    }


def _clarification_answer_summary(
    command: dict[str, Any],
    entity_id: str | None,
) -> dict[str, Any]:
    return {
        "question_id": command["question_id"],
        "option_id": command["option_id"],
        "remember": command["remember"],
        "entity_id": entity_id,
    }


def _snapshot_ids(job: dict[str, Any]) -> list[str]:
    return [
        snapshot["snapshot_id"]
        for snapshot in job.get("snapshots", [])
        if isinstance(snapshot, dict)
    ]


def _failure_message(history_result: dict[str, Any]) -> str:
    code = history_result["code"]
    if code == "entity_not_in_approved_catalog":
        rejected = ", ".join(history_result.get("rejected_entity_ids", []))
        return f"Prompt referenced entities outside the approved catalog: {rejected}."
    if code == "missing_approved_history":
        missing = ", ".join(history_result.get("missing_entity_ids", []))
        return f"Approved history is missing for: {missing}."
    return "Approved history retrieval failed before future planning."


def _artifact_series(source_snapshot: dict[str, Any]) -> list[dict[str, str]]:
    result = []
    for index, entity in enumerate(_source_snapshot_entities(source_snapshot), start=1):
        result.append(
            {
                "series_id": f"series-{index:03d}",
                "label": entity["label"],
                "entity_id": entity["entity_id"],
            }
        )
    return result


def _artifact_title(job: dict[str, Any], source_snapshot: dict[str, Any]) -> str:
    entities = source_snapshot.get("entities", [])
    if isinstance(entities, list) and len(entities) == 1 and isinstance(entities[0], dict):
        label = entities[0].get("label")
        if isinstance(label, str) and label.strip():
            return f"{label} Chart"
    prompt = job.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return f"Isolinear Chart: {prompt.strip()}"
    return "Isolinear Chart"
