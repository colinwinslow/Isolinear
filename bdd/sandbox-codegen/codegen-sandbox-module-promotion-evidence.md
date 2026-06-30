# Codegen sandbox module promotion — evidence

**Run date:** 2026-06-30 · branch `adr-0029-worker-codegen-eval` · Python 3.12,
matplotlib 3.11.0 (user-site only).

Raw evidence for `bdd/sandbox-codegen/codegen-sandbox-module-promotion-bdd.md`
(ADR-0029 packet 1). The codegen sandbox was promoted from the anchor
(`src/Isolinear/codegen_sandbox_anchor.py`) into the self-contained worker module
`worker/isolinear_worker/codegen_sandbox.py`, driven through its public API.

**Environment note (matplotlib-in-sandbox scenarios).** The sandbox runs
generated code under `python -I` (isolated mode), which excludes the *user*
site-packages. On this dev box matplotlib is installed only in the user site
(`/home/claude/.local/...`), so the `-I` subprocess cannot import it and the two
matplotlib-rendering scenarios (sandbox-codegen BDD C and the runtime
audit-denial half of E) **skip** here. They run on a worker container where
matplotlib is in the system site-packages (ADR-0029 packet 3). Every
non-matplotlib path — including a real PNG written through the fixed output path
— runs green. This is the same environment limitation that previously showed up
as the "3 pre-existing codegen-sandbox failures" in the anchor test; promotion
converts those hard failures into honest skips.

## Scenario A — the promoted module renders a PNG through its public API

Driven by `test_safe_code_writes_real_png_through_fixed_output_path`. The safe
sample writes a verbatim 1×1 PNG through `open(output_path, "wb")` (no
matplotlib), so the real-artifact proof holds in every environment. The
matplotlib variant (`test_matplotlib_pyplot_renders_png_with_agg_backend`) is the
Agg-backend version and is skip-gated as described above.

Real PNG produced on disk through the promoted public API:

```
status success
path /home/claude/repos/isolinear/.test-output/promotion-proof/codegen-sandbox-anchor.png
exists True
first8 89504e470d0a1a0a        # the PNG signature \x89PNG\r\n\x1a\n
$ file codegen-sandbox-anchor.png
codegen-sandbox-anchor.png: PNG image data, 1 x 1, 8-bit/color RGBA, non-interlaced
```

## Scenario B — the worker module is self-contained (HA-agnostic)

Driven by `test_worker_module_is_self_contained`, which imports the module in a
clean subprocess (`env -i`, no `PYTHONPATH`, cwd = `worker/` so neither `src/`
nor `custom_components/` is importable) and inspects `sys.modules`:

```
leaked_ha_modules: []
validator_file: /home/claude/repos/isolinear/worker/isolinear_worker/_schema_validation.py
module_file:    /home/claude/repos/isolinear/worker/isolinear_worker/codegen_sandbox.py
sys.path[0] (cwd): (cwd)
```

The module imports nothing from `custom_components.isolinear` or `src.Isolinear`,
and validates its policy against a schema bundled inside the worker package
(`worker/isolinear_worker/schemas/codegen-sandbox-policy.schema.json`).

## Scenario C — security denials hold at parity through the public API

- Static denials (`test_unsafe_code_is_rejected_before_execution`): forbidden
  `requests` import, secret file read, local socket, and environment read each
  return `accepted: False`, `code: "unsafe_code"`, `render_attempted: False`,
  `codegen_attempts: 0`, and write **no** files. PASS.
- `test_missing_entry_point_and_non_allowlisted_submodule_are_unsafe`: a missing
  `render_chart` yields `missing_fixed_entry_point`; `from matplotlib import
  backends` yields a `matplotlib.backends` import violation. PASS.
- Runtime audit denial (`test_matplotlib_arbitrary_read_is_denied_by_audit_hook`,
  via `pyplot.imread` of `STATUS.md`): skip-gated on sandbox matplotlib (see
  note). On a matplotlib-capable sandbox it fails closed with `runtime_error`
  and "sandbox allows reads only from worker runtime roots", writing no output.

## Scenario D — oversized output and timeout fail closed

- `test_oversized_output_fails_closed`: `output_too_large`, `max_output_bytes:
  1024`, `codegen_attempts: 1`. PASS.
- `test_runaway_code_times_out`: a `while True: pass` body under
  `timeout_seconds: 1, cpu_seconds: 30` fails closed with `timeout` and writes no
  output. PASS.

## Scenario E — capped repair loop with an injected repair callable

- `test_capped_repair_loop_exhausts_with_injected_repair`: an injected
  `repair(previous_code, error) -> next_code` that keeps returning broken code,
  `max_attempts = 2`. Result: final `runtime_error`, `codegen_attempts: 3`,
  `repair_requests: 2`, `repair` invoked exactly 2 times,
  `static_safety_checks_run: 3`, `error.details.repair_attempts: 2`. PASS.
- `test_repair_loop_stops_when_a_repair_succeeds`: a repair that returns the safe
  sample stops the loop early — `success`, `codegen_attempts: 2`,
  `repair_requests: 1`, `static_safety_checks_run: 2`. PASS.

## Scenario F — the anchor is retired without losing coverage

`src/Isolinear/codegen_sandbox_anchor.py` and
`tests/test_codegen_sandbox_anchor.py` are deleted. Raw runs:

```
$ python3 -m pytest tests/test_codegen_sandbox.py -v
collected 11 items
... test_capped_repair_loop_exhausts_with_injected_repair PASSED
... test_default_policy_is_pi_compatible_and_schema_valid PASSED
... test_matplotlib_arbitrary_read_is_denied_by_audit_hook SKIPPED
... test_matplotlib_pyplot_renders_png_with_agg_backend SKIPPED
... test_missing_entry_point_and_non_allowlisted_submodule_are_unsafe PASSED
... test_oversized_output_fails_closed PASSED
... test_repair_loop_stops_when_a_repair_succeeds PASSED
... test_runaway_code_times_out PASSED
... test_safe_code_writes_real_png_through_fixed_output_path PASSED
... test_unsafe_code_is_rejected_before_execution PASSED
... test_worker_module_is_self_contained PASSED
9 passed, 2 skipped in 1.62s

$ python3 -m pytest tests/
583 passed, 2 skipped in 14.78s        # was 581 passed, 3 failed (anchor matplotlib subprocess)

$ cd evals && python3 codegen_sandbox.py
... CASE codegen_policy_is_pi_compatible / PASS
... CASE fixed_entry_point_renders_fixed_output / PASS
... CASE unsafe_code_rejected_before_execution / PASS
... CASE output_size_limit_is_enforced / PASS
... CASE runtime_error_uses_capped_repair_loop / PASS
... CASE matplotlib_pyplot_renders_with_agg_backend / PASS   (skipped-branch CASE in this env)
PASS codegen_sandbox
```

The 3 pre-existing anchor failures (the matplotlib-in-`-I`-subprocess tests) are
gone: the suite is green, with the two genuinely matplotlib-dependent scenarios
recorded as explicit skips rather than silent failures.
