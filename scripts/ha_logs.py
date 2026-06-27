#!/usr/bin/env python3
"""Pull recent WARNING/ERROR records from the live HA instance over the WebSocket API.

Filesystem on the HA box is closed to this machine and /api/error_log 404s on this
instance, so we use the in-memory system_log capture instead. Isolinear escalates
card-facing failures to WARNING (_record_websocket_decision), so they land here.

Auth: set the HA_TOKEN env var to a long-lived access token. The HA base URL can
be overridden with HA_WS_URL (default ws://10.0.1.200:8123/api/websocket).

Usage:
  HA_TOKEN=<token> python3 scripts/ha_logs.py            # all captured warnings/errors
  HA_TOKEN=<token> python3 scripts/ha_logs.py isolinear  # filter by name/message substring
"""
import asyncio
import json
import os
import sys
import time

import websockets

URL = os.environ.get("HA_WS_URL", "ws://10.0.1.200:8123/api/websocket")
TOKEN = os.environ.get("HA_TOKEN", "")


async def fetch(filter_substr: str | None):
    if not TOKEN:
        print("Set HA_TOKEN to a Home Assistant long-lived access token.", file=sys.stderr)
        return 1
    async with websockets.connect(URL, max_size=None) as ws:
        # auth handshake
        await ws.recv()  # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            print(f"AUTH FAILED: {auth}", file=sys.stderr)
            return 1
        await ws.send(json.dumps({"id": 1, "type": "system_log/list"}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1:
                break
        if not msg.get("success"):
            print(f"REQUEST FAILED: {msg}", file=sys.stderr)
            return 1
        records = msg.get("result", [])
        records.sort(key=lambda r: r.get("timestamp", 0))  # oldest first
        shown = 0
        for r in records:
            blob = json.dumps(r).lower()
            if filter_substr and filter_substr.lower() not in blob:
                continue
            ts = time.strftime("%H:%M:%S", time.localtime(r.get("timestamp", 0)))
            level = r.get("level", "?")
            name = r.get("name", "?")
            message = r.get("message")
            if isinstance(message, list):
                message = " | ".join(message)
            count = r.get("count", 1)
            mult = f" (x{count})" if count and count > 1 else ""
            print(f"[{ts}] {level:7} {name}{mult}\n    {message}")
            shown += 1
        if shown == 0:
            print("(no matching records)")
        return 0


if __name__ == "__main__":
    flt = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(asyncio.run(fetch(flt)))
