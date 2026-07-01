# Worker container image — evidence

**Status:** filled by the packet-3 implementing slice. STATIC scenarios carry
**raw** outputs; DEFERRED scenarios are marked `DEFERRED (needs Docker host)`
with the exact command to complete them. Paired with
[worker-container-image-bdd.md](worker-container-image-bdd.md) and
[docs/specs/worker-container-image.md](../../docs/specs/worker-container-image.md).

**Run date:** 2026-07-01 · branch `adr-0029-worker-codegen-eval` · Python 3.12.3.

> **Environment note:** Docker is **not installed** in this authoring
> environment (`which docker` → not found; no daemon). The image therefore
> cannot be built or run here. This is expected for packet 3: the static
> contract (Dockerfile / `.dockerignore` / requirements well-formedness,
> entry-point mapping, config-var contract, unbroken suite) is verified below;
> the live build/run proofs are **deferred to a `linux/amd64` Docker host** (the
> deploy target CT103 `10.0.1.39`, or any Docker host), following the repo's
> "live HACS retest" deferral pattern. No build log is fabricated.

```
$ which docker hadolint
# (neither present)
```

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

## DEFERRED — needs Docker host

Run on the deploy target CT103 (`10.0.1.39`, amd64, GPU-less Docker) or any
`linux/amd64` Docker host. Record raw outputs here and promote the spec
`draft → accepted` once Scenarios A–F pass.

### Scenario A — image builds on amd64 — `DEFERRED (needs Docker host)`

```
docker build --platform linux/amd64 -t isolinear-worker:dev worker/
```
Expect: build succeeds; matplotlib installs from a prebuilt wheel (no compiler /
source build in the layers).

### Scenario B — fails closed without a token — `DEFERRED (needs Docker host)`

```
docker run --rm isolinear-worker:dev; echo "exit=$?"
```
Expect: stderr `isolinear worker startup failed: ISOLINEAR_WORKER_TOKEN is
required; refusing to start without a bearer token.` and `exit=1`.

### Scenario C — `/v1/health` → `ready` from a running container — `DEFERRED (needs Docker host)`

```
TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
docker run -d --name iw -e ISOLINEAR_WORKER_TOKEN="$TOKEN" -p 8080:8080 isolinear-worker:dev
curl -s -H "Authorization: Bearer $TOKEN" -H "X-Isolinear-Worker-API-Version: 1" \
     http://127.0.0.1:8080/v1/health
docker inspect --format '{{.State.Health.Status}}' iw
```
Expect: HTTP 200, `health.status == "ready"`, `capabilities.rendering == true`,
`matplotlib_import` check `ok`; `docker inspect` → `healthy`.

### Scenario D — authenticated `/v1/render` produces a real PNG — `DEFERRED (needs Docker host)`

POST a valid transport envelope (`{version:1, operation:"render_chart",
request_id, render_request}`) whose `render_request` is `render_mode:"codegen"`
with matplotlib code, e.g.:
```
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
     -H "X-Isolinear-Worker-API-Version: 1" -H "Content-Type: application/json" \
     --data @envelope.json http://127.0.0.1:8080/v1/render
```
Expect: HTTP 200, `render_result.status == "success"`, a valid PNG (first 8
bytes `89504e470d0a1a0a`) at the returned `image_path` in the container work_root.

### Scenario E — the 3 matplotlib-gated tests pass inside the container — `DEFERRED (needs Docker host)`

```
docker run --rm -v "$PWD:/src" -w /src isolinear-worker:dev \
  python -m pytest tests/test_codegen_sandbox.py tests/test_worker_http_server.py -q
```
Expect: `test_matplotlib_pyplot_renders_png_with_agg_backend`,
`test_matplotlib_arbitrary_read_is_denied_by_audit_hook`, and
`test_authenticated_render_matplotlib_reports_agg_backend` **run and pass** (no
longer skipped) because the container's `python -I` imports matplotlib from
system site-packages.

### Scenario F — image contains nothing from `custom_components`/`src` — `DEFERRED (needs Docker host)`

```
docker run --rm --entrypoint sh isolinear-worker:dev -c \
  'find / -path /proc -prune -o \( -name custom_components -o -path "*/src/Isolinear*" \) -print'
```
Expect: empty output.
