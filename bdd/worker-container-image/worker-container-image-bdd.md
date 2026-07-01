# Worker container image: standalone amd64 Docker image with matplotlib — BDD

## Status

Draft. Paired with
[docs/specs/worker-container-image.md](../../docs/specs/worker-container-image.md).

Evidence file:

- `bdd/worker-container-image/worker-container-image-evidence.md`

## Why this BDD exists

This pins down the standalone worker **container image** (ADR-0029 packet 3): a
single-arch `linux/amd64` Docker image whose **system** site-packages carry
matplotlib, so the sandbox's isolated `python -I` subprocess can import it and
the worker actually renders. It proves the image builds, fails closed without a
token, reports `ready` (matplotlib importable under `-I`), renders a real PNG
through a running container, flips the three matplotlib-gated tests from skipped
to passing, and contains nothing from the Home Assistant integration.

## Verification split

Docker is **not** installed in the authoring environment, so the image cannot be
built or run here. Each scenario below is tagged:

- **[STATIC — verifiable now]** — provable from the files on disk plus the
  packet-1/2 code, without Docker. Filled with real outputs in the evidence file.
- **[DEFERRED — needs Docker host]** — requires a real `docker build` / `docker
  run` on a `linux/amd64` Docker host (the deploy target CT103 `10.0.1.39`, or
  any Docker host). Marked `DEFERRED (needs Docker host)` in the evidence file
  with the exact command to run, following the repo's "live HACS retest"
  deferral pattern. Do **not** fabricate build logs.

## Scenarios

### Scenario A — [DEFERRED] image builds on amd64

**Given** `worker/Dockerfile` and `worker/.dockerignore` on disk and a
`linux/amd64` Docker host
**When** `docker build --platform linux/amd64 -t isolinear-worker:dev worker/`
runs
**Then** the build succeeds
**And** matplotlib installs from a prebuilt wheel into the interpreter's system
site-packages (no compiler / source build in the image)
*(DEFERRED — needs Docker host. Statically here: the Dockerfile is well-formed,
uses `python:3.12-slim`, and `pip install`s `worker/requirements.txt` as root
before `USER worker`.)*

### Scenario B — [DEFERRED] container starts and fails closed without a token

**Given** the built image
**When** `docker run --rm isolinear-worker:dev` runs with **no**
`ISOLINEAR_WORKER_TOKEN`
**Then** the container exits non-zero with the packet-2 message
`ISOLINEAR_WORKER_TOKEN is required; refusing to start without a bearer token.`
**And** no socket is bound and no request is served
*(DEFERRED — needs Docker host. Statically here: packet 2's
`test_entry_point_exits_nonzero_without_token` already proves fail-closed
startup; the image sets no `ISOLINEAR_WORKER_TOKEN`, so this behavior is
inherited unchanged.)*

### Scenario C — [DEFERRED] `/v1/health` returns `ready` (matplotlib importable in `-I`)

**Given** the built image run with a valid 24+char `ISOLINEAR_WORKER_TOKEN` and
port `8080` published
**When** an authenticated `GET /v1/health` is sent
(`Authorization: Bearer <token>`, `X-Isolinear-Worker-API-Version: 1`)
**Then** the response is HTTP `200`
**And** the body is `{"health": {...}}` with `status == "ready"`,
`capabilities.rendering == true`, and the `matplotlib_import` check `ok`
**And** `docker inspect` reports the container `healthy` (the `HEALTHCHECK` gates
on `health.status == "ready"`)
*(DEFERRED — needs Docker host. This is the anchor artifact: the first time the
worker can actually render, because the image installs matplotlib into the
**system** site-packages the `-I` subprocess reads. Statically here: the
readiness probe `_sandbox_can_import_matplotlib()` runs `python -I -c "import
matplotlib"` — so system-site install is exactly what flips it to `ok`/`ready`.)*

### Scenario D — [DEFERRED] authenticated `/v1/render` produces a real PNG through the running container

**Given** the running container with a valid token
**And** a valid transport envelope `{version: 1, operation: "render_chart",
request_id, render_request}` whose `render_request` is `render_mode: "codegen"`
with generated Python that imports `matplotlib` and draws a chart
**When** the request is POSTed to `/v1/render` with valid auth and version
headers
**Then** the response is HTTP `200` with `render_result.status == "success"`
**And** a valid PNG (signature `89504e470d0a1a0a`) exists at the returned
`image_path` inside the container's `work_root`
*(DEFERRED — needs Docker host. Statically here: packet 2 proves this exact path
end-to-end through the HTTP layer into the sandbox; only the matplotlib-render
assertion is gated, and it un-gates inside the container.)*

### Scenario E — [DEFERRED] the 3 previously-skipped matplotlib tests pass inside the container

**Given** the built image with the repo mounted
**When** `pytest tests/test_codegen_sandbox.py tests/test_worker_http_server.py`
runs **inside** the container
**Then** the three `skipUnless(_SANDBOX_HAS_MATPLOTLIB, ...)` tests —
`test_matplotlib_pyplot_renders_png_with_agg_backend`,
`test_matplotlib_arbitrary_read_is_denied_by_audit_hook`,
`test_authenticated_render_matplotlib_reports_agg_backend` — **run and pass**
instead of skipping
**And** the rest of the suite stays green
*(DEFERRED — needs Docker host. Statically here: on the authoring dev box these 3
skip because `python -I` cannot import matplotlib; the whole point of the system-
site install is that inside the container `_SANDBOX_HAS_MATPLOTLIB` is `True`.)*

### Scenario F — [DEFERRED] the image contains nothing from `custom_components`/`src`

**Given** the built image
**When** the image filesystem is searched for `custom_components` or a
`src/Isolinear` path
**Then** none is found (the image carries only the `isolinear_worker/` package,
its bundled schemas, and its pip-installed dependencies)
*(DEFERRED — needs Docker host for the in-image `find`. Statically here: the
build context is `worker/` (so `custom_components/`, `src/`, `frontend/` are
outside it and cannot be copied), the `.dockerignore` excludes cruft, and the
packet-1/2 import-graph checks already prove
`isolinear_worker.http_server`/`codegen_sandbox` import nothing from those
trees.)*

### Scenario G — [STATIC] entry point maps to the packet-2 module `__main__`

**Given** `worker/Dockerfile`
**When** its `ENTRYPOINT` is read
**Then** it is exec-form `["python", "-m", "isolinear_worker.http_server"]`
**And** `worker/isolinear_worker/http_server.py` carries
`if __name__ == "__main__": raise SystemExit(main())` (so `python -m
isolinear_worker.http_server` runs the server; no separate `__main__.py` is
needed)
*(STATIC — verifiable now.)*

### Scenario H — [STATIC] env vars and no baked secret match the packet-2 config contract

**Given** `worker/Dockerfile`
**When** its `ENV` lines and the packet-2 `load_config_from_env` are compared
**Then** every `ISOLINEAR_WORKER_*` name the image sets/documents
(`ISOLINEAR_WORKER_BIND_HOST`, `ISOLINEAR_WORKER_BIND_PORT`,
`ISOLINEAR_WORKER_WORK_ROOT`) matches a name `load_config_from_env` reads
**And** `ISOLINEAR_WORKER_TOKEN` is **not** set anywhere in the image (supplied
at runtime)
**And** `EXPOSE` matches the `ISOLINEAR_WORKER_BIND_PORT` default (`8080`)
*(STATIC — verifiable now.)*

### Scenario I — [STATIC] the unit suite stays green and no runtime dependency is added

**Given** the packet-3 files on disk
**When** `python3 -m pytest tests/ -q` runs on the authoring box
**Then** the result is `595 passed, 3 skipped` (the 3 matplotlib skips only flip
inside the container)
**And** `worker/requirements.txt` still declares only `matplotlib` and
`jsonschema`, appropriately pinned
*(STATIC — verifiable now.)*

## Evidence

The implementing slice produces an evidence file at
`bdd/worker-container-image/worker-container-image-evidence.md` containing the
**raw** outputs (not summaries) for the STATIC scenarios (the Dockerfile and
`.dockerignore` contents, the entry-point grep, the env-var/config-contract
diff, the requirements pin, the full-suite run) and, for each DEFERRED scenario,
a `DEFERRED (needs Docker host)` marker with the exact `docker` command a human
or CI runs to complete it on a `linux/amd64` Docker host.
