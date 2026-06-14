"""Package-local runtime paths for the Isolinear integration."""

from __future__ import annotations

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
SCHEMAS_DIR = PACKAGE_DIR / "schemas"
FRONTEND_DIST_DIR = PACKAGE_DIR / "frontend" / "dist"


def schema_path(filename: str) -> Path:
    """Return a bundled JSON Schema path inside the installed integration."""
    return SCHEMAS_DIR / filename


def frontend_dist_path(root: Path | None = None) -> Path:
    """Return the bundled dashboard card directory.

    When ``root`` is supplied by repo tests/evals, treat it as the repository
    root. In Home Assistant/HACS installs, use the package-local asset path.
    """
    if root is not None:
        return root / "custom_components" / "isolinear" / "frontend" / "dist"
    return FRONTEND_DIST_DIR
