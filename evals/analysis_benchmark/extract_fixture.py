#!/usr/bin/env python3
"""Extract a real Home Assistant history sample into a local benchmark fixture.

Reads HA_URL + HA_TOKEN from the environment; writes home_data.json next to this
file. The fixture is REAL home data (room temps, door timings) and is gitignored
by design — it never leaves the local machine. Re-run this to regenerate it.

Usage:
    HA_URL=http://<ha-host>:8123 HA_TOKEN=<long-lived-token> \
      python3 evals/analysis_benchmark/extract_fixture.py
"""
from __future__ import annotations
import json, os, sys, urllib.request, urllib.parse, datetime as dt, pathlib

HERE = pathlib.Path(__file__).resolve().parent
HA_URL = os.environ.get("HA_URL")
HA_TOKEN = os.environ.get("HA_TOKEN")
WINDOW_DAYS = int(os.environ.get("HA_WINDOW_DAYS", "7"))

# A representative multi-room set: indoor + outdoor temps, humidity, HVAC load,
# the thermostat's hvac_action cycles, and a door. Edit for your own install.
ENTITIES = [
    "sensor.attic_sensor_temperature", "sensor.family_room_sensor_temperature",
    "sensor.kitchen_ecobee_temperature", "sensor.upstairs_bedroom_sensor_temperature",
    "sensor.mbr_sensor_temperature", "sensor.bathroom_sensor_temperature",
    "sensor.hallway_sensor_temperature", "sensor.basement_temperature",
    "sensor.kvuo_temperature",  # outdoor (NWS station)
    "sensor.attic_sensor_humidity", "sensor.family_room_sensor_humidity",
    "sensor.kvuo_relative_humidity",
    "sensor.york_ac_power_estimate", "sensor.hvac_blower_homelab_basement_lights_9_1min",
    "climate.kitchen_ecobee", "binary_sensor.kitchen_door",
]
BAD = {"unknown", "unavailable", "", "none"}


def isnum(v):
    try:
        float(v); return True
    except (TypeError, ValueError):
        return False


def main() -> int:
    if not HA_URL or not HA_TOKEN:
        print("set HA_URL and HA_TOKEN in the environment", file=sys.stderr)
        return 2
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(days=WINDOW_DAYS)
    url = (f"{HA_URL}/api/history/period/{start.strftime('%Y-%m-%dT%H:%M:%S%z')}"
           f"?end_time={urllib.parse.quote(end.strftime('%Y-%m-%dT%H:%M:%S%z'))}"
           f"&filter_entity_id={','.join(ENTITIES)}&minimal_response")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {HA_TOKEN}"})
    raw = json.loads(urllib.request.urlopen(req, timeout=90).read())

    fixture = {}
    for series in raw:
        if not series:
            continue
        head = series[0]
        eid = head["entity_id"]
        a = head.get("attributes", {})
        dom = eid.split(".")[0]
        kind = "categorical" if dom == "climate" else ("binary" if dom == "binary_sensor" else "numeric")
        pts = []
        for rec in series:
            ts = rec.get("last_changed") or rec.get("last_updated")
            if dom == "climate":
                val = rec.get("attributes", {}).get("hvac_action")
                if val is None:
                    continue
            else:
                st = rec.get("state")
                if st is None or str(st).lower() in BAD:
                    continue
                if kind == "numeric":
                    if not isnum(st):
                        continue
                    val = float(st)
                else:
                    val = str(st)
            # epoch MILLISECONDS — decision 9: the model never parses raw ISO strings.
            pts.append([int(dt.datetime.fromisoformat(ts).timestamp() * 1000), val])
        fixture[eid] = {"friendly_name": a.get("friendly_name", eid), "unit": a.get("unit_of_measurement"),
                        "device_class": a.get("device_class"), "kind": kind, "points": pts}

    out = {"description": f"{WINDOW_DAYS}-day HA history sample; real irregular sampling.",
           "window_days": WINDOW_DAYS, "timestamp_format": "unix_epoch_milliseconds_int",
           "entities": fixture}
    (HERE / "home_data.json").write_text(json.dumps(out, indent=0))
    print(f"wrote home_data.json — {len(fixture)} entities, "
          f"{sum(len(m['points']) for m in fixture.values())} total points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
