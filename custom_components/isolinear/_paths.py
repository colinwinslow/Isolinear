"""Package-local runtime paths for the Isolinear integration."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(__file__).resolve().parent
SCHEMAS_DIR = PACKAGE_DIR / "schemas"
FRONTEND_DIST_DIR = PACKAGE_DIR / "frontend" / "dist"


def schema_path(filename: str) -> Path:
    """Return a bundled JSON Schema path inside the installed integration."""
    return SCHEMAS_DIR / filename


@lru_cache(maxsize=None)
def _load_schema_document_cached(resolved_path: str) -> dict[str, Any]:
    """Read and parse one bundled JSON Schema, memoized by resolved path."""
    return json.loads(Path(resolved_path).read_text(encoding="utf-8"))


def load_schema_document(path: Path) -> dict[str, Any]:
    """Return a parsed bundled JSON Schema, reading each file at most once.

    Validators call this on every contract check. Reading and parsing the
    bundled schema file on each call blocks the Home Assistant event loop
    (the recorder/setup blocking-call warnings). Memoizing by resolved path
    means the file is read once and every later validation reuses the parsed
    document. ``preload_schema_documents`` warms this cache from an executor
    during setup so the first read never runs on the event loop. A deep copy
    is returned so callers cannot mutate the shared cached document.
    """
    return deepcopy(_load_schema_document_cached(str(path.resolve())))


def preload_schema_documents() -> int:
    """Warm the schema-document cache for every bundled schema file.

    Intended to run inside an executor (off the event loop) during setup.
    Returns the number of schema documents loaded.
    """
    count = 0
    for schema_file in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        _load_schema_document_cached(str(schema_file.resolve()))
        count += 1
    return count


def frontend_dist_path(root: Path | None = None) -> Path:
    """Return the bundled dashboard card directory.

    When ``root`` is supplied by repo tests/evals, treat it as the repository
    root. In Home Assistant/HACS installs, use the package-local asset path.
    """
    if root is not None:
        return root / "custom_components" / "isolinear" / "frontend" / "dist"
    return FRONTEND_DIST_DIR
