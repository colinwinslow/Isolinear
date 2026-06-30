"""Test fixtures for the promoted codegen sandbox (ADR-0029, packet 1).

These generated-Python samples and the sample render request are *test material*,
not production code, so they live in the test tree rather than inside the worker
package (per docs/specs/codegen-sandbox-module-promotion.md). They are shared by
`tests/test_codegen_sandbox.py` and `evals/codegen_sandbox.py`, both of which
drive the promoted module's public API.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# A 1x1 PNG, written verbatim by the safe sample (no matplotlib needed). This
# lets the happy-path / fixed-output-path scenarios produce a real PNG on disk
# in any environment, including the `-I`-isolated subprocess that cannot see a
# user-site matplotlib install.
SAFE_SAMPLE_PNG_HEX = (
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000100ffff030000060005"
    "57bfab0000000049454e44ae426082"
)


def sandbox_can_import_matplotlib() -> bool:
    """True when the sandbox subprocess (`python3 -I`) can import matplotlib.

    The sandbox runs generated code under `-I` (isolated mode), which excludes
    the user site-packages. On a worker container matplotlib lives in the system
    site-packages and imports fine; on a dev box where matplotlib is only in the
    user site, the matplotlib-rendering scenarios cannot run and are skipped.
    """

    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", "import matplotlib"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def safe_generated_python() -> str:
    return f'''
def render_chart(data, output_path):
    png_bytes = bytes.fromhex("{SAFE_SAMPLE_PNG_HEX}")
    with open(output_path, "wb") as image_file:
        image_file.write(png_bytes)
    return {{
        "title": data["chart_spec"]["title"],
        "series_plotted": [series["series_id"] for series in data["chart_spec"]["series"]],
        "overlays_plotted": [overlay["overlay_id"] for overlay in data["chart_spec"].get("overlays", [])],
        "x_min": data["history_series"][0]["points"][0]["ts"],
        "x_max": data["history_series"][0]["points"][-1]["ts"],
        "warnings": [],
    }}
'''.strip()


def matplotlib_generated_python() -> str:
    return '''
import matplotlib
import matplotlib.pyplot as plt


def render_chart(data, output_path):
    series = data["history_series"][0]
    points = series["points"]
    x_values = [point["ts"] for point in points]
    y_values = [point["value"] for point in points]

    fig, ax = plt.subplots(figsize=(4, 2.4), dpi=120)
    ax.plot(x_values, y_values, marker="o")
    ax.set_title(data["chart_spec"]["title"])
    ax.set_ylabel(series["unit"])
    fig.tight_layout()
    fig.savefig(output_path, format="png")
    plt.close(fig)

    return {
        "title": data["chart_spec"]["title"],
        "series_plotted": [series["series_id"]],
        "overlays_plotted": [],
        "x_min": points[0]["ts"],
        "x_max": points[-1]["ts"],
        "warnings": [f"matplotlib_backend:{matplotlib.get_backend()}"],
    }
'''.strip()


def matplotlib_arbitrary_read_python(forbidden_path) -> str:
    from pathlib import Path

    resolved_path = str(Path(forbidden_path).resolve())
    return f'''
import matplotlib.pyplot as plt


def render_chart(data, output_path):
    plt.imread({resolved_path!r})
    return {{"warnings": []}}
'''.strip()


def unsafe_generated_python_examples() -> dict[str, str]:
    return {
        "requests_import": '''
import requests

def render_chart(data, output_path):
    return {}
'''.strip(),
        "secret_file_read": '''
def render_chart(data, output_path):
    with open("secrets.yaml", "r") as secret_file:
        secret_file.read()
    return {}
'''.strip(),
        "local_network_socket": '''
import socket

def render_chart(data, output_path):
    socket.socket().connect(("127.0.0.1", 8123))
    return {}
'''.strip(),
        "environment_read": '''
import os

def render_chart(data, output_path):
    token = os.environ.get("SUPERVISOR_TOKEN")
    return {"warnings": [token]}
'''.strip(),
    }


def broken_generated_python(message: str = "matplotlib runtime failure") -> str:
    return f'''
def render_chart(data, output_path):
    raise RuntimeError("{message}")
'''.strip()


def timeout_generated_python() -> str:
    return '''
def render_chart(data, output_path):
    while True:
        pass
'''.strip()


def oversized_generated_python(extra_bytes: int = 2048) -> str:
    return f'''
def render_chart(data, output_path):
    with open(output_path, "wb") as image_file:
        image_file.write(b"X" * {extra_bytes})
    return {{
        "title": data["chart_spec"]["title"],
        "series_plotted": [],
        "overlays_plotted": [],
        "warnings": ["oversized"],
    }}
'''.strip()


def sample_codegen_render_request(
    *,
    python_code: str | None = None,
    max_repair_attempts: int = 2,
) -> dict[str, Any]:
    return {
        "request_id": "codegen-sandbox-anchor",
        "render_mode": "codegen",
        "chart_spec": {
            "chart_id": "codegen_sandbox_temperature",
            "chart_type": "time_series",
            "title": "Sandboxed Temperature",
            "time_range": {"type": "relative", "duration": "24h"},
            "series": [
                {
                    "series_id": "upstairs_temperature",
                    "label": "Upstairs Temperature",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.upstairs_temperature",
                    },
                    "role": "primary",
                    "render_as": "line",
                    "unit": "degF",
                }
            ],
            "overlays": [],
            "notes": ["Sandbox codegen anchor."],
        },
        "history_series": [
            {
                "series_id": "upstairs_temperature",
                "entity_id": "sensor.upstairs_temperature",
                "label": "Upstairs Temperature",
                "kind": "numeric",
                "unit": "degF",
                "points": [
                    {
                        "ts": "2026-06-05T08:00:00Z",
                        "value": 71.2,
                        "raw_state": "71.2",
                        "quality": "ok",
                    },
                    {
                        "ts": "2026-06-05T09:00:00Z",
                        "value": 71.8,
                        "raw_state": "71.8",
                        "quality": "ok",
                    },
                ],
                "source_entity_ids": ["sensor.upstairs_temperature"],
                "warnings": [],
            }
        ],
        "derived_intervals": [],
        "output": {"format": "png", "width": 800, "height": 480},
        "theme": {},
        "codegen": {
            "python_code": safe_generated_python() if python_code is None else python_code,
            "max_repair_attempts": max_repair_attempts,
        },
    }
