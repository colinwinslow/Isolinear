# Isolinear worker — standalone amd64 container image (ADR-0029 packet 3).
#
# Packages the packet-2 HTTP server (isolinear_worker.http_server) and the
# packet-1 codegen sandbox into a single-arch linux/amd64 image whose SYSTEM
# site-packages carry matplotlib. The sandbox runs generated code under
# `python -I` (isolated mode → excludes user site-packages), so matplotlib MUST
# live in the interpreter's system site-packages for `python -I -c "import
# matplotlib"` — the readiness probe in http_server.py — to succeed and for
# GET /v1/health to report `ready`. That is the whole point of this packet.
#
# HA-agnostic by construction: the build context is `worker/`, so nothing from
# custom_components/, src/, or frontend/ is even reachable. Build with:
#   docker build --platform linux/amd64 -t isolinear-worker:dev worker/
#
# Multi-arch/aarch64 builds, the HA add-on wrapper, image publishing, and TLS
# are out of scope (ADR-0029). See docs/specs/worker-container-image.md.

# Pinned to the 3.12-slim (Debian bookworm) tag to match the repo's runtime
# (dev box + CI + sandbox authored against Python 3.12). A digest pin is a
# hardening option a live build can add.
FROM python:3.12-slim

# --- Runtime configuration (12-factor; no secrets baked in) -----------------
# These names match load_config_from_env() in isolinear_worker/http_server.py
# exactly. ISOLINEAR_WORKER_TOKEN is deliberately NOT set here: it is a secret
# supplied at `docker run` time. With no valid token the packet-2 entry point
# fails closed (non-zero exit, no socket bound).
ENV ISOLINEAR_WORKER_BIND_HOST=0.0.0.0 \
    ISOLINEAR_WORKER_BIND_PORT=8080 \
    ISOLINEAR_WORKER_WORK_ROOT=/var/lib/isolinear-worker/work \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# --- Dependencies (installed into SYSTEM site-packages, as root) ------------
# requirements.txt is copied and installed in its own layer BEFORE the app code
# so the (slow) matplotlib wheel install is cached across code-only rebuilds.
# No `--user`, no virtualenv: matplotlib + jsonschema land in
# /usr/local/lib/python3.12/site-packages, so a bare `python -I` can import them.
# The matplotlib manylinux wheel is self-contained for a headless Agg render on
# bookworm-slim, so no extra apt packages are installed. (If a live build ever
# surfaces a missing shared library, add a single explicit
# `apt-get install --no-install-recommends <lib>` layer here — not a toolchain.)
WORKDIR /opt/isolinear-worker
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- Application code --------------------------------------------------------
# Only the self-contained worker package (proven to import nothing from
# custom_components/ or src/ by the packet-1/2 import-graph checks).
COPY isolinear_worker ./isolinear_worker

# --- Non-root runtime user + writable work_root -----------------------------
# Defense-in-depth: run the server unprivileged. The work_root (where rendered
# PNGs are written) is created and chowned to the runtime user, and declared a
# VOLUME so a host/orchestrator can mount durable or tmpfs artifact storage.
RUN groupadd --system --gid 10001 worker \
    && useradd --system --uid 10001 --gid 10001 --home-dir /home/worker \
       --create-home worker \
    && mkdir -p "${ISOLINEAR_WORKER_WORK_ROOT}" \
    && chown -R worker:worker "${ISOLINEAR_WORKER_WORK_ROOT}" /opt/isolinear-worker
VOLUME ["/var/lib/isolinear-worker/work"]

# The bind port (matches the ISOLINEAR_WORKER_BIND_PORT default). Documentation
# only; actual publishing is `-p` at run time.
EXPOSE 8080

# --- Healthcheck ------------------------------------------------------------
# GET /v1/health requires the bearer token (auth is checked first — packet 2),
# so the probe reads ISOLINEAR_WORKER_TOKEN and ISOLINEAR_WORKER_BIND_PORT from
# the container's own env (the same place the server reads them; never baked
# into a layer or logged) and makes an authenticated request using only the
# standard library (no curl/wget added). Exits 0 only when the transport
# returns HTTP 200 AND health.status == "ready" — i.e. matplotlib is importable
# under `-I`. Until then the container is reported unhealthy, which is the exact
# observable signal that the system-site matplotlib install worked.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import json,os,sys,urllib.request; port=os.environ.get('ISOLINEAR_WORKER_BIND_PORT','8080'); tok=os.environ.get('ISOLINEAR_WORKER_TOKEN',''); req=urllib.request.Request('http://127.0.0.1:'+port+'/v1/health', headers={'Authorization':'Bearer '+tok,'X-Isolinear-Worker-API-Version':'1','Accept':'application/json'}); r=urllib.request.urlopen(req, timeout=8); sys.exit(0 if (r.status==200 and json.load(r).get('health',{}).get('status')=='ready') else 1)"]

# --- Entry point ------------------------------------------------------------
# Maps directly to the packet-2 module entry point:
# isolinear_worker/http_server.py has `if __name__ == "__main__": raise
# SystemExit(main())`, so `python -m isolinear_worker.http_server` runs
# main() → load_config_from_env() → serve(). WORKDIR already contains the
# isolinear_worker/ package, so the module resolves.
USER worker
ENTRYPOINT ["python", "-m", "isolinear_worker.http_server"]
