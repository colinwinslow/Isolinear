#!/usr/bin/env python3
"""Reproduce e2e-14 at the ENTITY RESOLUTION step (not the planner).

STATUS/HANDOFF (18th session) concluded the live failure is a resolution gap:
"resolution discloses only the temp sensor" for "Is the kitchen temperature
correlated with the kitchen humidity over the last 2 days?" — disclosing both
sensors plans the correlation fine (repro_e2e14.py). This script drives the
REAL select_prompt_entity_ids (D1) + _resolve_entity_selection_with_model (D2)
against the live gemma4:e4b endpoint with the real kitchen temp+humidity
catalog rows, to see exactly which stage drops the humidity sensor.
"""
import sys

sys.path.insert(0, "custom_components")
from isolinear.entity_resolution import (  # noqa: E402
    select_prompt_entity_ids,
    _resolve_entity_selection_with_model,
)
from isolinear.model_provider import (  # noqa: E402
    OllamaCompatiblePlannerClient as OllamaPlanner,
    DATA_MODEL_PROVIDER_PLANNER,
)
from isolinear.const import DOMAIN  # noqa: E402

ENDPOINT = "http://10.0.1.39:11434"
ENTRY_ID = "repro"

CATALOG = [
    {
        "entity_id": "sensor.kitchen_ecobee_temperature",
        "friendly_name": "Kitchen Temperature",
        "area": "Kitchen",
        "device_name": "Kitchen ecobee",
        "device_class": "temperature",
        "unit_of_measurement": "°F",
    },
    {
        "entity_id": "sensor.kitchen_ecobee_humidity",
        "friendly_name": "Kitchen ecobee Humidity",
        "area": "Kitchen",
        "device_name": "Kitchen ecobee",
        "device_class": "humidity",
        "unit_of_measurement": "%",
    },
]

PROMPT = "Is the kitchen temperature correlated with the kitchen humidity over the last 2 days?"


class FakeHass:
    def __init__(self, planner):
        self.data = {DOMAIN: {ENTRY_ID: {DATA_MODEL_PROVIDER_PLANNER: planner}}}


def main() -> None:
    planner = OllamaPlanner(endpoint_url=ENDPOINT, planner_model="gemma4:e4b")
    hass = FakeHass(planner)

    d1 = select_prompt_entity_ids(PROMPT, CATALOG)
    print("D1 result:")
    print(f"  accepted={d1['accepted']} code={d1['code']} source={d1.get('source')}")
    print(f"  entity_ids={d1.get('entity_ids')}")
    if not d1["accepted"]:
        print(f"  candidate_items={[c['entity_id'] for c in d1.get('candidate_items', [])]}")

    final = _resolve_entity_selection_with_model(
        hass, ENTRY_ID, PROMPT, CATALOG, d1,
    )
    print("\nFinal (post-D2) result:")
    print(f"  accepted={final['accepted']} code={final['code']} source={final.get('source')}")
    print(f"  entity_ids={final.get('entity_ids')}")


if __name__ == "__main__":
    main()
