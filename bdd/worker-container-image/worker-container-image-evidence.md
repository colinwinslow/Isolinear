# Worker container image — evidence

**Status:** filled by the packet-3 implementing slice, then **completed live on
CT103**. STATIC scenarios (G/H/I) carry **raw** outputs from the authoring box;
scenarios A–F carry **raw live outputs from the CT103 Docker host** and are
marked verified/PASS. Paired with
[worker-container-image-bdd.md](worker-container-image-bdd.md) and
[docs/specs/worker-container-image.md](../../docs/specs/worker-container-image.md).

**Static run date:** 2026-07-01 · branch `adr-0029-worker-codegen-eval` · Python 3.12.3.
**Live run date:** 2026-07-01 · CT103 · commit tested `2bb2747` (fresh clone + rebuild).

> **Environment note (updated 2026-07-01):** The Docker build/run proof is **no
> longer deferred** — it ran live on **CT103** (the deploy target). Scenarios
> A–F below carry the raw observed outputs from that host and are marked PASS.
> The authoring environment still has no Docker (`which docker` → not found),
> so the STATIC scenarios (G/H/I) below were verified there; the live scenarios
> were run on CT103.
>
> **CT103 live environment:** host `docker-host` (CT103) · `10.0.1.39` ·
> Debian 13 (trixie) · x86_64 · Docker 29.5.2 · 6 cores · container base
> `python:3.12-slim` · run date 2026-07-01 · commit tested `2bb2747`
> (fresh clone + rebuild).
>
> **The live build surfaced a real bug** (OpenBLAS × `RLIMIT_AS`), fixed in
> `2bb2747`. See the dedicated finding subsection below — it is the most
> important thing this live proof produced.

---

## Scenario G — [STATIC] entry point maps to the packet-2 module `__main__`

`ENTRYPOINT` (exec form) in `worker/Dockerfile`:

```
86:ENTRYPOINT ["python", "-m", "isolinear_worker.http_server"]
```

The target module carries the `__main__` guard and there is **no** separate
`__main__.py` (so `python -m isolinear_worker.http_server` runs the module
directly):

```
$ grep -n 'if __name__' worker/isolinear_worker/http_server.py
482:if __name__ == "__main__":
$ find worker -name "__main__.py" | wc -l
0
```

The invocation resolves and runs the packet-2 entry point (here it correctly
fails closed with no token — proving `-m isolinear_worker.http_server` reaches
`main()` → `load_config_from_env()`):

```
$ cd worker && env -u ISOLINEAR_WORKER_TOKEN python3 -m isolinear_worker.http_server
isolinear worker startup failed: ISOLINEAR_WORKER_TOKEN is required; refusing to start without a bearer token.
exit=1
```

## Scenario H — [STATIC] env vars and no baked secret match the packet-2 config contract

Config names `load_config_from_env` reads (`http_server.py`):

```
50:_ENV_TOKEN = "ISOLINEAR_WORKER_TOKEN"
51:_ENV_BIND_HOST = "ISOLINEAR_WORKER_BIND_HOST"
52:_ENV_BIND_PORT = "ISOLINEAR_WORKER_BIND_PORT"
53:_ENV_WORK_ROOT = "ISOLINEAR_WORKER_WORK_ROOT"
```

`ENV` block set by the image (`worker/Dockerfile`) — exactly the three non-secret
config vars, plus two non-`ISOLINEAR` runtime niceties:

```
ENV ISOLINEAR_WORKER_BIND_HOST=0.0.0.0 \
    ISOLINEAR_WORKER_BIND_PORT=8080 \
    ISOLINEAR_WORKER_WORK_ROOT=/var/lib/isolinear-worker/work \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
```

`ISOLINEAR_WORKER_TOKEN` is **not** set as an `ENV` anywhere (it is a
runtime-supplied secret). The only mentions of it in the Dockerfile are (a)
comments and (b) the healthcheck's `os.environ.get('ISOLINEAR_WORKER_TOKEN','')`
runtime *read* — never an image default:

```
$ grep -n 'ENV .*ISOLINEAR_WORKER_TOKEN\|ISOLINEAR_WORKER_TOKEN=' worker/Dockerfile
# (no match) → NOT SET as ENV
```

`EXPOSE` matches the `ISOLINEAR_WORKER_BIND_PORT` default:

```
$ grep -n 'EXPOSE' worker/Dockerfile
EXPOSE 8080
```

Contract check: `{BIND_HOST, BIND_PORT, WORK_ROOT}` set by the image ⊆ names read
by `load_config_from_env`; `TOKEN` is the one required var and is deliberately
runtime-only. No mismatch.

## Scenario I — [STATIC] unit suite stays green and no runtime dependency is added

```
$ python3 -m pytest tests/ -q
............................................................ ...
595 passed, 3 skipped in 15.10s
```

The 3 skips are the matplotlib-gated tests (`skipUnless(_SANDBOX_HAS_MATPLOTLIB,
...)`) — `test_matplotlib_pyplot_renders_png_with_agg_backend` and
`test_matplotlib_arbitrary_read_is_denied_by_audit_hook`
(`tests/test_codegen_sandbox.py`) and
`test_authenticated_render_matplotlib_reports_agg_backend`
(`tests/test_worker_http_server.py`). They skip here because this box's
`python -I` cannot import matplotlib; they flip to **passing inside the
container** (Scenario E). Packet 3 added no test and broke none.

`worker/requirements.txt` — matplotlib + jsonschema, pinned; no new runtime dep:

```
matplotlib>=3.7,<4
jsonschema>=4,<5
```

## `worker/Dockerfile` (as committed)

```dockerfile
FROM python:3.12-slim

ENV ISOLINEAR_WORKER_BIND_HOST=0.0.0.0 \
    ISOLINEAR_WORKER_BIND_PORT=8080 \
    ISOLINEAR_WORKER_WORK_ROOT=/var/lib/isolinear-worker/work \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt/isolinear-worker
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY isolinear_worker ./isolinear_worker

RUN groupadd --system --gid 10001 worker \
    && useradd --system --uid 10001 --gid 10001 --home-dir /home/worker \
       --create-home worker \
    && mkdir -p "${ISOLINEAR_WORKER_WORK_ROOT}" \
    && chown -R worker:worker "${ISOLINEAR_WORKER_WORK_ROOT}" /opt/isolinear-worker
VOLUME ["/var/lib/isolinear-worker/work"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import json,os,sys,urllib.request; port=os.environ.get('ISOLINEAR_WORKER_BIND_PORT','8080'); tok=os.environ.get('ISOLINEAR_WORKER_TOKEN',''); req=urllib.request.Request('http://127.0.0.1:'+port+'/v1/health', headers={'Authorization':'Bearer '+tok,'X-Isolinear-Worker-API-Version':'1','Accept':'application/json'}); r=urllib.request.urlopen(req, timeout=8); sys.exit(0 if (r.status==200 and json.load(r).get('health',{}).get('status')=='ready') else 1)"]

USER worker
ENTRYPOINT ["python", "-m", "isolinear_worker.http_server"]
```

(Header comment block omitted above for brevity; present in the file.)

## `worker/.dockerignore` (as committed)

```
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.md
Dockerfile
.dockerignore
.git/
.gitignore
.venv/
venv/
.idea/
.vscode/
work/
*.png
*.log
```

The build context is `worker/`, so `custom_components/`, `src/`, and `frontend/`
are outside the context and cannot be copied; this file removes build/test cruft
inside `worker/` from the image and the cache key.

## Lint — deferred (no tooling here)

```
$ which docker hadolint
# neither present
```

Dockerfile lint/parse is deferred: run `hadolint worker/Dockerfile` and/or
`docker build` on a Docker host (Scenario A) to confirm parse + best-practice
lint.

---

## VERIFIED LIVE on CT103 (2026-07-01, commit `2bb2747`)

Scenarios A–F ran on the deploy target **CT103** (`docker-host`, `10.0.1.39`,
Debian 13 trixie, x86_64, Docker 29.5.2, 6 cores) from a fresh clone at commit
`2bb2747` with a rebuilt image. The bearer token used was an ephemeral
`secrets.token_urlsafe(24)` generated on CT103 (never printed); the temp clone
was removed after; the proven `isolinear-worker:dev` image (418MB) is retained
on CT103. Each scenario carries its raw observed output and is marked **PASS**.

> **⚠ FINDING — read first.** The very first live matplotlib render through the
> sandbox **FAILED** before the `2bb2747` fix, with an OpenBLAS/`RLIMIT_AS`
> error. See **"OpenBLAS × RLIMIT_AS finding and the `2bb2747` fix"** below.
> The results here are the post-fix (`2bb2747`) re-proof, which all pass.

### Scenario A — image builds on amd64 — **PASS (CT103)**

```
$ docker build --platform linux/amd64 -t isolinear-worker:dev worker/
# ... build succeeded.
```
matplotlib-3.11.0 installed from **prebuilt wheels** (no source build) alongside
numpy-2.5.0, pillow-12.3.0, contourpy, fonttools, kiwisolver, jsonschema-4.26.0,
etc. Final image **418MB**. One benign warning:
`useradd warning: worker's uid 10001 is greater than SYS_UID_MAX 999` (harmless;
`--system` user with a high uid). No compiler / source build in the layers.

### Scenario B — fails closed without a token — **PASS (CT103)**

```
$ docker run --rm isolinear-worker:dev
isolinear worker startup failed: ISOLINEAR_WORKER_TOKEN is required; refusing to start without a bearer token.
exit=1

$ docker run --rm -e ISOLINEAR_WORKER_TOKEN=short isolinear-worker:dev
isolinear worker startup failed: ISOLINEAR_WORKER_TOKEN must be at least 24 characters; refusing to start with a weak token.
exit=1
```
Both the missing-token and weak-token paths fail closed with `exit=1` and bind
no socket.

### Scenario C — `/v1/health` → `ready` from a running container — **PASS (CT103)**

Authenticated `GET /v1/health` → HTTP 200, body:
```
{"health": {"accepted": true, "status": "ready", "code": "worker_ready", "message": "Worker is ready to render.", "checks": [{"name": "sandbox_policy", "status": "ok"}, {"name": "matplotlib_import", "status": "ok"}], "capabilities": {"rendering": true}}}
```
`status == "ready"`, `capabilities.rendering == true`, and the
`matplotlib_import` check is `ok` (matplotlib importable under `python -I` from
system site-packages). Unauthenticated `GET /v1/health` → `http_status=401`.

### Scenario D — authenticated `/v1/render` produces a real PNG — **PASS (CT103)**

Authenticated `POST /v1/render` with a `render_mode: codegen` envelope carrying
real matplotlib code →
```
status=      success
image_path=  /var/lib/isolinear-worker/work/codegen-sandbox-anchor.png
warnings=    ['matplotlib_backend:Agg']
```
PNG verified on disk inside the container:
`bytes= 16557  sig= 89504e470d0a1a0a  valid_png= True`.

### Scenario E — the 3 matplotlib-gated tests un-skip and pass, in-container — **PASS (CT103)**

Running inside the container (repo mounted, pytest installed ad-hoc):
```
$ python -m pytest tests/test_codegen_sandbox.py tests/test_worker_http_server.py
24 passed in 6.49s
```
**ZERO skips.** The three formerly-skipped tests —
`test_matplotlib_pyplot_renders_png_with_agg_backend`,
`test_matplotlib_arbitrary_read_is_denied_by_audit_hook`, and
`test_authenticated_render_matplotlib_reports_agg_backend` — now **PASS**
(in-container `python -I` imports matplotlib 3.11.0 from system site-packages).

> **Before the `2bb2747` fix these 3 un-skipped but FAILED** with the OpenBLAS
> error recorded below — that is the finding this live build surfaced.

### Scenario F — image contains nothing from `custom_components`/`src` — **PASS (CT103)**

```
$ find / -path /proc -prune -o \( -name custom_components -o -path "*/src/Isolinear*" \) -print
# (empty output)
```
No integration code in the image — HA-agnostic by construction (build context
`worker/`).

### Container HEALTHCHECK — **PASS (CT103)**

After the healthcheck interval:
```
$ docker inspect --format '{{.State.Health.Status}}' iw
healthy
```

---

## OpenBLAS × RLIMIT_AS finding and the `2bb2747` fix

This is the most important thing the live build surfaced — a real bug that only
became observable once matplotlib actually **rendered** inside the container.

**Initial failure.** The packet-3 image built and `/v1/health` reported
`ready` (matplotlib *imports* fine under `-I`), but the FIRST live matplotlib
render through the sandbox **FAILED** with:

```
OpenBLAS error: Memory allocation still failed after 10 retries, giving up.
```

**Root cause.** numpy's BLAS backend (OpenBLAS) reserves **per-core address
space** for its thread pool **at import time**, scaled to the host CPU count.
CT103 has **6 cores**, so that reservation exceeded the sandbox's **256 MB
`RLIMIT_AS`** cap and aborted **before any chart was drawn**. The safe
(non-numpy) render path was unaffected — which is exactly why this only surfaced
once matplotlib ran in-container (the matplotlib tests skip on the dev box,
where `python -I` cannot import matplotlib at all).

**Fix (`2bb2747`).** Pin the numeric threading libraries to a single thread in
the sandbox's stripped subprocess environment
(`worker/isolinear_worker/codegen_sandbox.py`, `_sandbox_environment`) and add
them to the policy's `explicit_environment_keys`:
`OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`,
`NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS` = `1`. Pinning the thread count
keeps the OpenBLAS address-space reservation within the `RLIMIT_AS` cap.

**Safety.** These variables only ever **reduce** resource use, so the sandbox is
**not weakened** — the `-I` isolation, import allowlist, audit hook, fixed
output path, timeout, and `resource` limits are all unchanged (invariant #3
intact).

**Re-proof.** After rebuilding the image at `2bb2747`, all of Scenarios A–F pass
(above), including the 3 matplotlib-gated tests un-skipping to `24 passed`.
