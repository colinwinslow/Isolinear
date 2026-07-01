"""Sandboxed execution of model-generated matplotlib chart code.

Promoted from the proven anchor (`src/Isolinear/codegen_sandbox_anchor.py`) into
a self-contained worker module per ADR-0029 and
`docs/specs/codegen-sandbox-module-promotion.md`. The sandbox security model is
unchanged and is specified by `docs/specs/worker-sandbox-spec.md` (proven by the
accepted sandbox-codegen BDD, scenarios A-G): an isolated `-I` subprocess with a
stripped environment, an import allowlist, an audit hook that fails closed on
network / subprocess / OS-mutation / out-of-sandbox filesystem events, a
fixed-output-path-only write rule, a subprocess timeout, `resource` limits where
available, and a maximum output-size cap.

This module imports nothing from `custom_components/isolinear/` or
`src/Isolinear/`; it validates against schemas bundled inside the worker package
(`isolinear_worker/schemas/`) through `._schema_validation`.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from ._schema_validation import ContractValidationError, validate_contract


SANDBOX_POLICY_VERSION = 1

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
_FORBIDDEN_GENERATED_IMPORTS = tuple(_POLICY["forbidden_imports"])
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
    return module_name in _ALLOWED_GENERATED_IMPORTS


def _generated_module_forbidden(module_name: str) -> bool:
    for forbidden_module in _FORBIDDEN_GENERATED_IMPORTS:
        if module_name == forbidden_module or module_name.startswith(forbidden_module + "."):
            return True
    return False


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
    fromlist = () if fromlist is None else fromlist
    for item in fromlist:
        # The module named after `from` (`name`) is what actually executes and is
        # already allowlisted above. A name pulled from it is an attribute or a
        # submodule of an already-trusted package (e.g. `from datetime import
        # datetime`, `from matplotlib import backends`); allow it. Still reject a
        # qualified name that resolves into a forbidden module.
        if item == "*":
            continue
        if _generated_module_forbidden(f"{name}.{item}"):
            raise ImportError(f"sandbox import not allowlisted: {name}.{item}")
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
                "MKL_NUM_THREADS",
                "MPLBACKEND",
                "MPLCONFIGDIR",
                "NUMEXPR_NUM_THREADS",
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "PYTHONIOENCODING",
                "PYTHONUTF8",
                "SYSTEMROOT",
                "TMP",
                "TEMP",
                "TMPDIR",
                "VECLIB_MAXIMUM_THREADS",
                "WINDIR",
            ],
        },
        "resource_limits": {
            "timeout": "subprocess_timeout",
            "cpu": "resource_rlimit_cpu_when_available",
            "memory": "resource_rlimit_as_when_available",
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
    render_request: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    work_root: str | Path | None = None,
    attempt_number: int = 1,
) -> dict[str, Any]:
    """Validate, static-check, and execute generated code in an isolated `-I`
    subprocess with a stripped env, audit hook, and bounded timeout.

    `work_root` is the directory the rendered PNG is written into (defaults to
    the current working directory). `attempt_number` is an internal counter used
    by `invoke_codegen_with_repair`; callers normally leave it at 1. Returns a
    RenderResult dict.
    """

    policy = default_codegen_sandbox_policy() if policy is None else policy
    output_directory = Path.cwd() if work_root is None else Path(work_root)
    request_id = str(render_request.get("request_id", "codegen-render"))

    try:
        validate_contract("codegen-sandbox-policy", policy)
        validate_contract("render-request", render_request)
        validate_contract("chart-spec", render_request["chart_spec"])
        for series in render_request["history_series"]:
            validate_contract("history-series", series)
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
    validate_contract("render-result", render_result)
    return render_result


def invoke_codegen_with_repair(
    render_request: dict[str, Any],
    *,
    repair: Callable[[str, dict[str, Any]], str],
    policy: dict[str, Any] | None = None,
    max_attempts: int = 2,
    work_root: str | Path | None = None,
) -> dict[str, Any]:
    """Capped repair loop around `invoke_codegen_sandbox`.

    `max_attempts` is the number of repair retries allowed after the initial
    attempt (so at most `1 + max_attempts` executions). The `repair` callable is
    injected — `repair(previous_code, error) -> next_code` — and is invoked after
    each retryable failure to produce the next code attempt; wiring it to a real
    repair *model* is a later packet (ADR-0029 packet 4). Static safety checks
    re-run for every attempt, including repaired ones. Returns the final
    RenderResult plus per-attempt diagnostics.
    """

    policy = default_codegen_sandbox_policy() if policy is None else policy
    max_attempts = max(0, int(max_attempts))
    codegen = render_request.get("codegen") if isinstance(render_request, dict) else None
    current_code = codegen.get("python_code", "") if isinstance(codegen, dict) else ""
    attempt_results = []
    repair_requests = []
    static_checks_run = 0

    for attempt_number in range(1, max_attempts + 2):
        attempt_request = _render_request_with_code(render_request, current_code)
        safety_result = static_safety_check(current_code, policy=policy)
        static_checks_run += 1
        render_result = invoke_codegen_sandbox(
            attempt_request,
            policy=policy,
            work_root=work_root,
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

        if attempt_number > max_attempts:
            break

        repair_requests.append(
            {
                "repair_attempt_number": attempt_number,
                "source_error_code": render_result["error"]["code"],
                "stack_trace_included": bool(
                    render_result["error"]["details"].get("traceback")
                ),
            }
        )

        current_code = repair(current_code, render_result["error"])

    final_result = attempt_results[-1]["render_result"]
    if final_result["status"] == "failed":
        final_result["error"]["details"]["repair_attempts"] = len(repair_requests)
        final_result["error"]["details"]["max_attempts"] = max_attempts
        final_result["error"]["details"]["static_safety_checks_run"] = static_checks_run
        validate_contract("render-result", final_result)

    return {
        "render_result": final_result,
        "attempt_results": attempt_results,
        "repair_requests": repair_requests,
        "max_attempts": max_attempts,
        "static_safety_checks_run": static_checks_run,
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
    if isinstance(node, ast.Import):
        for alias in node.names:
            _flag_disallowed_module(alias.name, node, policy=policy, violations=violations)
        return

    # ast.ImportFrom: the module named after `from` is what actually executes,
    # so it is the thing that must be allowlisted. Relative imports have no
    # importable module name and are rejected outright.
    if node.level:
        violations.append(
            {
                "code": "import_not_allowlisted",
                "message": "Relative imports are not allowed in sandboxed code.",
                "line": getattr(node, "lineno", 1),
                "module": ("." * node.level) + (node.module or ""),
            }
        )
        return

    base_module = node.module or ""
    _flag_disallowed_module(base_module, node, policy=policy, violations=violations)
    # Names pulled from an already-allowlisted module are attributes or
    # submodules of a trusted package (e.g. `from datetime import datetime`,
    # `from matplotlib import backends`) — allowed. Still reject a qualified name
    # that resolves into a forbidden module.
    for alias in node.names:
        if alias.name == "*":
            continue
        qualified = f"{base_module}.{alias.name}"
        if _module_forbidden(qualified, policy["forbidden_imports"]):
            violations.append(
                {
                    "code": "forbidden_import",
                    "message": f"Import is forbidden in sandboxed code: {qualified}",
                    "line": getattr(node, "lineno", 1),
                    "module": qualified,
                }
            )


def _flag_disallowed_module(
    module_name: str,
    node: ast.Import | ast.ImportFrom,
    *,
    policy: dict[str, Any],
    violations: list[dict[str, Any]],
) -> None:
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
        # Cap numeric threading libraries to a single thread. numpy's BLAS
        # backend (OpenBLAS) reserves per-core address space for its thread
        # pool at import time, scaled to the host CPU count; on a multi-core
        # host that reservation exceeds the sandbox RLIMIT_AS memory cap and
        # aborts with "OpenBLAS error: Memory allocation still failed" before
        # any chart is drawn. Pinning the thread count keeps matplotlib
        # rendering within the address-space limit. These variables only
        # *reduce* resource use, so they do not weaken the sandbox.
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
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
