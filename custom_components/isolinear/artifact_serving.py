"""Production artifact serving for rendered Isolinear chart images."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .const import DOMAIN


try:  # pragma: no cover - exercised by Home Assistant, not repo tests.
    from homeassistant.components.http import StaticPathConfig
except ImportError:  # pragma: no cover - deterministic fallback for repo tests.

    @dataclass(frozen=True)
    class StaticPathConfig:
        """Fallback shape matching Home Assistant's static path config."""

        url_path: str
        path: str
        cache_headers: bool


ARTIFACT_STATIC_URL_PATH = f"/api/{DOMAIN}/artifacts"
DATA_ARTIFACT_SERVING = "artifact_serving"
DATA_ARTIFACT_STORAGE_DIR = "artifact_storage_dir"
# Internal best-effort diagnostics for tests and rollback; not a persisted
# artifact metadata contract.
DATA_ARTIFACT_WRITES = "artifact_writes"
DATA_STATIC_PATHS = "static_paths"
MAX_ARTIFACT_PNG_BYTES = 2_000_000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SAFE_ARTIFACT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def setup_artifact_serving(
    hass: Any,
    entry: Any | None = None,
    *,
    artifact_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Prepare the integration-owned artifact directory for chart PNGs."""
    entry_id = getattr(entry, "entry_id", None)
    directory = artifact_storage_dir(hass, artifact_dir=artifact_dir)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        result = _artifact_serving_rejection(
            "artifact_directory_unavailable",
            entry_id=entry_id,
            artifact_dir=directory,
            message=str(exc),
        )
    else:
        result = {
            "accepted": True,
            "code": "artifact_serving_ready",
            "entry_id": entry_id,
            "config_entry_scoped": entry_id is not None,
            "artifact_dir": str(directory),
            "static_url_path": ARTIFACT_STATIC_URL_PATH,
            "static_path": {
                "code": "static_path_not_registered",
                "url_path": ARTIFACT_STATIC_URL_PATH,
                "path": str(directory),
                "cache_headers": False,
                "call_made": False,
            },
        }

    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[DATA_ARTIFACT_SERVING] = result
    domain_data[DATA_ARTIFACT_STORAGE_DIR] = str(directory)
    if entry_id is not None:
        domain_data.setdefault(entry_id, {})[DATA_ARTIFACT_SERVING] = result
    return result


async def async_setup_artifact_serving(
    hass: Any,
    entry: Any | None = None,
    *,
    artifact_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Prepare and register the static artifact path with Home Assistant."""
    result = setup_artifact_serving(hass, entry, artifact_dir=artifact_dir)
    if not result["accepted"]:
        return result

    static_path = await async_register_artifact_static_path(hass, Path(result["artifact_dir"]))
    result = {
        **result,
        "code": (
            "artifact_serving_registered"
            if static_path["code"] in {"static_path_registered", "static_path_already_registered"}
            else "artifact_serving_ready_without_static_path"
        ),
        "static_path": static_path,
    }
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[DATA_ARTIFACT_SERVING] = result
    entry_id = getattr(entry, "entry_id", None)
    if entry_id is not None:
        domain_data.setdefault(entry_id, {})[DATA_ARTIFACT_SERVING] = result
    return result


async def async_register_artifact_static_path(hass: Any, artifact_dir: Path) -> dict[str, Any]:
    """Register the artifact directory as a Home Assistant static path once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    static_paths = domain_data.setdefault(DATA_STATIC_PATHS, {})
    cached = static_paths.get(ARTIFACT_STATIC_URL_PATH)
    if cached is not None:
        return {
            **cached,
            "code": "static_path_already_registered",
            "call_made": False,
        }

    config = StaticPathConfig(ARTIFACT_STATIC_URL_PATH, str(artifact_dir), False)
    http = getattr(hass, "http", None)
    if http is None or not hasattr(http, "async_register_static_paths"):
        return {
            "code": "static_path_registration_unavailable",
            "url_path": ARTIFACT_STATIC_URL_PATH,
            "path": str(artifact_dir),
            "cache_headers": False,
            "call_made": False,
        }

    await http.async_register_static_paths([config])
    result = {
        "code": "static_path_registered",
        "url_path": ARTIFACT_STATIC_URL_PATH,
        "path": str(artifact_dir),
        "cache_headers": False,
        "call_made": True,
    }
    static_paths[ARTIFACT_STATIC_URL_PATH] = result
    return result


def write_png_artifact(
    hass: Any,
    entry_id: str,
    *,
    artifact_id: str,
    png_bytes: Any,
) -> dict[str, Any]:
    """Write trusted-renderer PNG bytes to the integration artifact directory."""
    prepared = prepare_png_artifact(hass, entry_id, artifact_id=artifact_id, png_bytes=png_bytes)
    if not prepared["accepted"]:
        return prepared

    directory = Path(prepared["artifact_dir"])
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _artifact_write_rejection(
            "artifact_directory_unavailable",
            artifact_id=artifact_id,
            artifact_dir=directory,
            message=str(exc),
        )

    target = Path(prepared["artifact_path"])
    temp_path = directory / f".{artifact_id}.tmp"
    try:
        temp_path.write_bytes(png_bytes)
        os.replace(temp_path, target)
    except OSError as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return _artifact_write_rejection(
            "artifact_write_failed",
            artifact_id=artifact_id,
            artifact_dir=directory,
            message=str(exc),
        )

    result = {
        "accepted": True,
        "code": "artifact_png_written",
        "artifact_id": artifact_id,
        "config_entry_id": entry_id,
        "artifact_dir": str(directory),
        "artifact_path": str(target),
        "image_url": prepared["image_url"],
        "mime_type": "image/png",
        "byte_count": len(png_bytes),
    }
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    entry_data.setdefault(DATA_ARTIFACT_WRITES, {})[artifact_id] = dict(result)
    return result


def remove_png_artifact(hass: Any, entry_id: str, *, artifact_id: str) -> dict[str, Any]:
    """Remove a written PNG artifact during failed snapshot rollback."""
    if not isinstance(artifact_id, str) or not SAFE_ARTIFACT_ID.fullmatch(artifact_id):
        return {
            "accepted": False,
            "code": "invalid_artifact_id",
            "artifact_id": artifact_id,
            "removed": False,
        }

    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    writes = entry_data.setdefault(DATA_ARTIFACT_WRITES, {})
    write_metadata = writes.get(artifact_id) if isinstance(writes, dict) else None
    if isinstance(write_metadata, dict) and isinstance(write_metadata.get("artifact_path"), str):
        target = Path(write_metadata["artifact_path"])
    else:
        target = _configured_artifact_dir(hass) / f"{artifact_id}.png"

    removed = False
    try:
        if target.exists():
            target.unlink()
            removed = True
    except OSError as exc:
        return {
            "accepted": False,
            "code": "artifact_remove_failed",
            "artifact_id": artifact_id,
            "artifact_path": str(target),
            "removed": False,
            "message": str(exc),
        }

    if isinstance(writes, dict):
        writes.pop(artifact_id, None)

    return {
        "accepted": True,
        "code": "artifact_png_removed" if removed else "artifact_png_not_present",
        "artifact_id": artifact_id,
        "artifact_path": str(target),
        "removed": removed,
    }


def prepare_png_artifact(
    hass: Any,
    entry_id: str,
    *,
    artifact_id: str,
    png_bytes: Any,
) -> dict[str, Any]:
    """Validate and describe the PNG artifact target without writing a file."""
    payload_validation = validate_png_artifact_payload(artifact_id=artifact_id, png_bytes=png_bytes)
    if not payload_validation["accepted"]:
        return payload_validation

    directory = _configured_artifact_dir(hass)
    target = directory / f"{artifact_id}.png"
    if not _path_is_inside_directory(target, directory):
        return _artifact_write_rejection(
            "invalid_artifact_id",
            artifact_id=artifact_id,
            artifact_dir=directory,
            message="Artifact filename escaped the artifact directory.",
        )

    return {
        "accepted": True,
        "code": "artifact_png_prepared",
        "artifact_id": artifact_id,
        "config_entry_id": entry_id,
        "artifact_dir": str(directory),
        "artifact_path": str(target),
        "image_url": artifact_url(artifact_id),
        "mime_type": "image/png",
        "byte_count": len(png_bytes),
    }


def validate_png_artifact_payload(*, artifact_id: Any, png_bytes: Any) -> dict[str, Any]:
    """Validate the artifact ID and PNG payload before any file write."""
    if not isinstance(artifact_id, str) or not SAFE_ARTIFACT_ID.fullmatch(artifact_id):
        return {
            "accepted": False,
            "code": "invalid_artifact_id",
            "artifact_id": artifact_id,
        }
    if not isinstance(png_bytes, bytes):
        return {
            "accepted": False,
            "code": "invalid_artifact_png_payload",
            "artifact_id": artifact_id,
            "reason": "must_be_bytes",
        }
    if not png_bytes.startswith(PNG_SIGNATURE):
        return {
            "accepted": False,
            "code": "invalid_artifact_png_payload",
            "artifact_id": artifact_id,
            "reason": "png_signature_required",
        }
    if len(png_bytes) > MAX_ARTIFACT_PNG_BYTES:
        return {
            "accepted": False,
            "code": "artifact_png_too_large",
            "artifact_id": artifact_id,
            "max_bytes": MAX_ARTIFACT_PNG_BYTES,
            "observed_bytes": len(png_bytes),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "artifact_id": artifact_id,
        "byte_count": len(png_bytes),
    }


def artifact_url(artifact_id: str) -> str:
    """Return the served same-origin URL for an artifact ID."""
    return f"{ARTIFACT_STATIC_URL_PATH}/{artifact_id}.png"


def artifact_storage_dir(
    hass: Any,
    *,
    artifact_dir: Path | str | None = None,
) -> Path:
    """Resolve the integration-owned artifact directory."""
    if artifact_dir is not None:
        return Path(artifact_dir)

    configured = getattr(hass, "data", {}).get(DOMAIN, {}).get(DATA_ARTIFACT_STORAGE_DIR)
    if isinstance(configured, str) and configured.strip():
        return Path(configured)

    config = getattr(hass, "config", None)
    path_helper = getattr(config, "path", None)
    if callable(path_helper):
        try:
            return Path(path_helper(".storage", DOMAIN, "artifacts"))
        except TypeError:
            return Path(path_helper(f".storage/{DOMAIN}/artifacts"))

    return Path(tempfile.gettempdir()) / DOMAIN / "artifacts"


def _configured_artifact_dir(hass: Any) -> Path:
    serving = getattr(hass, "data", {}).get(DOMAIN, {}).get(DATA_ARTIFACT_SERVING)
    if isinstance(serving, dict) and isinstance(serving.get("artifact_dir"), str):
        return Path(serving["artifact_dir"])
    return artifact_storage_dir(hass)


def _path_is_inside_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def _artifact_serving_rejection(
    code: str,
    *,
    entry_id: str | None,
    artifact_dir: Path,
    message: str,
) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "entry_id": entry_id,
        "config_entry_scoped": entry_id is not None,
        "artifact_dir": str(artifact_dir),
        "static_url_path": ARTIFACT_STATIC_URL_PATH,
        "message": message,
    }


def _artifact_write_rejection(
    code: str,
    *,
    artifact_id: str,
    artifact_dir: Path,
    message: str,
) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "artifact_id": artifact_id,
        "artifact_dir": str(artifact_dir),
        "message": message,
    }
