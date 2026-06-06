from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .contracts import ContractValidationError, validate_contract


SANDBOX_POLICY_VERSION = 1
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SAFE_SAMPLE_PNG_HEX = (
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000100ffff030000060005"
    "57bfab0000000049454e44ae426082"
)

_FORBIDDEN_ATTRIBUTE_NAMES = {
    "chdir",
    "chmod",
    "chown",
    "connect",
    "environ",
    "getcwd",
    "getenv",
    "listdir",
    "mkdir",
    "open",
    "popen",
    "read_bytes",
    "read_text",
    "remove",
    "rename",
    "replace",
    "request",
    "rmdir",
    "rmtree",
    "scandir",
    "socket",
    "system",
    "unlink",
    "urlopen",
    "walk",
    "write_bytes",
    "write_text",
}


_RUNNER_SOURCE = r'''
from __future__ import annotations

import builtins as _builtins
import json
import os
import sys
import traceback
from pathlib import Path


_PAYLOAD = json.loads(sys.stdin.read())
_POLICY = _PAYLOAD["policy"]
_ALLOWED_GENERATED_IMPORTS = set(_POLICY["allowed_imports"])
_OUTPUT_PATH = str(Path(_PAYLOAD["output_path"]).resolve())
_ALLOWED_READ_ROOTS = tuple(
    str(Path(path).resolve()) for path in _PAYLOAD["allowed_read_roots"]
)
_RESOURCE_STATUS = {
    "cpu": "not_available_on_platform",
    "memory": "not_available_on_platform",
}


def _path_is_under(path: str, root: str) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return False
    return True


def _generated_module_allowed(module_name: str) -> bool:
    return any(
        module_name == allowed_module
        or module_name.startswith(f"{allowed_module}.")
        for allowed_module in _ALLOWED_GENERATED_IMPORTS
    )


def _apply_resource_limits() -> None:
    global _RESOURCE_STATUS

    try:
        import resource
    except ImportError:
        return

    cpu_seconds = int(_POLICY["cpu_seconds"])
    memory_bytes = int(_POLICY["memory_limit_mb"]) * 1024 * 1024

    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        _RESOURCE_STATUS["cpu"] = "resource_rlimit_cpu"
    except (OSError, ValueError):
        _RESOURCE_STATUS["cpu"] = "timeout_fallback"

    try:
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        _RESOURCE_STATUS["memory"] = "resource_rlimit_as"
    except (OSError, ValueError):
        _RESOURCE_STATUS["memory"] = "not_available_on_platform"


def _audit(event: str, args: tuple[object, ...]) -> None:
    if event == "open":
        target = args[0] if args else None
        mode = str(args[1]) if len(args) > 1 else "r"

        if isinstance(target, int):
            return

        target_path = str(Path(str(target)).resolve())
        wants_write = any(flag in mode for flag in ("w", "a", "x", "+"))
        if wants_write:
            if target_path != _OUTPUT_PATH:
                raise PermissionError("sandbox allows writes only to the fixed output path")
        elif not any(_path_is_under(target_path, root) for root in _ALLOWED_READ_ROOTS):
            raise PermissionError("sandbox allows reads only from worker runtime roots")

    if event.startswith("socket.") or event in {
        "subprocess.Popen",
        "os.system",
        "os.remove",
        "os.rename",
        "os.rmdir",
        "shutil.rmtree",
    }:
        raise PermissionError(f"sandbox denied runtime event {event}")


def _sandbox_import(
    name: str,
    globals: dict[str, object] | None = None,
    locals: dict[str, object] | None = None,
    fromlist: tuple[str, ...] = (),
    level: int = 0,
) -> object:
    if level != 0:
        raise ImportError("sandbox does not allow relative imports")
    if not _generated_module_allowed(name):
        raise ImportError(f"sandbox import not allowlisted: {name}")
    return _builtins.__import__(name, globals, locals, fromlist, level)


def _sandbox_open(file: object, mode: str = "r", *args: object, **kwargs: object) -> object:
    target_path = str(Path(str(file)).resolve())
    wants_write = any(flag in mode for flag in ("w", "a", "x", "+"))
    if target_path != _OUTPUT_PATH or not wants_write:
        raise PermissionError("sandbox open is limited to writing the fixed output path")
    return _builtins.open(_OUTPUT_PATH, mode, *args, **kwargs)


def _safe_builtins() -> dict[str, object]:
    return {
        "__import__": _sandbox_import,
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "bytes": bytes,
        "dict": dict,
        "enumerate": enumerate,
        "Exception": Exception,
        "float": float,
        "int": int,
        "isinstance": isinstance,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "open": _sandbox_open,
        "range": range,
        "round": round,
        "RuntimeError": RuntimeError,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "ValueError": ValueError,
        "zip": zip,
    }


def _emit(payload: dict[str, object]) -> None:
    payload["resource_status"] = _RESOURCE_STATUS
    print(json.dumps(payload, sort_keys=True))


_apply_resource_limits()
sys.addaudithook(_audit)

try:
    namespace = {"__builtins__": _safe_builtins()}
    exec(compile(_PAYLOAD["python_code"], "<generated_chart>", "exec"), namespace, namespace)

    render_chart = namespace.get(_POLICY["entry_point"])
    if not callable(render_chart):
        raise TypeError("Generated code did not define render_chart.")

    code_object = getattr(render_chart, "__code__", None)
    expected_args = list(_POLICY["entry_point_args"])
    actual_args = list(code_object.co_varnames[: code_object.co_argcount]) if code_object else []
    if actual_args != expected_args:
        raise TypeError(
            f"render_chart must accept {expected_args!r}; got {actual_args!r}."
        )

    metadata = render_chart(_PAYLOAD["data"], _OUTPUT_PATH)
    if not isinstance(metadata, dict):
        raise TypeError("render_chart must return metadata as a dict.")

except BaseException as exc:
    _emit(
        {
            "status": "runtime_error",
            "error_message": str(exc),
            "traceback": traceback.format_exc(limit=8),
        }
    )
else:
    _emit({"status": "success", "metadata": metadata})
'''


def default_codegen_sandbox_policy() -> dict[str, Any]:
    return {
        "policy_version": SANDBOX_POLICY_VERSION,
        "execution_model": "isolated_subprocess",
        "entry_point": "render_chart",
        "entry_point_args": ["data", "output_path"],
        "python_flags": ["-I"],
        "allowed_imports": [
            "base64",
            "datetime",
            "json",
            "math",
            "matplotlib",
            "matplotlib.dates",
            "matplotlib.pyplot",
            "statistics",
            "struct",
            "zlib",
        ],
        "forbidden_imports": [
            "asyncio",
            "ftplib",
            "glob",
            "http",
            "importlib",
            "multiprocessing",
            "os",
            "pathlib",
            "requests",
            "shutil",
            "socket",
            "ssl",
            "subprocess",
            "sys",
            "threading",
            "urllib",
        ],
        "forbidden_call_names": [
            "__import__",
            "compile",
            "eval",
            "exec",
            "globals",
            "input",
            "locals",
            "vars",
        ],
        "timeout_seconds": 10,
        "cpu_seconds": 10,
        "memory_limit_mb": 256,
        "max_output_bytes": 1_000_000,
        "network_access": "denied",
        "filesystem": {
            "write_policy": "fixed_output_path_only",
            "output_path": "provided_render_chart_output_path",
            "read_policy": "worker_runtime_roots_only",
        },
        "environment": {
            "inherit_parent_environment": False,
            "explicit_environment_keys": [
                "HOME",
                "MPLBACKEND",
                "MPLCONFIGDIR",
                "PYTHONIOENCODING",
                "PYTHONUTF8",
                "SYSTEMROOT",
                "TMP",
                "TEMP",
                "TMPDIR",
                "WINDIR",
            ],
        },
        "resource_limits": {
            "timeout": "subprocess_timeout",
            "cpu": "resource_rlimit_cpu_when_available",
            "memory": "resource_rlimit_as_when_available",
        },
    }


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


def static_safety_check(
    python_code: str,
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = default_codegen_sandbox_policy() if policy is None else policy
    violations: list[dict[str, Any]] = []

    try:
        tree = ast.parse(python_code)
    except SyntaxError as exc:
        return {
            "accepted": False,
            "code": "invalid_code",
            "render_attempted": False,
            "violations": [
                {
                    "code": "syntax_error",
                    "message": str(exc),
                    "line": exc.lineno,
                }
            ],
        }

    render_functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == policy["entry_point"]
    ]
    if len(render_functions) != 1:
        violations.append(
            {
                "code": "missing_fixed_entry_point",
                "message": "Generated code must define exactly one render_chart function.",
                "line": 1,
            }
        )
    else:
        _validate_entry_point_signature(render_functions[0], policy=policy, violations=violations)

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
            continue

        violations.append(
            {
                "code": "top_level_statement",
                "message": "Generated code may contain only imports and function definitions at top level.",
                "line": getattr(node, "lineno", 1),
            }
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            _validate_import(node, policy=policy, violations=violations)
        elif isinstance(node, ast.Call):
            _validate_call(node, violations=violations)
        elif isinstance(node, ast.Attribute):
            _validate_attribute(node, violations=violations)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            violations.append(
                {
                    "code": "scope_escape",
                    "message": "Generated code may not use global or nonlocal declarations.",
                    "line": getattr(node, "lineno", 1),
                }
            )

    if violations:
        return {
            "accepted": False,
            "code": "unsafe_code",
            "render_attempted": False,
            "violations": violations,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "render_attempted": False,
        "violations": [],
    }


def invoke_codegen_sandbox(
    *,
    render_request: dict[str, Any],
    output_directory: Path,
    policy: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    attempt_number: int = 1,
) -> dict[str, Any]:
    policy = default_codegen_sandbox_policy() if policy is None else policy
    request_id = str(render_request.get("request_id", "codegen-render"))

    try:
        validate_contract("codegen-sandbox-policy", policy, repo_root=repo_root)
        validate_contract("render-request", render_request, repo_root=repo_root)
        validate_contract("chart-spec", render_request["chart_spec"], repo_root=repo_root)
        for series in render_request["history_series"]:
            validate_contract("history-series", series, repo_root=repo_root)
    except (ContractValidationError, KeyError) as exc:
        return _new_codegen_failure(
            request_id=request_id,
            code="validation_failed",
            message=str(exc),
            codegen_attempts=0,
        )

    if render_request.get("render_mode") != "codegen":
        return _new_codegen_failure(
            request_id=request_id,
            code="invalid_request",
            message="Codegen sandbox accepts only render_mode='codegen'.",
            codegen_attempts=0,
        )

    codegen = render_request.get("codegen")
    if not isinstance(codegen, dict) or not isinstance(codegen.get("python_code"), str):
        return _new_codegen_failure(
            request_id=request_id,
            code="invalid_request",
            message="Codegen sandbox requires codegen.python_code.",
            codegen_attempts=0,
        )

    safety_result = static_safety_check(codegen["python_code"], policy=policy)
    if not safety_result["accepted"]:
        return _new_codegen_failure(
            request_id=request_id,
            code="unsafe_code",
            message="Generated code failed static sandbox safety checks.",
            codegen_attempts=attempt_number - 1,
            details={
                "render_attempted": False,
                "violations": safety_result["violations"],
            },
        )

    output_directory.mkdir(parents=True, exist_ok=True)
    image_id = _safe_image_id(request_id)
    image_path = (output_directory / image_id).resolve()

    with tempfile.TemporaryDirectory(prefix="isolinear-codegen-sandbox-") as work_directory_text:
        work_directory = Path(work_directory_text)
        runner_path = work_directory / "sandbox_runner.py"
        runner_path.write_text(_RUNNER_SOURCE, encoding="utf-8")
        payload = {
            "policy": policy,
            "python_code": codegen["python_code"],
            "data": _sandbox_data(render_request),
            "output_path": str(image_path),
            "allowed_read_roots": _allowed_read_roots(work_directory),
        }
        env = _sandbox_environment(work_directory)

        try:
            completed = subprocess.run(
                [sys.executable, *policy["python_flags"], str(runner_path)],
                cwd=str(work_directory),
                input=json.dumps(payload),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=policy["timeout_seconds"],
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return _new_codegen_failure(
                request_id=request_id,
                code="timeout",
                message="Generated code exceeded the sandbox timeout.",
                codegen_attempts=attempt_number,
                details={
                    "timeout_seconds": policy["timeout_seconds"],
                    "stdout": exc.stdout or "",
                    "stderr": exc.stderr or "",
                },
            )

    outcome = _parse_runner_outcome(completed)
    if outcome["status"] != "success":
        return _new_codegen_failure(
            request_id=request_id,
            code="runtime_error",
            message=outcome.get("error_message", "Generated code failed at runtime."),
            codegen_attempts=attempt_number,
            details={
                "traceback": outcome.get("traceback", ""),
                "resource_status": outcome.get("resource_status", {}),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        )

    if not image_path.exists():
        return _new_codegen_failure(
            request_id=request_id,
            code="output_missing",
            message="Generated code did not create the fixed output path.",
            codegen_attempts=attempt_number,
            details={"output_path": str(image_path)},
        )

    image_size = image_path.stat().st_size
    if image_size > policy["max_output_bytes"]:
        return _new_codegen_failure(
            request_id=request_id,
            code="output_too_large",
            message="Generated code produced an output image larger than policy allows.",
            codegen_attempts=attempt_number,
            details={
                "output_path": str(image_path),
                "max_output_bytes": policy["max_output_bytes"],
                "actual_output_bytes": image_size,
            },
        )

    metadata = _normalize_render_metadata(
        outcome.get("metadata", {}),
        render_request=render_request,
        codegen_attempts=attempt_number,
    )
    render_result = {
        "request_id": request_id,
        "status": "success",
        "image_id": image_id,
        "image_mime_type": "image/png",
        "image_path": str(image_path),
        "error": None,
        "render_metadata": metadata,
    }
    validate_contract("render-result", render_result, repo_root=repo_root)
    return render_result


def invoke_codegen_with_repair(
    *,
    render_request: dict[str, Any],
    output_directory: Path,
    repaired_python_codes: list[str] | None = None,
    policy: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    policy = default_codegen_sandbox_policy() if policy is None else policy
    codegen = render_request.get("codegen") if isinstance(render_request, dict) else None
    max_repair_attempts = (
        codegen.get("max_repair_attempts", 0) if isinstance(codegen, dict) else 0
    )
    max_repair_attempts = max(0, int(max_repair_attempts))
    repaired_python_codes = [] if repaired_python_codes is None else list(repaired_python_codes)
    current_code = codegen.get("python_code", "") if isinstance(codegen, dict) else ""
    attempt_results = []
    repair_requests = []
    static_checks_run = 0

    for attempt_number in range(1, max_repair_attempts + 2):
        attempt_request = _render_request_with_code(render_request, current_code)
        safety_result = static_safety_check(current_code, policy=policy)
        static_checks_run += 1
        render_result = invoke_codegen_sandbox(
            render_request=attempt_request,
            output_directory=output_directory,
            policy=policy,
            repo_root=repo_root,
            attempt_number=attempt_number,
        )
        attempt_results.append(
            {
                "attempt_number": attempt_number,
                "static_safety_result": safety_result,
                "render_result": render_result,
            }
        )

        if render_result["status"] == "success" or render_result["error"]["code"] == "unsafe_code":
            break

        repair_attempt_number = attempt_number
        if repair_attempt_number > max_repair_attempts:
            break

        repair_requests.append(
            {
                "repair_attempt_number": repair_attempt_number,
                "source_error_code": render_result["error"]["code"],
                "stack_trace_included": bool(
                    render_result["error"]["details"].get("traceback")
                ),
            }
        )

        if repaired_python_codes:
            current_code = repaired_python_codes.pop(0)

    final_result = attempt_results[-1]["render_result"]
    if final_result["status"] == "failed":
        final_result["error"]["details"]["repair_attempts"] = len(repair_requests)
        final_result["error"]["details"]["max_repair_attempts"] = max_repair_attempts
        final_result["error"]["details"]["static_safety_checks_run"] = static_checks_run
        validate_contract("render-result", final_result, repo_root=repo_root)

    return {
        "render_result": final_result,
        "attempt_results": attempt_results,
        "repair_requests": repair_requests,
        "max_repair_attempts": max_repair_attempts,
        "static_safety_checks_run": static_checks_run,
    }


def verify_codegen_sandbox_anchor(root: Path | None = None) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2] if root is None else root
    policy = default_codegen_sandbox_policy()
    failures = []

    try:
        validate_contract("codegen-sandbox-policy", policy, repo_root=root)
    except ContractValidationError as exc:
        failures.append(f"Sandbox policy failed schema validation: {exc}")

    output_root = root / ".test-output"
    output_root.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=output_root) as run_directory_text:
        run_directory = Path(run_directory_text)
        safe_result = invoke_codegen_sandbox(
            render_request=sample_codegen_render_request(),
            output_directory=run_directory,
            policy=policy,
            repo_root=root,
        )
        safe_output_files = sorted(path.name for path in run_directory.iterdir())

    with tempfile.TemporaryDirectory(dir=output_root) as run_directory_text:
        run_directory = Path(run_directory_text)
        matplotlib_result = invoke_codegen_sandbox(
            render_request=sample_codegen_render_request(
                python_code=matplotlib_generated_python(),
            ),
            output_directory=run_directory,
            policy=policy,
            repo_root=root,
        )
        matplotlib_output_files = sorted(path.name for path in run_directory.iterdir())
        matplotlib_image_signature = (
            Path(matplotlib_result["image_path"]).read_bytes()[:8].hex()
            if matplotlib_result["status"] == "success"
            else None
        )

    unsafe_results = {
        name: invoke_codegen_sandbox(
            render_request=sample_codegen_render_request(python_code=python_code),
            output_directory=output_root,
            policy=policy,
            repo_root=root,
        )
        for name, python_code in unsafe_generated_python_examples().items()
    }

    small_output_policy = {**policy, "max_output_bytes": 1024}
    with tempfile.TemporaryDirectory(dir=output_root) as run_directory_text:
        oversized_result = invoke_codegen_sandbox(
            render_request=sample_codegen_render_request(
                python_code=oversized_generated_python(extra_bytes=2048),
            ),
            output_directory=Path(run_directory_text),
            policy=small_output_policy,
            repo_root=root,
        )

    with tempfile.TemporaryDirectory(dir=output_root) as run_directory_text:
        repair_result = invoke_codegen_with_repair(
            render_request=sample_codegen_render_request(
                python_code=broken_generated_python("initial matplotlib failure"),
                max_repair_attempts=2,
            ),
            output_directory=Path(run_directory_text),
            repaired_python_codes=[
                broken_generated_python("first repair still fails"),
                broken_generated_python("second repair still fails"),
            ],
            policy=policy,
            repo_root=root,
        )

    if safe_result["status"] != "success":
        failures.append("Safe generated code did not complete successfully.")
    elif safe_output_files != [safe_result["image_id"]]:
        failures.append("Safe generated code wrote files outside the fixed output image.")

    if matplotlib_result["status"] != "success":
        failures.append("Allowlisted matplotlib generated code did not complete successfully.")
    elif matplotlib_output_files != [matplotlib_result["image_id"]]:
        failures.append("Matplotlib generated code wrote files outside the fixed output image.")
    elif matplotlib_image_signature != PNG_SIGNATURE.hex():
        failures.append("Matplotlib generated code did not create a PNG image.")

    if not all(result["status"] == "failed" for result in unsafe_results.values()):
        failures.append("One or more unsafe code examples were not rejected.")
    if not all(result["error"]["code"] == "unsafe_code" for result in unsafe_results.values()):
        failures.append("One or more unsafe code examples failed with the wrong code.")
    if any(result["render_metadata"]["codegen_attempts"] for result in unsafe_results.values()):
        failures.append("Unsafe code executed instead of failing before render.")

    if oversized_result["error"]["code"] != "output_too_large":
        failures.append("Oversized output did not fail with output_too_large.")

    final_repair_result = repair_result["render_result"]
    if final_repair_result["error"]["code"] != "runtime_error":
        failures.append("Capped repair loop did not end with a runtime_error.")
    if len(repair_result["repair_requests"]) != 2:
        failures.append("Repair loop did not request exactly two repairs.")
    if repair_result["static_safety_checks_run"] != 3:
        failures.append("Static safety checks were not rerun for every code attempt.")

    return {
        "passed": not failures,
        "failures": failures,
        "policy": policy,
        "safe_result": safe_result,
        "safe_output_files": safe_output_files,
        "matplotlib_result": matplotlib_result,
        "matplotlib_output_files": matplotlib_output_files,
        "matplotlib_image_signature": matplotlib_image_signature,
        "unsafe_results": unsafe_results,
        "oversized_result": oversized_result,
        "repair_result": repair_result,
    }


def _validate_entry_point_signature(
    function_node: ast.FunctionDef,
    *,
    policy: dict[str, Any],
    violations: list[dict[str, Any]],
) -> None:
    if function_node.decorator_list:
        violations.append(
            {
                "code": "entry_point_decorator",
                "message": "render_chart may not use decorators.",
                "line": function_node.lineno,
            }
        )

    args = function_node.args
    positional_args = [arg.arg for arg in [*args.posonlyargs, *args.args]]
    expected_args = list(policy["entry_point_args"])
    if (
        positional_args != expected_args
        or args.vararg is not None
        or args.kwarg is not None
        or args.kwonlyargs
        or args.defaults
        or args.kw_defaults
    ):
        violations.append(
            {
                "code": "entry_point_signature",
                "message": f"render_chart must accept exactly {expected_args!r}.",
                "line": function_node.lineno,
            }
        )


def _validate_import(
    node: ast.Import | ast.ImportFrom,
    *,
    policy: dict[str, Any],
    violations: list[dict[str, Any]],
) -> None:
    module_names: list[str]
    if isinstance(node, ast.Import):
        module_names = [alias.name for alias in node.names]
    else:
        module_names = [node.module or ""]

    for module_name in module_names:
        if _module_forbidden(module_name, policy["forbidden_imports"]):
            violations.append(
                {
                    "code": "forbidden_import",
                    "message": f"Import is forbidden in sandboxed code: {module_name}",
                    "line": getattr(node, "lineno", 1),
                    "module": module_name,
                }
            )
        elif module_name not in policy["allowed_imports"]:
            violations.append(
                {
                    "code": "import_not_allowlisted",
                    "message": f"Import is not allowlisted in sandboxed code: {module_name}",
                    "line": getattr(node, "lineno", 1),
                    "module": module_name,
                }
            )


def _validate_call(node: ast.Call, *, violations: list[dict[str, Any]]) -> None:
    if isinstance(node.func, ast.Name) and node.func.id == "open":
        if _is_allowed_fixed_output_open(node):
            return

        violations.append(
            {
                "code": "forbidden_filesystem_access",
                "message": "Generated code may open only the provided output_path for writing.",
                "line": getattr(node, "lineno", 1),
            }
        )
        return

    if isinstance(node.func, ast.Name) and node.func.id in default_codegen_sandbox_policy()["forbidden_call_names"]:
        violations.append(
            {
                "code": "forbidden_call",
                "message": f"Generated code may not call {node.func.id}.",
                "line": getattr(node, "lineno", 1),
            }
        )


def _validate_attribute(node: ast.Attribute, *, violations: list[dict[str, Any]]) -> None:
    if node.attr.startswith("__"):
        violations.append(
            {
                "code": "dunder_attribute",
                "message": "Generated code may not access dunder attributes.",
                "line": getattr(node, "lineno", 1),
            }
        )
    elif node.attr in _FORBIDDEN_ATTRIBUTE_NAMES:
        violations.append(
            {
                "code": "forbidden_attribute",
                "message": f"Generated code may not access attribute {node.attr}.",
                "line": getattr(node, "lineno", 1),
            }
        )


def _is_allowed_fixed_output_open(node: ast.Call) -> bool:
    if not node.args or not isinstance(node.args[0], ast.Name):
        return False
    if node.args[0].id != "output_path":
        return False
    if len(node.args) < 2:
        return False
    mode_arg = node.args[1]
    if not isinstance(mode_arg, ast.Constant) or not isinstance(mode_arg.value, str):
        return False
    return mode_arg.value in {"w", "wb", "x", "xb"}


def _module_forbidden(module_name: str, forbidden_imports: list[str]) -> bool:
    return any(
        module_name == forbidden_module or module_name.startswith(f"{forbidden_module}.")
        for forbidden_module in forbidden_imports
    )


def _safe_image_id(request_id: str) -> str:
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", request_id).strip("._")
    if not safe_stem:
        safe_stem = "codegen-render"
    return f"{safe_stem}.png"


def _sandbox_data(render_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "chart_spec": render_request["chart_spec"],
        "history_series": render_request["history_series"],
        "derived_intervals": render_request.get("derived_intervals", []),
        "output": render_request.get("output", {}),
        "theme": render_request.get("theme", {}),
    }


def _sandbox_environment(work_directory: Path) -> dict[str, str]:
    env = {
        "HOME": str(work_directory),
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(work_directory / "matplotlib"),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "TEMP": str(work_directory),
        "TMP": str(work_directory),
        "TMPDIR": str(work_directory),
    }
    for key in ("SYSTEMROOT", "WINDIR"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _allowed_read_roots(work_directory: Path) -> list[str]:
    roots = {
        work_directory.resolve(),
        Path(sys.executable).resolve().parent,
        Path(sys.prefix).resolve(),
        Path(sys.base_prefix).resolve(),
    }
    return [str(root) for root in sorted(roots)]


def _parse_runner_outcome(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if stdout_lines:
        try:
            return json.loads(stdout_lines[-1])
        except json.JSONDecodeError:
            pass

    return {
        "status": "runtime_error",
        "error_message": "Sandbox runner did not return a valid JSON outcome.",
        "traceback": "",
        "resource_status": {},
    }


def _normalize_render_metadata(
    metadata: dict[str, Any],
    *,
    render_request: dict[str, Any],
    codegen_attempts: int,
) -> dict[str, Any]:
    chart_spec = render_request["chart_spec"]
    history_series = render_request["history_series"]
    first_series = history_series[0] if history_series else {"points": []}
    points = first_series.get("points", [])

    x_min = metadata.get("x_min")
    if x_min is None and points:
        x_min = points[0].get("ts")

    x_max = metadata.get("x_max")
    if x_max is None and points:
        x_max = points[-1].get("ts")

    return {
        "title": metadata.get("title", chart_spec.get("title")),
        "series_plotted": list(metadata.get("series_plotted", [])),
        "overlays_plotted": list(metadata.get("overlays_plotted", [])),
        "x_min": x_min,
        "x_max": x_max,
        "warnings": list(metadata.get("warnings", [])),
        "codegen_attempts": codegen_attempts,
    }


def _new_codegen_failure(
    *,
    request_id: str,
    code: str,
    message: str,
    codegen_attempts: int,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "status": "failed",
        "image_id": None,
        "image_mime_type": None,
        "image_path": None,
        "error": {
            "code": code,
            "message": message,
            "details": {} if details is None else details,
        },
        "render_metadata": {
            "title": None,
            "series_plotted": [],
            "overlays_plotted": [],
            "x_min": None,
            "x_max": None,
            "warnings": [],
            "codegen_attempts": codegen_attempts,
        },
    }


def _render_request_with_code(render_request: dict[str, Any], python_code: str) -> dict[str, Any]:
    copied = json.loads(json.dumps(render_request))
    copied["codegen"] = dict(copied.get("codegen") or {})
    copied["codegen"]["python_code"] = python_code
    return copied
