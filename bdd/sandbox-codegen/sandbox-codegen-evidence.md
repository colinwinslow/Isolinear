# Sandbox Codegen Evidence

Run timestamp: 2026-06-06T17:18:01+00:00

BDD file:
`bdd/sandbox-codegen/sandbox-codegen-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: sandbox policy is Raspberry Pi compatible -> `CASE codegen_policy_is_pi_compatible`
- Scenario B: generated code renders through the fixed entry point -> `CASE fixed_entry_point_renders_fixed_output`
- Scenario C: allowlisted matplotlib pyplot renders with Agg backend -> `CASE matplotlib_pyplot_renders_with_agg_backend`
- Scenario D: unsafe generated code is rejected before execution -> `CASE unsafe_code_rejected_before_execution`
- Scenario E: secret, filesystem, and network access fail closed -> `CASE unsafe_code_rejected_before_execution` and `CASE allowlisted_matplotlib_read_denied_by_audit_hook`
- Scenario F: oversized output fails after execution -> `CASE output_size_limit_is_enforced`
- Scenario G: runtime error triggers capped repair loop -> `CASE runtime_error_uses_capped_repair_loop`

## Python Verification

Raw command:

```powershell
.\scripts\test.ps1 tests/
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 45 items

tests\test_codegen_sandbox_anchor.py ..........                          [ 22%]
tests\test_dashboard_card_anchor.py .......                              [ 37%]
tests\test_fake_vertical_slice.py .......................                [ 88%]
tests\test_transport_auth_anchor.py .....                                [100%]

============================= 45 passed in 34.09s ==============================
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\codegen_sandbox.py
```

Raw output:

```text
CASE codegen_policy_is_pi_compatible
{
  "case_id": "codegen_policy_is_pi_compatible",
  "given": {
    "run_timestamp": "2026-06-06T17:18:01+00:00",
    "schema": "docs/schemas/codegen-sandbox-policy.schema.json"
  },
  "then": {
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
      "zlib"
    ],
    "environment": {
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
        "WINDIR"
      ],
      "inherit_parent_environment": false
    },
    "execution_model": "isolated_subprocess",
    "filesystem": {
      "output_path": "provided_render_chart_output_path",
      "read_policy": "worker_runtime_roots_only",
      "write_policy": "fixed_output_path_only"
    },
    "memory_limit_mb": 256,
    "network_access": "denied",
    "python_flags": [
      "-I"
    ],
    "resource_limits": {
      "cpu": "resource_rlimit_cpu_when_available",
      "memory": "resource_rlimit_as_when_available",
      "timeout": "subprocess_timeout"
    },
    "timeout_seconds": 10
  },
  "when": {
    "operation": "validate_default_codegen_sandbox_policy"
  }
}
PASS codegen_policy_is_pi_compatible
CASE fixed_entry_point_renders_fixed_output
{
  "case_id": "fixed_entry_point_renders_fixed_output",
  "given": {
    "entry_point": "render_chart(data, output_path)",
    "render_mode": "codegen"
  },
  "then": {
    "safe_output_files": [
      "codegen-sandbox-anchor.png"
    ],
    "safe_result": {
      "error": null,
      "image_id": "codegen-sandbox-anchor.png",
      "image_mime_type": "image/png",
      "image_path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\.test-output\\tmpyxnq3cvk\\codegen-sandbox-anchor.png",
      "render_metadata": {
        "codegen_attempts": 1,
        "overlays_plotted": [],
        "series_plotted": [
          "upstairs_temperature"
        ],
        "title": "Sandboxed Temperature",
        "warnings": [],
        "x_max": "2026-06-05T09:00:00Z",
        "x_min": "2026-06-05T08:00:00Z"
      },
      "request_id": "codegen-sandbox-anchor",
      "status": "success"
    }
  },
  "when": {
    "operation": "invoke_codegen_sandbox"
  }
}
PASS fixed_entry_point_renders_fixed_output
CASE matplotlib_pyplot_renders_with_agg_backend
{
  "case_id": "matplotlib_pyplot_renders_with_agg_backend",
  "given": {
    "allowed_imports": [
      "matplotlib",
      "matplotlib.pyplot"
    ],
    "backend": "Agg"
  },
  "then": {
    "matplotlib_image_signature": "89504e470d0a1a0a",
    "matplotlib_output_files": [
      "codegen-sandbox-anchor.png"
    ],
    "matplotlib_result": {
      "error": null,
      "image_id": "codegen-sandbox-anchor.png",
      "image_mime_type": "image/png",
      "image_path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\.test-output\\tmpox5rwte3\\codegen-sandbox-anchor.png",
      "render_metadata": {
        "codegen_attempts": 1,
        "overlays_plotted": [],
        "series_plotted": [
          "upstairs_temperature"
        ],
        "title": "Sandboxed Temperature",
        "warnings": [
          "matplotlib_backend:Agg"
        ],
        "x_max": "2026-06-05T09:00:00Z",
        "x_min": "2026-06-05T08:00:00Z"
      },
      "request_id": "codegen-sandbox-anchor",
      "status": "success"
    }
  },
  "when": {
    "operation": "invoke_codegen_sandbox_with_matplotlib_pyplot"
  }
}
PASS matplotlib_pyplot_renders_with_agg_backend
CASE unsafe_code_rejected_before_execution
{
  "case_id": "unsafe_code_rejected_before_execution",
  "given": {
    "unsafe_examples": [
      "requests_import",
      "secret_file_read",
      "local_network_socket",
      "environment_read"
    ]
  },
  "then": {
    "unsafe_results": {
      "environment_read": {
        "error": {
          "code": "unsafe_code",
          "details": {
            "render_attempted": false,
            "violations": [
              {
                "code": "forbidden_import",
                "line": 1,
                "message": "Import is forbidden in sandboxed code: os",
                "module": "os"
              },
              {
                "code": "forbidden_attribute",
                "line": 4,
                "message": "Generated code may not access attribute environ."
              }
            ]
          },
          "message": "Generated code failed static sandbox safety checks."
        },
        "image_id": null,
        "image_mime_type": null,
        "image_path": null,
        "render_metadata": {
          "codegen_attempts": 0,
          "overlays_plotted": [],
          "series_plotted": [],
          "title": null,
          "warnings": [],
          "x_max": null,
          "x_min": null
        },
        "request_id": "codegen-sandbox-anchor",
        "status": "failed"
      },
      "local_network_socket": {
        "error": {
          "code": "unsafe_code",
          "details": {
            "render_attempted": false,
            "violations": [
              {
                "code": "forbidden_import",
                "line": 1,
                "message": "Import is forbidden in sandboxed code: socket",
                "module": "socket"
              },
              {
                "code": "forbidden_attribute",
                "line": 4,
                "message": "Generated code may not access attribute connect."
              },
              {
                "code": "forbidden_attribute",
                "line": 4,
                "message": "Generated code may not access attribute socket."
              }
            ]
          },
          "message": "Generated code failed static sandbox safety checks."
        },
        "image_id": null,
        "image_mime_type": null,
        "image_path": null,
        "render_metadata": {
          "codegen_attempts": 0,
          "overlays_plotted": [],
          "series_plotted": [],
          "title": null,
          "warnings": [],
          "x_max": null,
          "x_min": null
        },
        "request_id": "codegen-sandbox-anchor",
        "status": "failed"
      },
      "requests_import": {
        "error": {
          "code": "unsafe_code",
          "details": {
            "render_attempted": false,
            "violations": [
              {
                "code": "forbidden_import",
                "line": 1,
                "message": "Import is forbidden in sandboxed code: requests",
                "module": "requests"
              }
            ]
          },
          "message": "Generated code failed static sandbox safety checks."
        },
        "image_id": null,
        "image_mime_type": null,
        "image_path": null,
        "render_metadata": {
          "codegen_attempts": 0,
          "overlays_plotted": [],
          "series_plotted": [],
          "title": null,
          "warnings": [],
          "x_max": null,
          "x_min": null
        },
        "request_id": "codegen-sandbox-anchor",
        "status": "failed"
      },
      "secret_file_read": {
        "error": {
          "code": "unsafe_code",
          "details": {
            "render_attempted": false,
            "violations": [
              {
                "code": "forbidden_filesystem_access",
                "line": 2,
                "message": "Generated code may open only the provided output_path for writing."
              }
            ]
          },
          "message": "Generated code failed static sandbox safety checks."
        },
        "image_id": null,
        "image_mime_type": null,
        "image_path": null,
        "render_metadata": {
          "codegen_attempts": 0,
          "overlays_plotted": [],
          "series_plotted": [],
          "title": null,
          "warnings": [],
          "x_max": null,
          "x_min": null
        },
        "request_id": "codegen-sandbox-anchor",
        "status": "failed"
      }
    }
  },
  "when": {
    "operation": "run_static_safety_checks"
  }
}
PASS unsafe_code_rejected_before_execution
CASE allowlisted_matplotlib_read_denied_by_audit_hook
{
  "case_id": "allowlisted_matplotlib_read_denied_by_audit_hook",
  "given": {
    "allowed_imports": [
      "matplotlib.pyplot"
    ],
    "read_policy": "worker_runtime_roots_only"
  },
  "then": {
    "matplotlib_read_output_files": [],
    "matplotlib_read_result": {
      "error": {
        "code": "runtime_error",
        "details": {
          "resource_status": {
            "cpu": "not_available_on_platform",
            "memory": "not_available_on_platform"
          },
          "stderr": "Could not save font_manager cache sandbox allows writes only to the fixed output path\n",
          "stdout": "{\"error_message\": \"sandbox allows reads only from worker runtime roots\", \"resource_status\": {\"cpu\": \"not_available_on_platform\", \"memory\": \"not_available_on_platform\"}, \"status\": \"runtime_error\", \"traceback\": \"Traceback (most recent call last):\\n  File \\\"C:\\\\Users\\\\C12BA~1.WIN\\\\AppData\\\\Local\\\\Temp\\\\isolinear-codegen-sandbox-vg756j66\\\\sandbox_runner.py\\\", line 170, in <module>\\n    metadata = render_chart(_PAYLOAD[\\\"data\\\"], _OUTPUT_PATH)\\n  File \\\"<generated_chart>\\\", line 5, in render_chart\\n  File \\\"C:\\\\Users\\\\c.winslow\\\\OneDrive - Kagwerks\\\\Documents\\\\Repos\\\\Isolinear\\\\.venv\\\\Lib\\\\site-packages\\\\matplotlib\\\\pyplot.py\\\", line 2614, in imread\\n    return matplotlib.image.imread(fname, format)\\n           ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^\\n  File \\\"C:\\\\Users\\\\c.winslow\\\\OneDrive - Kagwerks\\\\Documents\\\\Repos\\\\Isolinear\\\\.venv\\\\Lib\\\\site-packages\\\\matplotlib\\\\image.py\\\", line 1520, in imread\\n    with img_open(fname) as image:\\n         ~~~~~~~~^^^^^^^\\n  File \\\"C:\\\\Users\\\\c.winslow\\\\OneDrive - Kagwerks\\\\Documents\\\\Repos\\\\Isolinear\\\\.venv\\\\Lib\\\\site-packages\\\\PIL\\\\Image.py\\\", line 3635, in open\\n    fp = builtins.open(filename, \\\"rb\\\")\\n  File \\\"C:\\\\Users\\\\C12BA~1.WIN\\\\AppData\\\\Local\\\\Temp\\\\isolinear-codegen-sandbox-vg756j66\\\\sandbox_runner.py\\\", line 75, in _audit\\n    raise PermissionError(\\\"sandbox allows reads only from worker runtime roots\\\")\\nPermissionError: sandbox allows reads only from worker runtime roots\\n\"}\n",
          "traceback": "Traceback (most recent call last):\n  File \"C:\\Users\\C12BA~1.WIN\\AppData\\Local\\Temp\\isolinear-codegen-sandbox-vg756j66\\sandbox_runner.py\", line 170, in <module>\n    metadata = render_chart(_PAYLOAD[\"data\"], _OUTPUT_PATH)\n  File \"<generated_chart>\", line 5, in render_chart\n  File \"C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\.venv\\Lib\\site-packages\\matplotlib\\pyplot.py\", line 2614, in imread\n    return matplotlib.image.imread(fname, format)\n           ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^\n  File \"C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\.venv\\Lib\\site-packages\\matplotlib\\image.py\", line 1520, in imread\n    with img_open(fname) as image:\n         ~~~~~~~~^^^^^^^\n  File \"C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\.venv\\Lib\\site-packages\\PIL\\Image.py\", line 3635, in open\n    fp = builtins.open(filename, \"rb\")\n  File \"C:\\Users\\C12BA~1.WIN\\AppData\\Local\\Temp\\isolinear-codegen-sandbox-vg756j66\\sandbox_runner.py\", line 75, in _audit\n    raise PermissionError(\"sandbox allows reads only from worker runtime roots\")\nPermissionError: sandbox allows reads only from worker runtime roots\n"
        },
        "message": "sandbox allows reads only from worker runtime roots"
      },
      "image_id": null,
      "image_mime_type": null,
      "image_path": null,
      "render_metadata": {
        "codegen_attempts": 1,
        "overlays_plotted": [],
        "series_plotted": [],
        "title": null,
        "warnings": [],
        "x_max": null,
        "x_min": null
      },
      "request_id": "codegen-sandbox-anchor",
      "status": "failed"
    }
  },
  "when": {
    "operation": "invoke_codegen_sandbox_with_pyplot_imread"
  }
}
PASS allowlisted_matplotlib_read_denied_by_audit_hook
CASE output_size_limit_is_enforced
{
  "case_id": "output_size_limit_is_enforced",
  "given": {
    "max_output_bytes": 1024
  },
  "then": {
    "oversized_result": {
      "error": {
        "code": "output_too_large",
        "details": {
          "actual_output_bytes": 2048,
          "max_output_bytes": 1024,
          "output_path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\.test-output\\tmpduj1aylz\\codegen-sandbox-anchor.png"
        },
        "message": "Generated code produced an output image larger than policy allows."
      },
      "image_id": null,
      "image_mime_type": null,
      "image_path": null,
      "render_metadata": {
        "codegen_attempts": 1,
        "overlays_plotted": [],
        "series_plotted": [],
        "title": null,
        "warnings": [],
        "x_max": null,
        "x_min": null
      },
      "request_id": "codegen-sandbox-anchor",
      "status": "failed"
    }
  },
  "when": {
    "operation": "invoke_codegen_sandbox_with_oversized_output"
  }
}
PASS output_size_limit_is_enforced
CASE runtime_error_uses_capped_repair_loop
{
  "case_id": "runtime_error_uses_capped_repair_loop",
  "given": {
    "max_repair_attempts": 2
  },
  "then": {
    "render_result": {
      "error": {
        "code": "runtime_error",
        "details": {
          "max_repair_attempts": 2,
          "repair_attempts": 2,
          "resource_status": {
            "cpu": "not_available_on_platform",
            "memory": "not_available_on_platform"
          },
          "static_safety_checks_run": 3,
          "stderr": "",
          "stdout": "{\"error_message\": \"second repair still fails\", \"resource_status\": {\"cpu\": \"not_available_on_platform\", \"memory\": \"not_available_on_platform\"}, \"status\": \"runtime_error\", \"traceback\": \"Traceback (most recent call last):\\n  File \\\"C:\\\\Users\\\\C12BA~1.WIN\\\\AppData\\\\Local\\\\Temp\\\\isolinear-codegen-sandbox-xfm63nyg\\\\sandbox_runner.py\\\", line 170, in <module>\\n    metadata = render_chart(_PAYLOAD[\\\"data\\\"], _OUTPUT_PATH)\\n  File \\\"<generated_chart>\\\", line 2, in render_chart\\nRuntimeError: second repair still fails\\n\"}\n",
          "traceback": "Traceback (most recent call last):\n  File \"C:\\Users\\C12BA~1.WIN\\AppData\\Local\\Temp\\isolinear-codegen-sandbox-xfm63nyg\\sandbox_runner.py\", line 170, in <module>\n    metadata = render_chart(_PAYLOAD[\"data\"], _OUTPUT_PATH)\n  File \"<generated_chart>\", line 2, in render_chart\nRuntimeError: second repair still fails\n"
        },
        "message": "second repair still fails"
      },
      "image_id": null,
      "image_mime_type": null,
      "image_path": null,
      "render_metadata": {
        "codegen_attempts": 3,
        "overlays_plotted": [],
        "series_plotted": [],
        "title": null,
        "warnings": [],
        "x_max": null,
        "x_min": null
      },
      "request_id": "codegen-sandbox-anchor",
      "status": "failed"
    },
    "repair_requests": [
      {
        "repair_attempt_number": 1,
        "source_error_code": "runtime_error",
        "stack_trace_included": true
      },
      {
        "repair_attempt_number": 2,
        "source_error_code": "runtime_error",
        "stack_trace_included": true
      }
    ],
    "static_safety_checks_run": 3
  },
  "when": {
    "operation": "invoke_codegen_with_repair"
  }
}
PASS runtime_error_uses_capped_repair_loop
PASS codegen_sandbox
```
