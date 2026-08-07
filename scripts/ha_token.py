#!/usr/bin/env python3
"""Resolve the HA long-lived token from the homelab SOPS vault and run a command with it.

The token is NOT stored in this repo, in shell history, or in any note. It lives in
``~/repos/homelab/secrets/ha-access.enc.yaml`` (age-encrypted, decryptable by whoever
holds the age key). This helper decrypts it in-process and injects it as ``HA_TOKEN``
into a child command, so the plaintext never lands in a shell variable, a log, or a
scrollback buffer.

Rotating the token breaks every consumer at once with a bare 401 and no hint where the
real value lives (observed 2026-07-31: the e2e harness died mid-run on `auth_invalid`).
Hence this helper plus the expiry check below — a future 401 should be self-diagnosing.

Usage:
  python3 scripts/ha_token.py --check                     # verify the token + print expiry
  python3 scripts/ha_token.py -- python3 evals/e2e_pipeline_harness.py
  python3 scripts/ha_token.py -- python3 scripts/ha_logs.py isolinear
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

VAULT = os.path.expanduser("~/repos/homelab/secrets/ha-access.enc.yaml")
AGE_KEY = os.path.expanduser("~/.config/sops/age/keys.txt")


def load() -> dict:
    """Decrypt the vault entry. Returns the ha_access mapping."""
    if not os.path.exists(VAULT):
        raise SystemExit(f"vault not found: {VAULT}")
    env = dict(os.environ)
    # macOS sops needs this pointed explicitly; harmless elsewhere.
    env.setdefault("SOPS_AGE_KEY_FILE", AGE_KEY)
    try:
        out = subprocess.run(
            ["sops", "-d", VAULT], capture_output=True, text=True, check=True, env=env
        ).stdout
    except FileNotFoundError:
        raise SystemExit("sops not installed") from None
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"sops decrypt failed (age key at {AGE_KEY}?): {exc.stderr.strip()}") from None
    try:
        import yaml
    except ImportError:
        raise SystemExit("pyyaml required") from None
    data = yaml.safe_load(out) or {}
    access = data.get("ha_access")
    if not isinstance(access, dict) or not access.get("token"):
        raise SystemExit("vault has no ha_access.token")
    return access


def check(access: dict) -> int:
    """Verify the token against the live instance, with a negative control.

    A bare 200 proves nothing on its own — an instance with auth misconfigured would
    also return 200 for garbage. The bogus-token arm is what makes the pass meaningful.
    """
    url = access["url"].rstrip("/")
    expires = str(access.get("expires_unencrypted", "unknown"))
    print(f"vault:   {VAULT}")
    print(f"url:     {url}")
    print(f"expires: {expires}", end="")
    try:
        exp = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        days = (exp - datetime.now(timezone.utc)).days
        print(f"   ({days} days left)" + ("   <<< RENEW" if days < 30 else ""))
    except ValueError:
        print()

    def probe(token: str) -> int | str:
        req = urllib.request.Request(f"{url}/api/", headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code
        except OSError as exc:
            return f"unreachable: {exc}"

    real = probe(access["token"])
    bogus = probe("not-a-real-token")
    print(f"  real token  /api/ -> {real}")
    print(f"  bogus token /api/ -> {bogus}   (negative control)")
    if real == 200 and bogus == 401:
        req = urllib.request.Request(
            f"{url}/api/config", headers={"Authorization": f"Bearer {access['token']}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"  HA version: {json.load(resp).get('version')}")
        print("VERDICT: token valid (negative control behaved)")
        return 0
    if real == 200 and bogus == 200:
        print("VERDICT: INCONCLUSIVE — bogus token also accepted; auth is not being enforced")
        return 2
    print("VERDICT: token REJECTED — rotate it and re-encrypt the vault")
    return 1


def main(argv: list[str]) -> int:
    access = load()
    if "--check" in argv or not argv:
        return check(access)
    if argv[0] == "--":
        argv = argv[1:]
    if not argv:
        raise SystemExit("nothing to run after --")
    env = dict(os.environ)
    env["HA_TOKEN"] = access["token"]
    env.setdefault("HA_URL", access["url"])
    return subprocess.call(argv, env=env)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
