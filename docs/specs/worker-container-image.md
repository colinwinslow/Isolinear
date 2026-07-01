---
status: draft
date: 2026-07-01
depends-on-adrs: [0029, 0012, 0014, 0008, 0001]
---

# Worker container image: standalone amd64 Docker image with matplotlib

## Status

Draft. Defines the contract surface for the standalone worker **container image**
per ADR-0029 (revive the isolated worker for codegen evaluation). This is
ADR-0029 **packet 3**. It packages the packet-2 HTTP server
(`worker/isolinear_worker/http_server.py`) and the packet-1 codegen sandbox
(`worker/isolinear_worker/codegen_sandbox.py`) into a single-arch (`linux/amd64`)
Docker image whose **system** site-packages carry matplotlib, so the sandbox's
isolated `-I` subprocess can import it and `/v1/health` reports `ready`.

Left `draft` (not `accepted`) because the core proof — a real image build, a
running container answering `/v1/health` with `ready`, and the three
matplotlib-gated tests passing *inside* the container — is a **deferred
live-verification requirement** that this authoring environment cannot execute
(Docker is not installed here). The static contract below is complete and
verified; acceptance waits on the first live build on a Docker host, matching
how the repo defers "live HACS retest" and how packet 2's dev-box matplotlib
limitation is handled. See **Proof requirements** for the exact split.

## Related docs

- [bdd/worker-container-image/worker-container-image-bdd.md](../../bdd/worker-container-image/worker-container-image-bdd.md) — observable behavior
- [worker-http-server.md](worker-http-server.md) — packet 2, the server this image runs
- [codegen-sandbox-module-promotion.md](codegen-sandbox-module-promotion.md) — packet 1, the sandbox `-I` subprocess that needs matplotlib
- [worker-sandbox-spec.md](worker-sandbox-spec.md) — the sandbox security model (inherited, unchanged)
- ADR-0012 — worker transport and authentication (bearer token, versioned headers)
- ADR-0014 — worker health/readiness endpoint
- ADR-0029 — revive the worker for codegen evaluation (standalone Docker first; multi-arch + HA add-on deferred)
- [STATUS.md](../../STATUS.md) — current phase and active work

## Context

Packets 1 and 2 produced a self-contained, HA-agnostic worker package
(`worker/isolinear_worker/`) and a stdlib HTTP server that speaks the ADR-0012
transport in front of the codegen sandbox. Both packets deliberately deferred the
one thing that makes the worker *actually able to render*: an environment where
matplotlib is importable from the exact interpreter and flags the sandbox uses.

ADR-0017 was forced into in-process trusted rendering because **matplotlib would
not install reliably in the Home Assistant Python environment**. ADR-0029's whole
premise is that this blocker dissolves when matplotlib lives in the *worker's own
container image*, never in HA's Python. Packet 3 is where that image is built.

The subtlety that makes packet 3 non-trivial (and is the reason it is its own
packet): the sandbox runs generated code under **`python -I`** (isolated mode).
`-I` implies `-E` (ignore `PYTHON*` env vars) and `-s` (exclude the **user**
site-packages directory). So installing matplotlib into a user-site location
(`pip install --user`) or into a virtualenv that the `-I` subprocess does not
inherit would leave the sandbox unable to import it — health would report
`not_ready` even though `pip show matplotlib` succeeds. The readiness probe
proves this precisely: `_sandbox_can_import_matplotlib()` runs
`python -I -c "import matplotlib"` (`http_server.py`). Therefore the image
**must** install matplotlib into the interpreter's **system** site-packages, so a
bare `python -I` can import it. This is the core requirement of packet 3.

Nothing here is user-visible yet. The value is a runnable artifact: `docker run`
a worker whose `/v1/health` returns `ready`, which packets 4 (codegen generation
+ repair model) and 5 (end-to-end + reliability eval) build on, and which the
homelab two-repo split later deploys to CT103 (`10.0.1.39`, amd64, GPU-less
Docker).

## Behavior contract

### Base image

- **`python:3.12-slim` (Debian `bookworm`-based, `linux/amd64` only).** Chosen so:
  - **matplotlib installs from a prebuilt manylinux wheel into the interpreter's
    system site-packages** — no compiler, no source build, no BLAS/Fortran
    toolchain in the image. The `-slim` variant already carries the shared libs a
    manylinux matplotlib wheel links against (glibc); the wheel bundles its own
    freetype/libpng, so no extra `apt` packages are required for a headless `Agg`
    render. (If a live build surfaces a missing shared lib, the fix is a minimal,
    named `apt-get install` layer — see "System packages" — not a source build.)
  - **Python 3.12** matches this repo's runtime (the dev box and CI run 3.12; the
    sandbox, server, and tests are authored against 3.12) so the container
    interpreter behaves identically to where the code was proven. The base image
    is pinned to the `3.12-slim` **tag** (not `latest`, not bare `slim`); a
    stronger digest pin is an option a live build can add.
  - **Single-arch `linux/amd64`.** ADR-0029 defers multi-arch/aarch64 builds; the
    deploy target (CT103) is amd64. The Dockerfile must not preclude a future
    `--platform`/buildx multi-arch build, but does not attempt one.

### matplotlib into the system site-packages (the core requirement)

- `pip install` runs as **root, before dropping to the non-root runtime user**,
  with no `--user` flag and no virtualenv, so matplotlib and jsonschema land in
  the base image's **system** site-packages (`/usr/local/lib/python3.12/
  site-packages`). A bare `python -I -c "import matplotlib"` — exactly what the
  sandbox and the readiness probe run — must succeed.
- Dependencies come from `worker/requirements.txt` (matplotlib + jsonschema,
  already pinned: `matplotlib>=3.7,<4`, `jsonschema>=4,<5`). The requirements file
  is copied and installed in its **own layer, before** the application code is
  copied, so the (slow) matplotlib wheel install is cached across code-only
  rebuilds. `pip install --no-cache-dir` keeps the wheel cache out of the image
  layer.
- The sandbox's `Agg` backend needs no display: the sandbox already sets
  `MPLBACKEND=Agg` in the `-I` subprocess environment (`_sandbox_environment` in
  `codegen_sandbox.py`), and it points `MPLCONFIGDIR`/`HOME` at a per-render temp
  dir, so no writable global matplotlib config dir is required in the image.

### System packages

- Keep `apt` layers minimal or empty. The manylinux matplotlib wheel is
  self-contained for a headless `Agg` render on `bookworm-slim`, so the baseline
  Dockerfile installs **no** extra apt packages. If a live build reveals a
  genuinely missing shared library, the remedy is a single, explicitly-named
  `apt-get update && apt-get install --no-install-recommends <lib> && rm -rf
  /var/lib/apt/lists/*` layer — documented, not a blanket toolchain.

### Non-root runtime user and the work root

- Create an unprivileged user/group (e.g. `worker`, a fixed non-zero UID/GID) and
  `USER worker` for the runtime. Generated code already runs in an isolated `-I`
  subprocess (ADR-0008); running the *server* as non-root is defense-in-depth and
  standard container hygiene.
- The image sets `ISOLINEAR_WORKER_WORK_ROOT` to a fixed path (e.g.
  `/var/lib/isolinear-worker/work`), creates it, and `chown`s it to the runtime
  user so the server can write rendered PNGs there. That path is declared a
  `VOLUME` so a host/orchestrator can mount durable or tmpfs storage for
  artifacts (the worker is stateless beyond this artifact dir — ADR-0029). When no
  `work_root` is configured, packet 2 falls back to a per-process temp dir; the
  image sets the env var explicitly so behavior is predictable.

### 12-factor configuration (env only; no baked secrets)

- **No secrets are baked into the image.** `ISOLINEAR_WORKER_TOKEN` is **not** set
  in the Dockerfile; it is supplied at `docker run` time (`-e` / env file /
  orchestrator secret). The image ships only non-secret defaults.
- The env vars the image sets/documents match `load_config_from_env` in
  `http_server.py` **exactly**:

  | Env var | Set in image? | Value / default |
  |---|---|---|
  | `ISOLINEAR_WORKER_TOKEN` | **No** (runtime-supplied secret) | *(required at runtime; server fails closed if unset/short — packet 2)* |
  | `ISOLINEAR_WORKER_BIND_HOST` | Optional | defaults to `0.0.0.0` in packet 2; image may set it explicitly |
  | `ISOLINEAR_WORKER_BIND_PORT` | Yes | `8080` (matches packet-2 default; also the `EXPOSE`d port) |
  | `ISOLINEAR_WORKER_WORK_ROOT` | Yes | `/var/lib/isolinear-worker/work` |

- Fail-closed startup is already enforced by packet 2: with no valid
  `ISOLINEAR_WORKER_TOKEN` the entry point exits non-zero and binds no socket. The
  image inherits that behavior unchanged — a container started without a token
  exits immediately rather than serving unauthenticated.

### Entry point and exposed port

- `ENTRYPOINT` (exec form) is **`["python", "-m", "isolinear_worker.http_server"]`**,
  which maps directly to packet 2's module entry point (`__main__` guard →
  `main()` → `load_config_from_env()` → `serve()`). Verified statically: the
  module has an `if __name__ == "__main__": raise SystemExit(main())` guard and no
  separate `__main__.py` is needed (`python -m isolinear_worker.http_server`
  executes the module directly).
- `WORKDIR` is set to the worker package root (the dir containing the
  `isolinear_worker/` package) so `-m isolinear_worker.http_server` resolves.
- `EXPOSE 8080` documents the bind port (matches the `ISOLINEAR_WORKER_BIND_PORT`
  default). `EXPOSE` is documentation only; actual publishing is `-p` at run time.

### Container HEALTHCHECK

- A `HEALTHCHECK` hits `GET /v1/health` and reports the container healthy only
  when the worker is *ready to render*.
- **Auth tradeoff, reasoned through:** `/v1/health` requires the bearer token
  (auth is checked first, on both endpoints — packet 2). The healthcheck therefore
  must present the same token. It reads it from the container's own environment:
  the check runs a tiny stdlib probe (no `curl` dependency added) as
  `python -c` that reads `ISOLINEAR_WORKER_TOKEN` and
  `ISOLINEAR_WORKER_BIND_PORT` from `os.environ` and issues an authenticated
  `GET http://127.0.0.1:$PORT/v1/health` with `Authorization: Bearer <token>` and
  `X-Isolinear-Worker-API-Version: 1`, then exits `0` only if the HTTP status is
  `200` **and** the parsed body's `health.status == "ready"`.
  - This is safe: the token is already present in the container's env (that is how
    the server itself reads it); the healthcheck reads it from the same place and
    never writes it to a layer, an image env default, or a log. It is *not* baked
    into the image — it arrives at runtime like every other secret.
  - Gating on `health.status == "ready"` (not merely HTTP `200`) means the
    container is reported unhealthy until matplotlib is importable under `-I` — the
    precise readiness the worker exists to provide. This is the observable signal
    that the "install into system site-packages" requirement actually worked.
  - The probe uses only the standard library (`urllib.request`, `json`, `os`) so
    no extra package (`curl`/`wget`) is added to the image.

### `.dockerignore` — HA-agnostic image (worker package + requirements only)

- A `worker/.dockerignore` (evaluated against the **worker/** build context; the
  image is built with `worker/` as context) keeps everything that is not the
  worker package and its requirements out of the image. Because the build context
  is `worker/`, `custom_components/`, `src/`, and `frontend/` are already outside
  the context and cannot be copied; the `.dockerignore` additionally excludes
  build/test cruft inside `worker/`:
  - `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`
  - `*.md`, docs, and any local scratch/output dirs
  - VCS metadata that a broader context might drag in
- **Self-containment is already proven** (packet 1 and packet 2 import-graph
  checks): `isolinear_worker.http_server` and `isolinear_worker.codegen_sandbox`
  import **only** stdlib + `matplotlib`/`jsonschema` (installed from
  requirements) + bundled schemas under `isolinear_worker/schemas/`. The image
  needs **nothing** from `custom_components/isolinear/` or `src/Isolinear/`. The
  BDD pins a scenario asserting the built image filesystem contains no
  `custom_components`/`src` path.

## Anchor artifact

The simplest concrete observable version of the thing: a `docker build` of
`worker/Dockerfile` (context `worker/`) produces an image; `docker run` of that
image with a valid `ISOLINEAR_WORKER_TOKEN` starts the server; an authenticated
`GET /v1/health` against the running container returns HTTP `200` with
`health.status == "ready"` (matplotlib importable under `-I` inside the
container). That single "`ready` from a running container" is the artifact packet
3 exists to produce — it is the first time the worker can actually render.

Because Docker is not available in the authoring environment, this anchor is a
**deferred live-verification artifact** (see Proof requirements). What *is*
built and verified here without Docker: the Dockerfile, `.dockerignore`, and
requirements are on disk, well-formed, and statically consistent with the packet-2
entry point and config contract.

## Implementation order

Concrete-first, with the live proof deferred to a Docker host:

1. **Spec + BDD + evidence scaffold** (this spec, the paired BDD, and an evidence
   file whose static sections are filled with real outputs and whose Docker-host
   sections are marked `DEFERRED (needs Docker host)` with the exact commands).
2. **`worker/requirements.txt`** — confirm matplotlib + jsonschema are present and
   appropriately pinned (they are: `matplotlib>=3.7,<4`, `jsonschema>=4,<5`); no
   change unless the pins are wrong.
3. **`worker/.dockerignore`** — exclude cruft; rely on the `worker/`-scoped build
   context to keep `custom_components`/`src`/`frontend` out.
4. **`worker/Dockerfile`** — `python:3.12-slim` base; copy requirements and
   `pip install --no-cache-dir` as root into system site-packages; create the
   non-root user and the chowned `work_root` VOLUME; copy the `isolinear_worker/`
   package; set the 12-factor env defaults (no token); `EXPOSE 8080`;
   stdlib-only `HEALTHCHECK` gated on `health.status == "ready"`; exec-form
   `ENTRYPOINT ["python", "-m", "isolinear_worker.http_server"]`; `USER worker`.
5. **Static verification here** (all achievable without Docker): entry-point
   maps to the `__main__` guard; env var names match `load_config_from_env`;
   requirements pins; `.dockerignore` correctness; full suite still
   `595 passed, 3 skipped`.
6. **Deferred live verification** on a Docker host: build the image, run it,
   confirm `/v1/health` → `ready`, run the 3 matplotlib-gated tests *inside* the
   container and confirm they pass, and confirm the image filesystem contains no
   `custom_components`/`src`. Record raw outputs into the evidence file and promote
   this spec to `accepted`.

## Proof requirements

### Statically verifiable in the authoring environment (done here)

1. `worker/Dockerfile` and `worker/.dockerignore` exist, are well-formed, and are
   internally consistent (entry point, env vars, port, base image, user).
2. **Entry-point proof:** `python -m isolinear_worker.http_server` is the correct
   invocation — the module carries `if __name__ == "__main__": raise
   SystemExit(main())` and no separate `__main__.py` is required (grep evidence).
3. **Config-contract proof:** every `ISOLINEAR_WORKER_*` name used or documented
   in the Dockerfile matches `load_config_from_env` in `http_server.py` exactly
   (`ISOLINEAR_WORKER_TOKEN`, `ISOLINEAR_WORKER_BIND_HOST`,
   `ISOLINEAR_WORKER_BIND_PORT`, `ISOLINEAR_WORKER_WORK_ROOT`), and no secret
   (`ISOLINEAR_WORKER_TOKEN`) is set in the image.
4. **Requirements proof:** `worker/requirements.txt` pins matplotlib and
   jsonschema (`matplotlib>=3.7,<4`, `jsonschema>=4,<5`); no new runtime dep added.
5. **Suite unbroken:** `python3 -m pytest tests/ -q` stays `595 passed,
   3 skipped` (the 3 matplotlib skips only flip *inside* the container).
6. **Lint deferred:** `hadolint`/`docker build` are unavailable here; Dockerfile
   lint/parse is a deferred check listed with its command.

### Deferred to a Docker host — `DEFERRED (needs Docker host)`

The following require Docker and are the live-verification proof this packet's
acceptance rests on. Run on the deploy target CT103 (`10.0.1.39`, amd64,
GPU-less Docker) or any `linux/amd64` Docker host:

7. **Image builds on amd64:**
   `docker build --platform linux/amd64 -t isolinear-worker:dev worker/`
8. **Fails closed without a token:**
   `docker run --rm isolinear-worker:dev` exits non-zero with the
   `ISOLINEAR_WORKER_TOKEN is required` message and binds no socket.
9. **`/v1/health` → `ready` from a running container** (matplotlib importable
   under `-I`):
   ```
   docker run -d --name iw -e ISOLINEAR_WORKER_TOKEN=<24+char-token> \
     -p 8080:8080 isolinear-worker:dev
   # authenticated GET /v1/health → HTTP 200, health.status == "ready"
   curl -s -H "Authorization: Bearer <token>" \
     -H "X-Isolinear-Worker-API-Version: 1" \
     http://127.0.0.1:8080/v1/health
   docker inspect --format '{{.State.Health.Status}}' iw   # -> healthy
   ```
10. **Authenticated `/v1/render` produces a real PNG through the running
    container:** POST a valid transport envelope with a matplotlib
    `render_request`; assert HTTP `200`, `render_result.status == "success"`, and
    a valid PNG (signature `89504e470d0a1a0a`) at the returned `image_path`
    inside the container / mounted work_root.
11. **The 3 matplotlib-gated tests pass inside the container:**
    ```
    docker run --rm -v "$PWD:/src" -w /src isolinear-worker:dev \
      python -m pytest \
        tests/test_codegen_sandbox.py \
        tests/test_worker_http_server.py -q
    ```
    the three `skipUnless(_SANDBOX_HAS_MATPLOTLIB, ...)` tests
    (`test_matplotlib_pyplot_renders_png_with_agg_backend`,
    `test_matplotlib_arbitrary_read_is_denied_by_audit_hook`,
    `test_authenticated_render_matplotlib_reports_agg_backend`) **run and pass**
    instead of skipping (the interpreter's `-I` can import matplotlib from system
    site-packages).
12. **Image contains nothing from `custom_components`/`src`:**
    ```
    docker run --rm isolinear-worker:dev \
      sh -c 'find / -path /proc -prune -o \
        \( -name custom_components -o -path "*/src/Isolinear*" \) -print' 
    ```
    returns empty.
13. **Lint (optional):** `hadolint worker/Dockerfile` reports no errors.

Completing 7–12 with raw outputs recorded in the evidence file is the trigger to
promote this spec `draft → accepted`.

## Non-goals

- **Multi-arch / aarch64 image builds** — deferred by ADR-0029. The Dockerfile is
  single-arch `linux/amd64` and must not preclude a later buildx multi-arch build.
- **Home Assistant add-on packaging** — a later thin wrapper over this same image
  (ADR-0029), not a fork; not built here.
- **Image publishing / registry push / tagging strategy / CI build** — the homelab
  two-repo split deploys this image and owns publishing; that waits on the
  homelab `docker_host` role. This packet produces a buildable Dockerfile, not a
  published image.
- **TLS termination** — assumed handled by the deployment/reverse proxy per
  ADR-0012's `http(s)://` endpoint; the container serves plain HTTP.
- **The model codegen generation path and a real repair model** — ADR-0029
  packet 4.
- **Artifact byte transfer end-to-end into the integration store** — packet 5.
- Any change to the sandbox **security model** (inherited from
  worker-sandbox-spec.md) or the packet-1/packet-2 public contracts.

## References

- ADR-0029 — revive worker for codegen evaluation (standalone Docker first)
- ADR-0012 — worker transport and authentication
- ADR-0014 — worker health/readiness endpoint
- ADR-0008 — read-only MVP and sandbox security
- [worker-http-server.md](worker-http-server.md) — packet 2 (the server this image runs)
- [codegen-sandbox-module-promotion.md](codegen-sandbox-module-promotion.md) — packet 1 (the `-I` sandbox needing matplotlib)
- [worker-sandbox-spec.md](worker-sandbox-spec.md) — sandbox security model
- Entry point: `worker/isolinear_worker/http_server.py` (`main` / `__main__`)
- Config contract: `load_config_from_env` in `worker/isolinear_worker/http_server.py`
- Deps: `worker/requirements.txt`
