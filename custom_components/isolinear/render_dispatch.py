"""Render dispatch for job orchestration (ADR-0035 step 1).

How a validated plan becomes a PNG — the seam where invariant #6 lives:
the integration-orchestrated codegen loop (generate -> worker sandbox ->
bounded repair -> grounding gate) with its config readers, the chart-spec
worker dispatch, the trusted Pillow in-process fallback (always surfaced via
render_path/render_fallback_reason, never silent), worker artifact/progress
recording, the ADR-0033 precomputed overlay bands, the artifact-metadata
builders, and worker transport-failure classification + retry policy.
Layer L2. See docs/specs/job-orchestration-split.md.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from .answer_grounding import run_grounding_check as _run_grounding_check
from .artifact_serving import (
    prepare_png_artifact,
    remove_png_artifact,
    write_png_artifact,
)
from .const import (
    DOMAIN,
    RENDER_MODE_CODEGEN,
    RENDER_PATH_PILLOW,
)
from copy import deepcopy
from datetime import datetime
from .history_dispatch import (
    _history_series_for_render_plan,
    _history_series_with_epoch_ms,
    _history_window_end_dt,
)
from .in_process_renderer import (
    IN_PROCESS_RENDERER_NAME,
    _OVERLAY_COLORS,
    _binary_on_regions,
    _categorical_overlay_states,
    _rgb_to_hex,
    first_real_vertical_slice_enabled,
    render_in_process_chart,
)
from .job_state import store_validated_job_snapshot
from .model_provider import (
    configured_codegen_model,
    configured_render_path,
    get_model_provider_codegen,
)
from .orchestration_contracts import (
    WORKER_PROGRESS_SCHEMA_PATH,
    validate_artifact_metadata_contract,
    validate_render_request_contract,
    validate_render_result_contract,
    validate_worker_dispatch_contract,
    validate_worker_progress_contract,
    validate_worker_retry_policy_contract,
    validate_worker_transport_failure_classification_contract,
    validate_worker_transport_request_contract,
)
from .orchestration_store import (
    _store_validated_artifact_metadata,
    _store_validated_model_provider_plan,
    _store_validated_render_plan,
    _store_validated_worker_progress_event,
    _store_validated_worker_retry_policy,
    _store_validated_worker_transport_failure_classification,
    _subscription_ids_for_job,
    _worker_retry_policy_attempt_number,
    _worker_transport_failure_classification_attempt_number,
)
from .snapshot_assembly import (
    _artifact_series,
    _artifact_title,
    CODEGEN_CONTEXT_OVERFLOW_CODE,
    CODEGEN_RENDER_FAILED_CODE,
    FORBIDDEN_WORKER_PROGRESS_TEXT,
    WORKER_RENDERER_NAME,
    _safe_worker_failure_code,
    _safe_worker_transport_failure_code,
    _safe_worker_transport_failure_message,
    _worker_failure_code,
    _worker_transport_failure_family,
)
from typing import Any
from .worker_renderer import (
    build_worker_transport_request,
    get_worker_render_client,
    redacted_worker_transport_request,
    worker_client_metadata,
    worker_client_token,
)

_LOGGER = logging.getLogger(__name__)

MAX_WORKER_PROGRESS_EVENTS = 5


def _accept_in_process_render_result(
    store: dict[str, Any],
    *,
    in_process_render_result: dict[str, Any],
    model_provider_result: dict[str, Any],
    render_plan: dict[str, Any],
    render_plan_validation: dict[str, Any],
) -> dict[str, Any]:
    """Store + return the accepted in-process render (direct or codegen fallback)."""
    model_provider_plan = model_provider_result.get("model_provider_plan")
    artifact = in_process_render_result["artifact"]
    if model_provider_plan is not None:
        _store_validated_model_provider_plan(store, model_provider_plan)
    _store_validated_artifact_metadata(store, artifact)
    _store_validated_render_plan(store, render_plan)
    return {
        "accepted": True,
        "code": "accepted",
        "artifact": deepcopy(artifact),
        "render_plan": deepcopy(render_plan),
        "model_provider_plan": deepcopy(model_provider_plan) if model_provider_plan is not None else None,
        "worker_dispatch": None,
        "worker_progress_events": [],
        "in_process_render": deepcopy(in_process_render_result["in_process_render"]),
        "model_provider_called": model_provider_result.get("model_provider_called", False),
        "worker_called": False,
        "chart_rendering_called": True,
        "chart_artifact_written": in_process_render_result.get("chart_artifact_written", False),
        "worker_progress_streaming_called": False,
        "artifact_validation": in_process_render_result.get("artifact_validation"),
        "model_provider_validation": model_provider_result.get("validation"),
        "render_plan_validation": render_plan_validation,
        "worker_dispatch_validation": None,
        "worker_progress_validation": None,
    }


def _codegen_fallback_reason(
    hass: Any,
    entry_id: str,
    worker_dispatch_result: dict[str, Any],
) -> str | None:
    """Reason string when a failed worker dispatch should fall back to Pillow.

    ADR-0030 fallback triggers: a codegen failure (generation failure / repair
    exhaustion, surfaced as ``codegen_render_failed``) or a worker transport
    fault while the codegen path is active. Returns ``None`` when the failure
    is not a codegen-path failure (e.g. the legacy safe worker path, or
    integration-side validation bugs, which should still fail loudly).
    """
    if get_model_provider_codegen(hass, entry_id) is None:
        return None
    if worker_dispatch_result.get("code") == CODEGEN_RENDER_FAILED_CODE:
        codegen_failure = worker_dispatch_result.get("codegen_failure")
        if isinstance(codegen_failure, dict):
            final_error_code = codegen_failure.get("final_error_code")
            if isinstance(final_error_code, str) and final_error_code:
                return final_error_code
        return CODEGEN_RENDER_FAILED_CODE
    if worker_dispatch_result.get("worker_transport_failure_classification") is not None:
        code = worker_dispatch_result.get("code")
        return code if isinstance(code, str) and code else "worker_transport_failure"
    return None


def _record_in_process_render(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    artifact: dict[str, Any],
    render_plan: dict[str, Any],
    model_provider_result: dict[str, Any],
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    """Render through the trusted in-process Pillow renderer.

    Runs when no worker is configured, when ``render_path: "pillow"`` is the
    explicit choice, or as the surfaced codegen fallback (``fallback_reason``
    set — ADR-0030: no silent fallback, the reason rides the artifact/chart).
    """
    if not first_real_vertical_slice_enabled(hass, entry_id):
        return {"enabled": False}
    if (
        fallback_reason is None
        and get_worker_render_client(hass, entry_id) is not None
        and _configured_render_path(hass, entry_id) != RENDER_PATH_PILLOW
    ):
        return {"enabled": False}
    if model_provider_result.get("model_provider_plan") is None:
        return {"enabled": False}

    render_request = _build_worker_render_request(
        store,
        hass=hass,
        entry_id=entry_id,
        render_plan=render_plan,
    )
    render_request_validation = validate_render_request_contract(render_request)
    if not render_request_validation["accepted"]:
        return {
            "enabled": True,
            "accepted": False,
            "code": "invalid_in_process_render_request",
            "validation": render_request_validation,
            "chart_rendering_called": False,
        }

    render_response = render_in_process_chart(render_request)
    render_result = render_response.get("render_result") if isinstance(render_response, dict) else None
    render_result_validation = validate_render_result_contract(render_result)
    if not render_result_validation["accepted"]:
        return {
            "enabled": True,
            "accepted": False,
            "code": "invalid_in_process_render_result",
            "validation": render_result_validation,
            "chart_rendering_called": True,
        }
    if not isinstance(render_response, dict) or not render_response.get("accepted"):
        return {
            "enabled": True,
            "accepted": False,
            "code": render_response.get("code", "in_process_renderer_failed")
            if isinstance(render_response, dict)
            else "in_process_renderer_failed",
            "validation": render_result_validation,
            "chart_rendering_called": True,
            "in_process_render": render_response if isinstance(render_response, dict) else None,
        }
    if not isinstance(render_result, dict) or render_result.get("status") != "success":
        return {
            "enabled": True,
            "accepted": False,
            "code": "in_process_renderer_failed",
            "validation": render_result_validation,
            "chart_rendering_called": True,
            "in_process_render": render_response,
        }

    prepared_artifact = prepare_png_artifact(
        hass,
        entry_id,
        artifact_id=artifact["artifact_id"],
        png_bytes=render_response.get("png_bytes"),
    )
    if not prepared_artifact["accepted"]:
        return {
            "enabled": True,
            "accepted": False,
            "code": prepared_artifact["code"],
            "validation": prepared_artifact,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "in_process_render": render_response,
        }

    render_result = deepcopy(render_result)
    render_result["image_path"] = prepared_artifact["artifact_path"]
    render_result_validation = validate_render_result_contract(render_result)
    if not render_result_validation["accepted"]:
        return {
            "enabled": True,
            "accepted": False,
            "code": "invalid_in_process_render_result",
            "validation": render_result_validation,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "in_process_render": render_response,
        }

    rendered_artifact = _build_in_process_artifact_metadata(
        artifact,
        render_result=render_result,
        image_url=prepared_artifact["image_url"],
        fallback_reason=fallback_reason,
    )
    artifact_validation = validate_artifact_metadata_contract(rendered_artifact)
    if not artifact_validation["accepted"]:
        return {
            "enabled": True,
            "accepted": False,
            "code": "invalid_in_process_artifact_metadata",
            "validation": artifact_validation,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "in_process_render": render_response,
        }

    artifact_write = write_png_artifact(
        hass,
        entry_id,
        artifact_id=artifact["artifact_id"],
        png_bytes=render_response.get("png_bytes"),
    )
    if not artifact_write["accepted"]:
        return {
            "enabled": True,
            "accepted": False,
            "code": artifact_write["code"],
            "validation": artifact_write,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "in_process_render": {
                **render_response,
                "render_result": render_result,
            },
        }

    return {
        "enabled": True,
        "accepted": True,
        "code": "in_process_render_recorded",
        "artifact": rendered_artifact,
        "artifact_validation": artifact_validation,
        "render_result_validation": render_result_validation,
        "in_process_render": {
            "renderer": render_response["renderer"],
            "render_result": render_result,
            "png_byte_count": render_response["png_byte_count"],
            "image_url": artifact_write["image_url"],
            "artifact_path": artifact_write["artifact_path"],
            "image_url_prefix": "/api/isolinear/artifacts",
        },
        "chart_rendering_called": True,
        "chart_artifact_written": True,
    }


def _record_worker_rendered_artifact(
    hass: Any,
    entry_id: str,
    *,
    artifact: dict[str, Any],
    render_result: dict[str, Any],
    render_path: str | None = None,
    answer_verification: str | None = None,
    withheld_answer: bool = False,
) -> dict[str, Any]:
    png_result = _worker_png_bytes_from_render_result(render_result)
    if not png_result["accepted"]:
        return png_result

    prepared_artifact = prepare_png_artifact(
        hass,
        entry_id,
        artifact_id=artifact["artifact_id"],
        png_bytes=png_result["png_bytes"],
    )
    if not prepared_artifact["accepted"]:
        return {
            "accepted": False,
            "code": prepared_artifact["code"],
            "validation": prepared_artifact,
        }

    sanitized_render_result = deepcopy(render_result)
    sanitized_render_result.pop("image_bytes_base64", None)
    sanitized_render_result["image_path"] = prepared_artifact["artifact_path"]
    render_result_validation = validate_render_result_contract(sanitized_render_result)
    if not render_result_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_render_result",
            "validation": render_result_validation,
        }

    rendered_artifact = _build_worker_artifact_metadata(
        artifact,
        render_result=sanitized_render_result,
        image_url=prepared_artifact["image_url"],
        render_path=render_path,
        answer_verification=answer_verification,
        withheld_answer=withheld_answer,
    )
    artifact_validation = validate_artifact_metadata_contract(rendered_artifact)
    if not artifact_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_artifact_metadata",
            "validation": artifact_validation,
        }

    artifact_write = write_png_artifact(
        hass,
        entry_id,
        artifact_id=artifact["artifact_id"],
        png_bytes=png_result["png_bytes"],
    )
    if not artifact_write["accepted"]:
        return {
            "accepted": False,
            "code": artifact_write["code"],
            "validation": artifact_write,
        }

    return {
        "accepted": True,
        "code": "worker_rendered_artifact_recorded",
        "artifact": rendered_artifact,
        "render_result": sanitized_render_result,
        "artifact_validation": artifact_validation,
        "render_result_validation": render_result_validation,
        "artifact_write": artifact_write,
        "chart_artifact_written": True,
    }


def _rollback_worker_rendered_artifact(
    hass: Any,
    entry_id: str,
    artifact_result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(artifact_result, dict) or not artifact_result.get("chart_artifact_written"):
        return None
    artifact = artifact_result.get("artifact")
    if not isinstance(artifact, dict) or not isinstance(artifact.get("artifact_id"), str):
        return None
    return remove_png_artifact(hass, entry_id, artifact_id=artifact["artifact_id"])


def _worker_png_bytes_from_render_result(render_result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(render_result, dict):
        return {
            "accepted": False,
            "code": "invalid_worker_render_result",
        }
    if render_result.get("image_mime_type") != "image/png":
        return {
            "accepted": False,
            "code": "invalid_worker_image_mime_type",
            "validation": {
                "accepted": False,
                "code": "invalid_worker_image_mime_type",
                "expected": "image/png",
                "observed": render_result.get("image_mime_type"),
            },
        }

    encoded = render_result.get("image_bytes_base64")
    if not isinstance(encoded, str) or not encoded.strip():
        return {
            "accepted": False,
            "code": "missing_worker_image_bytes",
            "validation": {
                "accepted": False,
                "code": "missing_worker_image_bytes",
            },
        }

    try:
        png_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return {
            "accepted": False,
            "code": "invalid_worker_image_bytes",
            "validation": {
                "accepted": False,
                "code": "invalid_worker_image_bytes",
            },
        }
    return {
        "accepted": True,
        "code": "accepted",
        "png_bytes": png_bytes,
    }


def _record_worker_progress_events(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    worker: dict[str, Any],
    worker_authorization: str,
    request_id: str,
    progress_payloads: Any,
) -> dict[str, Any]:
    forbidden_text_values = [worker_authorization]
    if worker_authorization.startswith("Bearer "):
        forbidden_text_values.append(worker_authorization.removeprefix("Bearer ").strip())
    payload_validation = _normalize_worker_progress_payloads(
        progress_payloads,
        forbidden_text_values=forbidden_text_values,
    )
    if not payload_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_progress",
            "validation": payload_validation,
            "worker_progress_streaming_called": False,
        }

    normalized_payloads = payload_validation["progress_payloads"]
    if not normalized_payloads:
        return {
            "accepted": True,
            "code": "worker_progress_not_reported",
            "worker_progress_events": [],
            "worker_progress_streaming_called": False,
            "validation": payload_validation,
        }

    stored_events = []
    for payload in normalized_payloads:
        snapshot = _build_worker_progress_snapshot(job, payload)
        event = _build_worker_progress_event(
            store,
            hass=hass,
            entry_id=entry_id,
            job=job,
            worker=worker,
            worker_authorization=worker_authorization,
            request_id=request_id,
            payload=payload,
            snapshot=snapshot,
        )
        progress_validation = validate_worker_progress_contract(event)
        if not progress_validation["accepted"]:
            return {
                "accepted": False,
                "code": "invalid_integration_worker_progress",
                "validation": progress_validation,
                "worker_progress_streaming_called": True,
            }

        snapshot_result = store_validated_job_snapshot(job, snapshot)
        if not snapshot_result["accepted"]:
            return {
                "accepted": False,
                "code": "invalid_integration_worker_progress",
                "validation": snapshot_result,
                "worker_progress_streaming_called": True,
            }
        job["next_snapshot_number"] += 1
        _store_validated_worker_progress_event(store, event)
        stored_events.append(deepcopy(event))

    return {
        "accepted": True,
        "code": "worker_progress_recorded",
        "worker_progress_events": stored_events,
        "worker_progress_streaming_called": True,
        "validation": {
            "accepted": True,
            "code": "accepted",
            "event_count": len(stored_events),
            "schema": str(WORKER_PROGRESS_SCHEMA_PATH),
        },
    }


def _normalize_worker_progress_payloads(
    progress_payloads: Any,
    *,
    forbidden_text_values: list[str] | None = None,
) -> dict[str, Any]:
    if progress_payloads is None:
        return {
            "accepted": True,
            "code": "worker_progress_not_reported",
            "progress_payloads": [],
        }
    if not isinstance(progress_payloads, list):
        return {
            "accepted": False,
            "code": "invalid_worker_progress_payloads",
            "error": "worker progress payloads must be a list",
        }
    if len(progress_payloads) > MAX_WORKER_PROGRESS_EVENTS:
        return {
            "accepted": False,
            "code": "too_many_worker_progress_payloads",
            "max_worker_progress_events": MAX_WORKER_PROGRESS_EVENTS,
            "observed_worker_progress_events": len(progress_payloads),
        }

    normalized = []
    for index, payload in enumerate(progress_payloads, start=1):
        if not isinstance(payload, dict):
            return {
                "accepted": False,
                "code": "invalid_worker_progress_payload",
                "path": f"progress_events[{index - 1}]",
                "error": "worker progress payload must be an object",
            }
        sequence = payload.get("sequence", index)
        stage = payload.get("stage")
        message = payload.get("message")
        percent_complete = payload.get("percent_complete")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            return {
                "accepted": False,
                "code": "invalid_worker_progress_sequence",
                "path": f"progress_events[{index - 1}].sequence",
            }
        if not isinstance(stage, str) or not stage.strip():
            return {
                "accepted": False,
                "code": "invalid_worker_progress_stage",
                "path": f"progress_events[{index - 1}].stage",
            }
        if not isinstance(message, str) or not message.strip():
            return {
                "accepted": False,
                "code": "invalid_worker_progress_message",
                "path": f"progress_events[{index - 1}].message",
            }
        if _worker_progress_text_contains_forbidden_material(stage, forbidden_text_values):
            return {
                "accepted": False,
                "code": "forbidden_worker_progress_text",
                "path": f"progress_events[{index - 1}].stage",
            }
        if _worker_progress_text_contains_forbidden_material(message, forbidden_text_values):
            return {
                "accepted": False,
                "code": "forbidden_worker_progress_text",
                "path": f"progress_events[{index - 1}].message",
            }
        if (
            not isinstance(percent_complete, (int, float))
            or isinstance(percent_complete, bool)
            or percent_complete < 0
            or percent_complete > 100
        ):
            return {
                "accepted": False,
                "code": "invalid_worker_progress_percent",
                "path": f"progress_events[{index - 1}].percent_complete",
            }
        normalized.append(
            {
                "sequence": sequence,
                "stage": stage.strip(),
                "message": message.strip(),
                "percent_complete": percent_complete,
            }
        )

    return {
        "accepted": True,
        "code": "accepted",
        "progress_payloads": normalized,
    }


def _worker_progress_text_contains_forbidden_material(
    value: str,
    forbidden_text_values: list[str] | None,
) -> bool:
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(value):
        return True
    for forbidden in forbidden_text_values or []:
        if isinstance(forbidden, str) and forbidden.strip() and forbidden.strip() in value:
            return True
    return False


def _build_worker_progress_snapshot(job: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    snapshot_number = job["next_snapshot_number"]
    return {
        "snapshot_id": f"{job['job_id']}-snapshot-{snapshot_number:03d}",
        "job_id": job["job_id"],
        "status": "rendering",
        "prompt": job["prompt"],
        "state_label": "Rendering",
        "message": payload["message"],
        "progress": {
            "stage": payload["stage"],
            "message": payload["message"],
        },
        "validation": {
            "status": "in_progress",
            "summary": "Worker progress validates before snapshot storage.",
            "checks": [
                {"name": "worker_progress_payload", "status": "pass"},
                {"name": "worker_authorization_redacted", "status": "pass"},
                {"name": "integration_job_snapshot", "status": "pass"},
            ],
        },
        "warnings": [
            "worker_progress_streaming_scaffold",
            "worker_authorization_redacted",
            "integration_chart_artifact_file_not_written",
        ],
    }


def _build_worker_progress_event(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    worker: dict[str, Any],
    worker_authorization: str,
    request_id: str,
    payload: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    event_number = store["next_worker_progress_event_number"]
    event_id = f"{store['entry_id']}-worker-progress-{event_number:03d}"
    return {
        "event_id": event_id,
        "type": "isolinear_worker_progress",
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "worker": {
            "type": worker.get("type") or "http_json_worker",
            "role": worker.get("role") or "renderer",
            "endpoint_url": worker.get("endpoint_url") or "",
            "api_version": worker.get("api_version") or 1,
            "authorization": "Bearer <redacted>" if worker_authorization.startswith("Bearer ") else "<missing>",
        },
        "request_id": request_id,
        "sequence": payload["sequence"],
        "stage": payload["stage"],
        "message": payload["message"],
        "percent_complete": payload["percent_complete"],
        "subscription_ids": _subscription_ids_for_job(hass, entry_id, job["job_id"]),
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot": deepcopy(snapshot),
        "validation": {
            "status": "pass",
            "summary": "Worker progress payload and rendering snapshot validate before storage.",
            "checks": [
                {"name": "worker_progress_payload", "status": "pass"},
                {"name": "integration_worker_progress_schema", "status": "pass"},
                {"name": "integration_job_snapshot_schema", "status": "pass"},
                {"name": "worker_authorization_redacted", "status": "pass"},
            ],
        },
        "warnings": [
            "worker_progress_streaming_scaffold",
            "worker_authorization_redacted",
            "bounded_in_memory_progress_event",
        ],
    }


def _record_worker_dispatch(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    artifact: dict[str, Any],
    render_plan: dict[str, Any],
    serve_artifact: bool = False,
) -> dict[str, Any]:
    worker_client = get_worker_render_client(hass, entry_id)
    if worker_client is None:
        return {
            "accepted": True,
            "code": "worker_renderer_not_configured",
            "worker_called": False,
            "chart_rendering_called": False,
            "worker_progress_streaming_called": False,
            "worker_dispatch": None,
            "worker_progress_events": [],
        }

    token = worker_client_token(worker_client)
    worker_summary = {
        "worker": worker_client_metadata(worker_client),
        "authorization": "Bearer <redacted>" if token else "<missing>",
    }
    if token is None:
        return {
            "accepted": False,
            "code": "worker_renderer_token_missing",
            "worker_called": False,
            "chart_rendering_called": False,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
        }

    # ADR-0029 packet 4: when the opt-in codegen path is enabled (a codegen
    # client was installed by setup_model_provider_codegen), the render step is
    # replaced by model-generated matplotlib + an integration-orchestrated repair
    # loop. Planning, allowlist enforcement, and render-family routing are
    # upstream and unchanged; only the render step differs.
    codegen_client = get_model_provider_codegen(hass, entry_id)
    if codegen_client is not None:
        return _record_codegen_worker_dispatch(
            store,
            hass=hass,
            entry_id=entry_id,
            job=job,
            source_snapshot=source_snapshot,
            artifact=artifact,
            render_plan=render_plan,
            serve_artifact=serve_artifact,
            worker_client=worker_client,
            codegen_client=codegen_client,
            token=token,
            worker_summary=worker_summary,
        )

    render_request = _build_worker_render_request(
        store,
        hass=hass,
        entry_id=entry_id,
        render_plan=render_plan,
    )
    render_request_validation = validate_render_request_contract(render_request)
    if not render_request_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_render_request",
            "validation": render_request_validation,
            "worker_called": False,
            "chart_rendering_called": False,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
        }

    dispatch_number = store["next_worker_dispatch_number"]
    transport_request = build_worker_transport_request(
        render_request,
        request_id=f"{store['entry_id']}-worker-transport-{dispatch_number:03d}",
        worker_token=token,
    )
    transport_validation = validate_worker_transport_request_contract(transport_request)
    if not transport_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_transport_request",
            "validation": transport_validation,
            "worker_called": False,
            "chart_rendering_called": False,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
        }

    render_method = getattr(worker_client, "render_chart", None)
    if not callable(render_method):
        return {
            "accepted": False,
            "code": "worker_renderer_unavailable",
            "worker_called": False,
            "chart_rendering_called": False,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
        }

    worker_response = render_method(transport_request)
    if not isinstance(worker_response, dict) or not worker_response.get("accepted"):
        classification_result = _record_worker_transport_failure_classification(
            store,
            job=job,
            source_snapshot=source_snapshot,
            worker=worker_client_metadata(worker_client),
            transport_request=transport_request,
            worker_response=worker_response,
        )
        if not classification_result["accepted"]:
            return {
                "accepted": False,
                "code": classification_result["code"],
                "validation": classification_result.get("validation"),
                "worker_called": True,
                "chart_rendering_called": True,
                "worker_progress_streaming_called": False,
                "worker": worker_summary,
            }

        classification = classification_result["worker_transport_failure_classification"]
        return {
            "accepted": False,
            "code": classification["failure"]["code"],
            "worker_called": True,
            "chart_rendering_called": True,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
            "worker_transport_failure_classification": classification,
            "worker_transport_failure_classification_written": True,
        }

    render_result = worker_response.get("render_result")
    render_result_validation = validate_render_result_contract(render_result)
    if not render_result_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_render_result",
            "validation": render_result_validation,
            "worker_called": True,
            "chart_rendering_called": True,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
        }
    if not isinstance(render_result, dict) or render_result.get("status") != "success":
        retry_policy_result = _record_worker_retry_policy(
            store,
            job=job,
            source_snapshot=source_snapshot,
            worker=worker_response.get("worker") or worker_client_metadata(worker_client),
            transport_request=transport_request,
            failure_code=_worker_failure_code(render_result),
            retry_safe=True,
        )
        if not retry_policy_result["accepted"]:
            return {
                "accepted": False,
                "code": retry_policy_result["code"],
                "validation": retry_policy_result.get("validation"),
                "worker_called": True,
                "chart_rendering_called": True,
                "worker_progress_streaming_called": False,
                "worker": worker_summary,
            }
        return {
            "accepted": False,
            "code": _worker_failure_code(render_result),
            "validation": render_result_validation,
            "worker_called": True,
            "chart_rendering_called": True,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
            "worker_retry_policy": retry_policy_result.get("worker_retry_policy"),
            "worker_retry_policy_written": True,
        }

    artifact_result = None
    if serve_artifact:
        artifact_result = _record_worker_rendered_artifact(
            hass,
            entry_id,
            artifact=artifact,
            render_result=render_result,
        )
        if not artifact_result["accepted"]:
            retry_policy_result = _record_worker_retry_policy(
                store,
                job=job,
                source_snapshot=source_snapshot,
                worker=worker_response.get("worker") or worker_client_metadata(worker_client),
                transport_request=transport_request,
                failure_code=artifact_result["code"],
                retry_safe=False,
            )
            if not retry_policy_result["accepted"]:
                return {
                    "accepted": False,
                    "code": retry_policy_result["code"],
                    "validation": retry_policy_result.get("validation"),
                    "worker_called": True,
                    "chart_rendering_called": True,
                    "chart_artifact_written": False,
                    "worker_progress_streaming_called": False,
                    "worker": worker_summary,
                }
            return {
                "accepted": False,
                "code": artifact_result["code"],
                "validation": artifact_result.get("validation"),
                "worker_called": True,
                "chart_rendering_called": True,
                "chart_artifact_written": False,
                "worker_progress_streaming_called": False,
                "worker": worker_summary,
                "worker_retry_policy": retry_policy_result.get("worker_retry_policy"),
                "worker_retry_policy_written": True,
            }
        artifact = artifact_result["artifact"]
        render_result = artifact_result["render_result"]

    worker_dispatch = _build_worker_dispatch(
        store,
        job=job,
        source_snapshot=source_snapshot,
        artifact=artifact,
        render_plan=render_plan,
        worker=worker_response.get("worker") or worker_client_metadata(worker_client),
        transport_request=transport_request,
        render_result=render_result,
        chart_artifact_written=artifact_result is not None,
    )
    dispatch_validation = validate_worker_dispatch_contract(worker_dispatch)
    if not dispatch_validation["accepted"]:
        artifact_rollback = _rollback_worker_rendered_artifact(hass, entry_id, artifact_result)
        return {
            "accepted": False,
            "code": "invalid_integration_worker_dispatch",
            "validation": dispatch_validation,
            "worker_called": True,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
            "artifact_rollback": artifact_rollback,
        }

    worker_progress_result = _record_worker_progress_events(
        store,
        hass=hass,
        entry_id=entry_id,
        job=job,
        worker=worker_response.get("worker") or worker_client_metadata(worker_client),
        worker_authorization=f"Bearer {token}",
        request_id=transport_request["body"]["request_id"],
        progress_payloads=worker_response.get("progress_events"),
    )
    if not worker_progress_result["accepted"]:
        artifact_rollback = _rollback_worker_rendered_artifact(hass, entry_id, artifact_result)
        return {
            "accepted": False,
            "code": worker_progress_result["code"],
            "validation": worker_progress_result.get("validation"),
            "worker_called": True,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "worker_progress_streaming_called": worker_progress_result.get("worker_progress_streaming_called", False),
            "worker": worker_summary,
            "artifact_rollback": artifact_rollback,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "worker_called": True,
        "chart_rendering_called": True,
        "chart_artifact_written": artifact_result is not None,
        "worker_progress_streaming_called": worker_progress_result.get("worker_progress_streaming_called", False),
        "artifact": deepcopy(artifact),
        "artifact_validation": artifact_result.get("artifact_validation") if artifact_result is not None else None,
        "worker_dispatch": worker_dispatch,
        "worker_progress_events": worker_progress_result.get("worker_progress_events", []),
        "validation": dispatch_validation,
        "worker_progress_validation": worker_progress_result.get("validation"),
        "worker": worker_summary,
    }


def _configured_render_path(hass: Any, entry_id: str) -> str:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    entry = entry_data.get("entry") if isinstance(entry_data, dict) else None
    return configured_render_path(getattr(entry, "options", {}) or {})


def _configured_max_codegen_repair_attempts(hass: Any, entry_id: str) -> int:
    # Default 3 (open-queue (m)): ADR-0034 made repairs do real analysis work,
    # and ~1/5 generations hit a repairable runtime slip that a single pass
    # often misses — three passes recover it (the proven live configuration).
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    entry = entry_data.get("entry") if isinstance(entry_data, dict) else None
    options = getattr(entry, "options", {}) or {}
    value = options.get("max_codegen_repair_attempts") if hasattr(options, "get") else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 3
    return value


def _build_codegen_render_request(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    render_plan: dict[str, Any],
    python_code: str,
    max_repair_attempts: int,
) -> dict[str, Any]:
    """Build a render_mode='codegen' render request carrying generated code.

    Mirrors ``_build_worker_render_request`` but flips render_mode to codegen and
    attaches ``codegen.python_code`` + ``codegen.max_repair_attempts``. The
    worker re-runs static safety on this code on every dispatch (packet 1).
    """
    render_request = _build_worker_render_request(
        store,
        hass=hass,
        entry_id=entry_id,
        render_plan=render_plan,
    )
    render_request["render_mode"] = "codegen"
    # ADR-0031 D9: hand the model epoch-ms integers, never raw HA ISO timestamps.
    render_request["history_series"] = _history_series_with_epoch_ms(
        render_request["history_series"]
    )
    render_request["codegen"] = {
        "python_code": python_code,
        "max_repair_attempts": max_repair_attempts,
    }
    return render_request


def _compact_codegen_error_detail(final_error: Any) -> dict[str, Any] | None:
    """Compact, log-safe detail from a sandbox error for diagnostics.

    Returns a `violations` list (`code@Lline: message`) for `unsafe_code`, or a
    short `traceback_tail` for runtime failures. No secrets cross here — the
    data boundary already strips tokens from the generated code; violations name
    code constructs (imports/attributes/calls), not data.
    """
    if not isinstance(final_error, dict):
        return None
    details = final_error.get("details")
    if not isinstance(details, dict):
        return None
    if final_error.get("code") == CODEGEN_CONTEXT_OVERFLOW_CODE:
        prompt_eval_count = details.get("prompt_eval_count")
        num_ctx = details.get("num_ctx")
        if isinstance(prompt_eval_count, int) and isinstance(num_ctx, int):
            return {"context_overflow": {"prompt_eval_count": prompt_eval_count, "num_ctx": num_ctx}}
    violations = details.get("violations")
    if isinstance(violations, list) and violations:
        summary = [
            f"{v.get('code')}@L{v.get('line')}: {str(v.get('message'))[:120]}"
            for v in violations[:8]
            if isinstance(v, dict)
        ]
        if summary:
            return {"violations": summary}
    traceback = details.get("traceback")
    if isinstance(traceback, str) and traceback.strip():
        return {"traceback_tail": traceback.strip().splitlines()[-3:]}
    return None


def _codegen_render_failed(
    *,
    worker_summary: dict[str, Any],
    final_error_code: str,
    stage: str,
    worker_called: bool,
    chart_rendering_called: bool,
    codegen_attempts: int,
    repair_attempts: int,
    final_error: Any = None,
) -> dict[str, Any]:
    """Fail-closed codegen result (no silent fallback to the trusted renderer).

    ADR-0029 packet 4: returns a dedicated ``codegen_render_failed`` code that
    carries the final sandbox/model error code as context. A silent trusted
    fallback would mask codegen failures and muddy the packet-5 accept/reject/
    repair eval.
    """
    codegen_failure: dict[str, Any] = {
        "stage": stage,
        "final_error_code": final_error_code,
        "codegen_attempts": codegen_attempts,
        "repair_attempts": repair_attempts,
    }
    detail = _compact_codegen_error_detail(final_error)
    if detail is not None:
        codegen_failure["detail"] = detail
    return {
        "accepted": False,
        "code": CODEGEN_RENDER_FAILED_CODE,
        "worker_called": worker_called,
        "chart_rendering_called": chart_rendering_called,
        "worker_progress_streaming_called": False,
        "worker": worker_summary,
        "codegen_failure": codegen_failure,
    }


def _record_codegen_worker_dispatch(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    artifact: dict[str, Any],
    render_plan: dict[str, Any],
    serve_artifact: bool,
    worker_client: Any,
    codegen_client: Any,
    token: str,
    worker_summary: dict[str, Any],
) -> dict[str, Any]:
    """Integration-orchestrated codegen render + repair loop (ADR-0029 packet 4).

    The data boundary (ADR-0029) forbids the worker from holding a model client,
    so the repair loop lives here, not in the worker's worker-local
    ``invoke_codegen_with_repair``. Per attempt the integration dispatches a
    fresh ``POST /v1/render`` (``render_mode: 'codegen'``); on any sandbox
    failure — including ``unsafe_code`` (ADR-0030) — it asks its own model
    provider to repair the code and re-dispatches, up to
    ``max_codegen_repair_attempts``; the worker re-runs static safety on every
    attempt. On exhaustion / generation failure it fails closed with
    ``codegen_render_failed`` — never a silent trusted fallback.
    """
    config_data = getattr(getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {}).get("entry"), "data", {}) or {}
    codegen_model = configured_codegen_model(config_data)
    max_repair_attempts = _configured_max_codegen_repair_attempts(hass, entry_id)
    # ADR-0034: the user's original prompt is the analysis-intent conduit — the
    # codegen model needs it to know whether to compute a derived series / answer
    # a question rather than plot the raw inputs. It is a generation-time argument
    # only; it never enters `codegen_request` (the render request that crosses to
    # the worker sandbox), which is built independently below.
    user_request = job.get("prompt") if isinstance(job, dict) else None

    # 1. Generate the initial code from the validated ChartSpec + render data.
    #    ADR-0031 D9: normalize timestamps to epoch-ms before the data reaches the
    #    model, matching the dispatch request the sandbox will execute against.
    codegen_request = _build_worker_render_request(
        store, hass=hass, entry_id=entry_id, render_plan=render_plan
    )
    codegen_request["history_series"] = _history_series_with_epoch_ms(
        codegen_request["history_series"]
    )
    generation = codegen_client.generate_chart_code(
        codegen_request, model=codegen_model, user_request=user_request
    )
    if not isinstance(generation, dict) or not generation.get("accepted"):
        return _codegen_render_failed(
            worker_summary=worker_summary,
            final_error_code=generation.get("code", "model_provider_codegen_failed")
            if isinstance(generation, dict)
            else "model_provider_codegen_failed",
            stage="generate",
            worker_called=False,
            chart_rendering_called=False,
            codegen_attempts=0,
            repair_attempts=0,
        )
    current_code = generation["python_code"]

    # Context overflow: the prompt was truncated, so the model never saw the
    # instructions and its code (and any repair, whose prompt is larger) is
    # doomed. Fail fast with a distinct, actionable code instead of burning the
    # repair budget on a misleading downstream syntax_error.
    generation_overflow = generation.get("context_overflow")
    if isinstance(generation_overflow, dict):
        return _codegen_render_failed(
            worker_summary=worker_summary,
            final_error_code=CODEGEN_CONTEXT_OVERFLOW_CODE,
            stage="generate",
            worker_called=False,
            chart_rendering_called=False,
            codegen_attempts=1,
            repair_attempts=0,
            final_error={"code": CODEGEN_CONTEXT_OVERFLOW_CODE, "details": generation_overflow},
        )

    render_method = getattr(worker_client, "render_chart", None)
    if not callable(render_method):
        return {
            "accepted": False,
            "code": "worker_renderer_unavailable",
            "worker_called": False,
            "chart_rendering_called": False,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
        }

    repair_attempts_made = 0
    final_error_code = "runtime_error"
    # Tracks the most recent sandbox-success for grounding-failure recovery.
    _last_ok_render_result: dict[str, Any] | None = None
    _last_ok_worker_response: dict[str, Any] | None = None
    _last_ok_transport_request: dict[str, Any] | None = None
    _last_grounding_outcome: str | None = None

    # Attempts: the initial render + up to max_repair_attempts repaired renders.
    for attempt_number in range(1, max_repair_attempts + 2):
        render_request = _build_codegen_render_request(
            store,
            hass=hass,
            entry_id=entry_id,
            render_plan=render_plan,
            python_code=current_code,
            max_repair_attempts=max_repair_attempts,
        )
        render_request_validation = validate_render_request_contract(render_request)
        if not render_request_validation["accepted"]:
            return {
                "accepted": False,
                "code": "invalid_worker_render_request",
                "validation": render_request_validation,
                "worker_called": False,
                "chart_rendering_called": False,
                "worker_progress_streaming_called": False,
                "worker": worker_summary,
            }

        dispatch_number = store["next_worker_dispatch_number"]
        transport_request = build_worker_transport_request(
            render_request,
            request_id=f"{store['entry_id']}-worker-transport-{dispatch_number:03d}-codegen-{attempt_number:02d}",
            worker_token=token,
        )
        transport_validation = validate_worker_transport_request_contract(transport_request)
        if not transport_validation["accepted"]:
            return {
                "accepted": False,
                "code": "invalid_worker_transport_request",
                "validation": transport_validation,
                "worker_called": False,
                "chart_rendering_called": False,
                "worker_progress_streaming_called": False,
                "worker": worker_summary,
            }

        worker_response = render_method(transport_request)
        if not isinstance(worker_response, dict) or not worker_response.get("accepted"):
            # Transport-layer fault (auth/version/connection): not a codegen bug.
            classification_result = _record_worker_transport_failure_classification(
                store,
                job=job,
                source_snapshot=source_snapshot,
                worker=worker_client_metadata(worker_client),
                transport_request=transport_request,
                worker_response=worker_response,
            )
            if not classification_result["accepted"]:
                return {
                    "accepted": False,
                    "code": classification_result["code"],
                    "validation": classification_result.get("validation"),
                    "worker_called": True,
                    "chart_rendering_called": True,
                    "worker_progress_streaming_called": False,
                    "worker": worker_summary,
                }
            classification = classification_result["worker_transport_failure_classification"]
            return {
                "accepted": False,
                "code": classification["failure"]["code"],
                "worker_called": True,
                "chart_rendering_called": True,
                "worker_progress_streaming_called": False,
                "worker": worker_summary,
                "worker_transport_failure_classification": classification,
                "worker_transport_failure_classification_written": True,
            }

        render_result = worker_response.get("render_result")
        render_result_validation = validate_render_result_contract(render_result)
        if not render_result_validation["accepted"]:
            return {
                "accepted": False,
                "code": "invalid_worker_render_result",
                "validation": render_result_validation,
                "worker_called": True,
                "chart_rendering_called": True,
                "worker_progress_streaming_called": False,
                "worker": worker_summary,
            }

        if isinstance(render_result, dict) and render_result.get("status") == "success":
            # ADR-0031 D8a: run the deterministic answer-grounding check before
            # serving the artifact.  Grounding failures route through the shared
            # repair loop (same budget); on exhaustion the chart is served with
            # the answer withheld (contradicted) or caveated (soft failure).
            render_metadata = render_result.get("render_metadata") or {}
            grounding = _run_grounding_check(render_metadata, codegen_request["history_series"])

            if grounding["outcome"] not in ("repair_contradicted", "repair_soft"):
                # Pass / verified / unverified_caveat — serve immediately.
                return _finish_codegen_success(
                    store,
                    hass=hass,
                    entry_id=entry_id,
                    job=job,
                    source_snapshot=source_snapshot,
                    artifact=artifact,
                    render_plan=render_plan,
                    serve_artifact=serve_artifact,
                    worker_client=worker_client,
                    worker_response=worker_response,
                    transport_request=transport_request,
                    render_result=render_result,
                    token=token,
                    worker_summary=worker_summary,
                    answer_verification=grounding["answer_verification"],
                    withheld_answer=False,
                )

            # Grounding failure: save this successful render for potential
            # withheld-serve on repair exhaustion, then continue the loop.
            _last_ok_render_result = render_result
            _last_ok_worker_response = worker_response
            _last_ok_transport_request = transport_request
            _last_grounding_outcome = grounding["outcome"]
            error = grounding["synthetic_error"] or {}
            final_error_code = error.get("code", "grounding_check_failed")
        else:
            # Sandbox-level failure. Every failure class is repairable, including
            # unsafe_code (ADR-0030): the worker re-runs the full static check +
            # sandbox on each fresh dispatch, so the boundary still enforces —
            # repair gets another try at the gate, never around it.
            _last_ok_render_result = None
            _last_grounding_outcome = None
            error = render_result.get("error") if isinstance(render_result, dict) else None
            final_error_code = error.get("code") if isinstance(error, dict) else "runtime_error"

        if attempt_number > max_repair_attempts:
            break

        repair = codegen_client.repair_chart_code(
            current_code,
            error if isinstance(error, dict) else {},
            codegen_request,
            model=codegen_model,
            user_request=user_request,
        )
        repair_attempts_made += 1
        if not isinstance(repair, dict) or not repair.get("accepted"):
            return _codegen_render_failed(
                worker_summary=worker_summary,
                final_error_code=repair.get("code", "model_provider_codegen_repair_failed")
                if isinstance(repair, dict)
                else "model_provider_codegen_repair_failed",
                stage="repair",
                worker_called=True,
                chart_rendering_called=True,
                codegen_attempts=attempt_number,
                repair_attempts=repair_attempts_made,
            )
        repair_overflow = repair.get("context_overflow")
        if isinstance(repair_overflow, dict):
            return _codegen_render_failed(
                worker_summary=worker_summary,
                final_error_code=CODEGEN_CONTEXT_OVERFLOW_CODE,
                stage="repair",
                worker_called=True,
                chart_rendering_called=True,
                codegen_attempts=attempt_number,
                repair_attempts=repair_attempts_made,
                final_error={"code": CODEGEN_CONTEXT_OVERFLOW_CODE, "details": repair_overflow},
            )
        current_code = repair["python_code"]

    # Exhausted.
    # If the last failure was a grounding check (the sandbox succeeded), serve
    # the chart — with the answer withheld (contradicted) or present with a
    # caveat (soft failure) — rather than failing closed.
    if _last_ok_render_result is not None and _last_grounding_outcome is not None:
        withheld = _last_grounding_outcome == "repair_contradicted"
        return _finish_codegen_success(
            store,
            hass=hass,
            entry_id=entry_id,
            job=job,
            source_snapshot=source_snapshot,
            artifact=artifact,
            render_plan=render_plan,
            serve_artifact=serve_artifact,
            worker_client=worker_client,
            worker_response=_last_ok_worker_response,
            transport_request=_last_ok_transport_request,
            render_result=_last_ok_render_result,
            token=token,
            worker_summary=worker_summary,
            answer_verification="unverified",
            withheld_answer=withheld,
        )

    # Sandbox-level exhaustion: fail closed carrying the final sandbox error code
    # + a compact detail (violations / traceback tail) for diagnostics.
    return _codegen_render_failed(
        worker_summary=worker_summary,
        final_error_code=final_error_code,
        stage="render",
        final_error=error if isinstance(error, dict) else None,
        worker_called=True,
        chart_rendering_called=True,
        codegen_attempts=max_repair_attempts + 1,
        repair_attempts=repair_attempts_made,
    )


def _finish_codegen_success(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    artifact: dict[str, Any],
    render_plan: dict[str, Any],
    serve_artifact: bool,
    worker_client: Any,
    worker_response: dict[str, Any],
    transport_request: dict[str, Any],
    render_result: dict[str, Any],
    token: str,
    worker_summary: dict[str, Any],
    answer_verification: str | None = None,
    withheld_answer: bool = False,
) -> dict[str, Any]:
    """Serve a successful codegen render through the existing worker artifact path."""
    artifact_result = None
    if serve_artifact:
        artifact_result = _record_worker_rendered_artifact(
            hass,
            entry_id,
            artifact=artifact,
            render_result=render_result,
            render_path=RENDER_MODE_CODEGEN,
            answer_verification=answer_verification,
            withheld_answer=withheld_answer,
        )
        if not artifact_result["accepted"]:
            return _codegen_render_failed(
                worker_summary=worker_summary,
                final_error_code=artifact_result["code"],
                stage="serve",
                worker_called=True,
                chart_rendering_called=True,
                codegen_attempts=1,
                repair_attempts=0,
            )
        artifact = artifact_result["artifact"]
        render_result = artifact_result["render_result"]

    worker_dispatch = _build_worker_dispatch(
        store,
        job=job,
        source_snapshot=source_snapshot,
        artifact=artifact,
        render_plan=render_plan,
        worker=worker_response.get("worker") or worker_client_metadata(worker_client),
        transport_request=transport_request,
        render_result=render_result,
        chart_artifact_written=artifact_result is not None,
    )
    dispatch_validation = validate_worker_dispatch_contract(worker_dispatch)
    if not dispatch_validation["accepted"]:
        artifact_rollback = _rollback_worker_rendered_artifact(hass, entry_id, artifact_result)
        return {
            "accepted": False,
            "code": "invalid_integration_worker_dispatch",
            "validation": dispatch_validation,
            "worker_called": True,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
            "artifact_rollback": artifact_rollback,
        }

    worker_progress_result = _record_worker_progress_events(
        store,
        hass=hass,
        entry_id=entry_id,
        job=job,
        worker=worker_response.get("worker") or worker_client_metadata(worker_client),
        worker_authorization=f"Bearer {token}",
        request_id=transport_request["body"]["request_id"],
        progress_payloads=worker_response.get("progress_events"),
    )
    if not worker_progress_result["accepted"]:
        artifact_rollback = _rollback_worker_rendered_artifact(hass, entry_id, artifact_result)
        return {
            "accepted": False,
            "code": worker_progress_result["code"],
            "validation": worker_progress_result.get("validation"),
            "worker_called": True,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "worker_progress_streaming_called": worker_progress_result.get("worker_progress_streaming_called", False),
            "worker": worker_summary,
            "artifact_rollback": artifact_rollback,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "worker_called": True,
        "chart_rendering_called": True,
        "chart_artifact_written": artifact_result is not None,
        "worker_progress_streaming_called": worker_progress_result.get("worker_progress_streaming_called", False),
        "artifact": deepcopy(artifact),
        "artifact_validation": artifact_result.get("artifact_validation") if artifact_result is not None else None,
        "worker_dispatch": worker_dispatch,
        "worker_progress_events": worker_progress_result.get("worker_progress_events", []),
        "validation": dispatch_validation,
        "worker_progress_validation": worker_progress_result.get("validation"),
        "worker": worker_summary,
    }


def _build_artifact_metadata(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    artifact_number = store["next_artifact_number"]
    artifact_id = f"{store['entry_id']}-artifact-{artifact_number:03d}"
    chart = _chart_metadata_for_artifact(
        artifact_id=artifact_id,
        job=job,
        source_snapshot=source_snapshot,
    )
    artifact = {
        "artifact_id": artifact_id,
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "artifact_kind": "chart_image",
        "status": "placeholder",
        **chart,
        "render_metadata": {
            "renderer": "artifact_storage_scaffold",
            "render_attempted": False,
            "worker_called": False,
            "chart_rendering_called": False,
        },
        "validation": {
            "status": "pass",
            "summary": "Placeholder artifact metadata validates before storage.",
            "checks": [
                {"name": "integration_job_snapshot", "status": "pass"},
                {"name": "artifact_metadata_schema", "status": "pass"},
                {"name": "worker", "status": "not_called"},
                {"name": "chart_rendering", "status": "not_called"},
            ],
        },
        "warnings": [
            "artifact_storage_scaffold",
            "placeholder_chart_artifact",
            "chart_rendering_not_started",
        ],
    }
    return artifact


def _build_in_process_artifact_metadata(
    artifact: dict[str, Any],
    *,
    render_result: dict[str, Any],
    image_url: str,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    rendered = deepcopy(artifact)
    render_metadata = render_result.get("render_metadata") if isinstance(render_result, dict) else {}
    if not isinstance(render_metadata, dict):
        render_metadata = {}
    rendered["status"] = "rendered"
    rendered["image_url"] = image_url
    # ADR-0030: every served chart records how it was rendered; a Pillow render
    # that happened because codegen could not complete carries the reason.
    rendered["render_path"] = RENDER_PATH_PILLOW
    if fallback_reason is not None:
        rendered["render_fallback_reason"] = fallback_reason
    # Carry the model summary and renderer color manifest onto the artifact so the
    # complete snapshot can surface them as the caption and card legend (ADR-0027).
    summary = render_metadata.get("summary")
    if isinstance(summary, str) and summary.strip():
        rendered["summary"] = summary.strip()
    legend = render_metadata.get("legend")
    if isinstance(legend, list) and legend:
        rendered["legend"] = legend
    rendered["render_metadata"] = {
        "renderer": IN_PROCESS_RENDERER_NAME,
        "render_attempted": True,
        "worker_called": False,
        "chart_rendering_called": True,
    }
    rendered["validation"] = {
        "status": "pass",
        "summary": "In-process trusted Pillow artifact validates before storage.",
        "checks": [
            {"name": "integration_job_snapshot", "status": "pass"},
            {"name": "integration_render_plan", "status": "pass"},
            {"name": "render_request_schema", "status": "pass"},
            {"name": "render_result_schema", "status": "pass"},
            {"name": "pillow_png", "status": "pass"},
            {"name": "worker", "status": "not_called"},
        ],
    }
    rendered["warnings"] = [
        "first_real_vertical_slice",
        "in_process_pillow_renderer",
        "chart_artifact_served_url",
        *list(render_metadata.get("warnings", []) if isinstance(render_metadata, dict) else []),
    ]
    return rendered


def _build_worker_artifact_metadata(
    artifact: dict[str, Any],
    *,
    render_result: dict[str, Any],
    image_url: str,
    render_path: str | None = None,
    answer_verification: str | None = None,
    withheld_answer: bool = False,
) -> dict[str, Any]:
    rendered = deepcopy(artifact)
    render_metadata = render_result.get("render_metadata") if isinstance(render_result, dict) else {}
    if not isinstance(render_metadata, dict):
        render_metadata = {}
    rendered["status"] = "rendered"
    if render_path is not None:
        rendered["render_path"] = render_path
    rendered["image_url"] = image_url
    # ADR-0031 tranche 1: carry the grounded analysis answer the sandbox computed
    # onto the artifact so the complete snapshot can surface it under the caption.
    # ADR-0031 D8a: suppress the answer when the grounding check determined it is
    # contradicted and repair was exhausted (withheld_answer=True).
    if not withheld_answer:
        answer_text = render_metadata.get("answer_text")
        if isinstance(answer_text, str) and answer_text.strip():
            rendered["answer_text"] = answer_text.strip()
    if answer_verification is not None:
        rendered["answer_verification"] = answer_verification
    rendered["render_metadata"] = {
        "renderer": WORKER_RENDERER_NAME,
        "render_attempted": True,
        "worker_called": True,
        "chart_rendering_called": True,
    }
    rendered["validation"] = {
        "status": "pass",
        "summary": "Worker-rendered artifact validates before storage.",
        "checks": [
            {"name": "integration_job_snapshot", "status": "pass"},
            {"name": "integration_render_plan", "status": "pass"},
            {"name": "render_request_schema", "status": "pass"},
            {"name": "render_result_schema", "status": "pass"},
            {"name": "worker_png_payload", "status": "pass"},
            {"name": "worker", "status": "pass"},
        ],
    }
    rendered["warnings"] = [
        "first_real_vertical_slice",
        "worker_renderer",
        "worker_rendered_artifact_serving",
        "worker_render_result_recorded",
        "chart_artifact_served_url",
        *list(render_metadata.get("warnings", []) if isinstance(render_metadata, dict) else []),
    ]
    return rendered


_OVERLAY_BAND_AUTO_PALETTE = ((173, 216, 230), (255, 200, 150), (200, 230, 200), (220, 200, 240))


def _overlay_band(start: datetime, end: datetime, color: str, label: Any, entity_id: Any) -> dict[str, Any]:
    return {
        "start_ms": int(start.timestamp() * 1000),
        "end_ms": int(end.timestamp() * 1000),
        "color": color,
        "label": label,
        "entity_id": entity_id,
    }


def _compute_overlay_bands(
    chart_spec: Any, history_series: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Precompute shaded overlay bands so codegen draws them deterministically (ADR-0033).

    The floor model cannot reliably turn a categorical state series into shaded
    intervals — it plotted the raw state ("cool") as a line on the value axis. So
    the integration computes the bands here, reusing the trusted Pillow renderer's
    attribute-aware state-segment/region logic (e.g. ``hvac_action`` for climate),
    and hands the model ready-to-draw ``{start_ms, end_ms, color, label}`` bands via
    ``derived_intervals`` — matching the Pillow overlay exactly. The state overlay
    series is still delivered in ``history_series`` (grounding/answer may use it);
    the prompt tells the model not to plot non-numeric series as lines.
    """
    if not isinstance(chart_spec, dict):
        return []
    history_by_entity = {
        s.get("entity_id"): s for s in history_series if isinstance(s, dict)
    }
    window_end = _history_window_end_dt(history_series)
    bands: list[dict[str, Any]] = []
    for index, overlay in enumerate(chart_spec.get("overlays") or []):
        if not isinstance(overlay, dict) or overlay.get("render_as") != "shaded_intervals":
            continue
        source = overlay.get("source") if isinstance(overlay.get("source"), dict) else {}
        entity_id = source.get("entity_id")
        history = history_by_entity.get(entity_id)
        if history is None:
            continue
        attribute_key = source.get("attribute")
        overlay_label = overlay.get("label") or entity_id
        color_map = overlay.get("color_map")
        active_values = overlay.get("active_values")

        if isinstance(color_map, dict) and color_map:
            state_colors = list(color_map.items())
        elif active_values is None:
            state_colors = [
                (sv, _rgb_to_hex(_OVERLAY_BAND_AUTO_PALETTE[i % len(_OVERLAY_BAND_AUTO_PALETTE)]))
                for i, sv in enumerate(_categorical_overlay_states(history))
            ]
        else:
            # Binary: one color across the whole active set.
            hexc = _rgb_to_hex(_OVERLAY_COLORS[index % len(_OVERLAY_COLORS)])
            for start, end in _binary_on_regions(
                history, {str(v) for v in active_values}, window_end=window_end, attribute_key=attribute_key
            ):
                bands.append(_overlay_band(start, end, hexc, overlay_label, entity_id))
            continue

        for state_value, hexc in state_colors:
            for start, end in _binary_on_regions(
                history, {state_value}, window_end=window_end, attribute_key=attribute_key
            ):
                bands.append(_overlay_band(start, end, hexc, state_value, entity_id))
    return bands


def _build_worker_render_request(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    render_plan: dict[str, Any],
) -> dict[str, Any]:
    dispatch_number = store["next_worker_dispatch_number"]
    chart_spec = deepcopy(render_plan["chart_spec"])
    history_series = _history_series_for_render_plan(
        hass,
        entry_id=entry_id,
        render_plan=render_plan,
    )
    return {
        "request_id": f"{store['entry_id']}-render-request-{dispatch_number:03d}",
        "render_mode": render_plan["render_mode"],
        "chart_spec": chart_spec,
        "history_series": history_series,
        "derived_intervals": _compute_overlay_bands(chart_spec, history_series),
        "output": deepcopy(render_plan["output"]),
        "theme": {},
        "codegen": None,
    }


def _build_worker_dispatch(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    artifact: dict[str, Any],
    render_plan: dict[str, Any],
    worker: dict[str, Any],
    transport_request: dict[str, Any],
    render_result: dict[str, Any],
    chart_artifact_written: bool = False,
) -> dict[str, Any]:
    dispatch_number = store["next_worker_dispatch_number"]
    dispatch_id = f"{store['entry_id']}-worker-dispatch-{dispatch_number:03d}"
    return {
        "dispatch_id": dispatch_id,
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "render_plan_id": render_plan["render_plan_id"],
        "artifact_id": artifact["artifact_id"],
        "status": "render_succeeded",
        "worker": {
            "type": worker.get("type") or "http_json_worker",
            "role": worker.get("role") or "renderer",
            "endpoint_url": worker.get("endpoint_url") or "",
            "api_version": worker.get("api_version") or 1,
        },
        "request": redacted_worker_transport_request(transport_request),
        "render_result": deepcopy(render_result),
        "validation": {
            "status": "pass",
            "summary": "Worker transport request and render result validate before dispatch storage.",
            "checks": [
                {"name": "integration_render_plan", "status": "pass"},
                {"name": "render_request_schema", "status": "pass"},
                {"name": "worker_transport_request_schema", "status": "pass"},
                {"name": "render_result_schema", "status": "pass"},
                {"name": "worker_authorization_redacted", "status": "pass"},
            ],
        },
        "warnings": [
            "worker_dispatch_rendering_scaffold",
            "worker_render_result_recorded",
            "worker_authorization_redacted",
            (
                "worker_rendered_artifact_serving"
                if chart_artifact_written
                else "integration_chart_artifact_file_not_written"
            ),
        ],
    }


def _record_worker_transport_failure_classification(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    worker: dict[str, Any],
    transport_request: dict[str, Any],
    worker_response: Any,
) -> dict[str, Any]:
    classification = _build_worker_transport_failure_classification(
        store,
        job=job,
        source_snapshot=source_snapshot,
        worker=worker,
        transport_request=transport_request,
        worker_response=worker_response,
    )
    validation = validate_worker_transport_failure_classification_contract(classification)
    if not validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_transport_failure_classification",
            "validation": validation,
        }

    _store_validated_worker_transport_failure_classification(store, classification)
    return {
        "accepted": True,
        "code": "worker_transport_failure_classification_recorded",
        "worker_transport_failure_classification": deepcopy(classification),
        "validation": validation,
    }


def _build_worker_transport_failure_classification(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    worker: dict[str, Any],
    transport_request: dict[str, Any],
    worker_response: Any,
) -> dict[str, Any]:
    classification_number = store["next_worker_transport_failure_classification_number"]
    attempt_number = _worker_transport_failure_classification_attempt_number(store, job["job_id"])
    failure_code = _safe_worker_transport_failure_code(
        worker_response.get("code") if isinstance(worker_response, dict) else None
    )
    retry_safe = (
        bool(worker_response.get("retry_safe"))
        if isinstance(worker_response, dict) and isinstance(worker_response.get("retry_safe"), bool)
        else False
    )
    family = _worker_transport_failure_family(failure_code)
    delay_seconds = min(60, 5 * (2 ** (attempt_number - 1))) if retry_safe else 0
    return {
        "classification_id": f"{store['entry_id']}-worker-transport-failure-{classification_number:03d}",
        "type": "isolinear_worker_transport_failure_classification",
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "worker": {
            "type": worker.get("type") or "http_json_worker",
            "role": worker.get("role") or "renderer",
            "endpoint_url": worker.get("endpoint_url") or "",
            "api_version": worker.get("api_version") or 1,
            "authorization": "Bearer <redacted>",
        },
        "request": redacted_worker_transport_request(transport_request),
        "failure": {
            "stage": "worker_transport",
            "code": failure_code,
            "message": _safe_worker_transport_failure_message(
                worker_response.get("message") if isinstance(worker_response, dict) else None
            ),
            "retry_safe": retry_safe,
        },
        "classification": {
            "family": family,
            "retry_eligible": retry_safe,
            "reason": f"worker_transport_{family}_{'retry_safe' if retry_safe else 'not_retry_safe'}",
            "manual_retry_allowed": retry_safe,
            "automatic_retry_scheduled": False,
        },
        "backoff": {
            "strategy": "bounded_exponential_scaffold",
            "attempt_number": attempt_number,
            "delay_seconds": delay_seconds,
            "max_delay_seconds": 60,
            "jitter_applied": False,
        },
        "validation": {
            "status": "pass",
            "summary": "Worker transport failure classification validates before storage.",
            "checks": [
                {"name": "worker_transport_failure_observed", "status": "pass"},
                {"name": "worker_transport_failure_classification_schema", "status": "pass"},
                {"name": "worker_failure_text_sanitized", "status": "pass"},
                {"name": "worker_authorization_redacted", "status": "pass"},
                {"name": "automatic_retry_not_scheduled", "status": "pass"},
            ],
        },
        "warnings": [
            "worker_transport_failure_retry_classification_scaffold",
            "worker_authorization_redacted",
            "automatic_retry_not_scheduled",
            "bounded_in_memory_transport_classification",
        ],
    }


def _record_worker_retry_policy(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    worker: dict[str, Any],
    transport_request: dict[str, Any],
    failure_code: str,
    retry_safe: bool,
) -> dict[str, Any]:
    policy = _build_worker_retry_policy(
        store,
        job=job,
        source_snapshot=source_snapshot,
        worker=worker,
        transport_request=transport_request,
        failure_code=failure_code,
        retry_safe=retry_safe,
    )
    validation = validate_worker_retry_policy_contract(policy)
    if not validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_retry_policy",
            "validation": validation,
        }

    _store_validated_worker_retry_policy(store, policy)
    return {
        "accepted": True,
        "code": "worker_retry_policy_recorded",
        "worker_retry_policy": deepcopy(policy),
        "validation": validation,
    }


def _build_worker_retry_policy(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    worker: dict[str, Any],
    transport_request: dict[str, Any],
    failure_code: str,
    retry_safe: bool,
) -> dict[str, Any]:
    policy_number = store["next_worker_retry_policy_number"]
    attempt_number = _worker_retry_policy_attempt_number(store, job["job_id"])
    delay_seconds = min(60, 5 * (2 ** (attempt_number - 1)))
    normalized_failure_code = _safe_worker_failure_code(failure_code)
    eligible = bool(retry_safe)
    return {
        "policy_id": f"{store['entry_id']}-worker-retry-policy-{policy_number:03d}",
        "type": "isolinear_worker_retry_policy",
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "worker": {
            "type": worker.get("type") or "http_json_worker",
            "role": worker.get("role") or "renderer",
            "endpoint_url": worker.get("endpoint_url") or "",
            "api_version": worker.get("api_version") or 1,
            "authorization": "Bearer <redacted>",
        },
        "request": redacted_worker_transport_request(transport_request),
        "failure": {
            "stage": "worker_render",
            "code": normalized_failure_code,
            "message": "Worker render failed before scaffold artifact metadata was accepted.",
            "retry_safe": eligible,
        },
        "decision": {
            "eligible": eligible,
            "reason": "worker_failure_retry_safe" if eligible else "worker_failure_not_retry_safe",
            "manual_retry_allowed": eligible,
            "automatic_retry_scheduled": False,
        },
        "backoff": {
            "strategy": "bounded_exponential_scaffold",
            "attempt_number": attempt_number,
            "delay_seconds": delay_seconds if eligible else 0,
            "max_delay_seconds": 60,
            "jitter_applied": False,
        },
        "validation": {
            "status": "pass",
            "summary": "Worker retry/backoff policy validates before storage.",
            "checks": [
                {"name": "worker_failure_observed", "status": "pass"},
                {"name": "worker_retry_policy_schema", "status": "pass"},
                {"name": "worker_authorization_redacted", "status": "pass"},
                {"name": "automatic_retry_not_scheduled", "status": "pass"},
            ],
        },
        "warnings": [
            "worker_retry_backoff_policy_scaffold",
            "worker_authorization_redacted",
            "automatic_retry_not_scheduled",
            "bounded_in_memory_retry_policy",
        ],
    }


def _chart_metadata_for_artifact(
    *,
    artifact_id: str,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    series = _artifact_series(source_snapshot)
    return {
        "title": _artifact_title(job, source_snapshot),
        "image_url": f"/api/isolinear/artifacts/{artifact_id}.png",
        "time_range": "approved scaffold history window",
        "series": series,
        "overlays": [],
    }
