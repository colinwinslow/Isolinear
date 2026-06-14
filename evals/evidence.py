import json
from typing import Any


def print_case(case_id: str, *, given: dict[str, Any], when: dict[str, Any], then: dict[str, Any]) -> None:
    observed = {
        "case_id": case_id,
        "given": given,
        "when": when,
        "then": then,
    }
    print(f"CASE {case_id}")
    print(json.dumps(observed, indent=2, sort_keys=True, default=str))
    print(f"PASS {case_id}")
