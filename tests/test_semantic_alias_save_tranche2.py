"""Tests for semantic-alias propose/confirm/save (ADR-0009/0010, Tranche 2).

Covers the pure derivation helpers, the synchronous ``save_alias`` write method
(append / replace / validate / immediate in-memory availability), and the
end-to-end clarification -> "Use and remember" -> save -> next-request-injection
round trip through the job orchestration handler.
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from custom_components.isolinear.semantic_memory import (  # noqa: E402
    SemanticMemoryStorageHelper,
    _entity_id_to_alias_id,
    _sanitize_prompt_for_storage,
    derive_alias_natural_names,
    save_semantic_alias,
    semantic_memory_store_for,
    validate_semantic_alias_contract,
)

from tests.test_first_real_vertical_slice import (  # noqa: E402
    FakePlanner,
    _answer_clarification,
    _snapshot_job,
    _start_job,
    configured_real_slice_hass,
)

_AC_METADATA = {
    "sensor.kitchen_temperature": {
        "friendly_name": "Kitchen Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "degF",
        "area": "Kitchen",
    },
    "climate.kitchen_ecobee": {
        "friendly_name": "Kitchen Ecobee",
        "state_class": "measurement",
        "unit_of_measurement": "degF",
        "area": "Kitchen",
    },
}


def _valid_alias(**overrides):
    alias = {
        "alias_id": "climate_kitchen_ecobee",
        "natural_names": ["air conditioning"],
        "meaning": {"type": "entity", "entity_id": "climate.kitchen_ecobee"},
        "source": "user_confirmed",
        "created_from_prompt": "show me the air conditioning",
        "created_at": "2026-06-23T12:00:00+00:00",
        "enabled": True,
    }
    alias.update(overrides)
    return alias


class AliasDerivationTests(unittest.TestCase):
    def test_entity_id_to_alias_id_slugifies(self):
        self.assertEqual(_entity_id_to_alias_id("climate.kitchen_ecobee"), "climate_kitchen_ecobee")
        self.assertEqual(
            _entity_id_to_alias_id("sensor.family_room_sensor_temperature"),
            "sensor_family_room_sensor_temperature",
        )

    def test_derive_natural_names_keeps_distinctive_prompt_tokens(self):
        names = derive_alias_natural_names(
            "show kitchen temp and when the AC was running",
            "climate.kitchen_ecobee",
            "Kitchen Ecobee",
        )
        # "kitchen"/"ecobee" are entity tokens (>=4 chars) and are removed; the
        # action words are stripped; the short, meaning-bearing "ac" survives.
        self.assertEqual(names, ["ac running temp"])

    def test_derive_natural_names_strips_action_words(self):
        names = derive_alias_natural_names(
            "show me the air conditioning", "climate.kitchen_ecobee", "Kitchen Ecobee"
        )
        self.assertEqual(names, ["air conditioning"])

    def test_derive_natural_names_falls_back_to_label(self):
        # Prompt contributes nothing distinctive beyond the entity's own tokens.
        names = derive_alias_natural_names(
            "show kitchen ecobee", "climate.kitchen_ecobee", "Kitchen Ecobee"
        )
        self.assertEqual(names, ["Kitchen Ecobee"])

    def test_sanitize_prompt_truncates_and_strips(self):
        self.assertEqual(_sanitize_prompt_for_storage("  hello  "), "hello")
        self.assertEqual(len(_sanitize_prompt_for_storage("x" * 500)), 200)
        self.assertIsNone(_sanitize_prompt_for_storage("   "))
        self.assertIsNone(_sanitize_prompt_for_storage(None))

    def test_sanitize_prompt_drops_secret_like_material(self):
        self.assertIsNone(_sanitize_prompt_for_storage("token sk-ABCDEFGH1234567890"))
        self.assertIsNone(_sanitize_prompt_for_storage("Authorization: Bearer abc.def"))


class SaveAliasTests(unittest.TestCase):
    def test_save_new_alias_appends_and_is_immediately_available(self):
        helper = SemanticMemoryStorageHelper()
        result = helper.save_alias("entry-1", _valid_alias())
        self.assertTrue(result["accepted"], result)
        store = helper.store_for("entry-1")
        self.assertEqual(store["store_version"], 1)
        self.assertEqual(store["config_entry_id"], "entry-1")
        self.assertEqual(len(store["aliases"]), 1)
        self.assertEqual(store["aliases"][0]["alias_id"], "climate_kitchen_ecobee")

    def test_save_replaces_existing_alias_by_id(self):
        helper = SemanticMemoryStorageHelper()
        helper.save_alias("entry-1", _valid_alias(natural_names=["old name"]))
        helper.save_alias("entry-1", _valid_alias(natural_names=["new name"]))
        store = helper.store_for("entry-1")
        aliases = [a for a in store["aliases"] if a["alias_id"] == "climate_kitchen_ecobee"]
        self.assertEqual(len(aliases), 1)
        self.assertEqual(aliases[0]["natural_names"], ["new name"])

    def test_save_appends_distinct_alias_ids(self):
        helper = SemanticMemoryStorageHelper()
        helper.save_alias("entry-1", _valid_alias())
        helper.save_alias(
            "entry-1",
            _valid_alias(
                alias_id="sensor_kitchen_temperature",
                meaning={"type": "entity", "entity_id": "sensor.kitchen_temperature"},
            ),
        )
        self.assertEqual(len(helper.store_for("entry-1")["aliases"]), 2)

    def test_save_rejects_invalid_alias_via_store_envelope(self):
        helper = SemanticMemoryStorageHelper()
        # A malformed alias_id fails the store-envelope schema (pattern).
        result = helper.save_alias("entry-1", _valid_alias(alias_id="Bad Spaces!"))
        self.assertFalse(result["accepted"])
        self.assertIsNone(helper.store_for("entry-1"))

    def test_schedule_save_called_with_ha_store(self):
        calls: list[tuple] = []

        class _FakeHaStore:
            def async_delay_save(self, data_func, delay):
                calls.append((data_func(), delay))

        helper = SemanticMemoryStorageHelper(ha_store=_FakeHaStore())
        helper.save_alias("entry-1", _valid_alias())
        self.assertEqual(len(calls), 1)
        self.assertIn("entry-1", calls[0][0]["stores"])

    def test_module_save_validates_alias_before_storage(self):
        class _Hass:
            def __init__(self):
                self.data = {}

        hass = _Hass()
        bad = _valid_alias(alias_id="Bad Spaces!")  # fails alias_id pattern
        result = save_semantic_alias(hass, "entry-1", bad)
        self.assertFalse(result["accepted"])

    def test_validate_semantic_alias_contract(self):
        self.assertTrue(validate_semantic_alias_contract(_valid_alias())["accepted"])
        self.assertFalse(validate_semantic_alias_contract({"alias_id": "x"})["accepted"])


class SaveTranche2IntegrationTests(unittest.TestCase):
    """End-to-end: zero-match clarification -> remember -> save -> reuse."""

    def _ac_hass(self, temp_dir):
        return configured_real_slice_hass(
            planner=FakePlanner(),
            artifact_dir=Path(temp_dir),
            extra_metadata_by_entity=_AC_METADATA,
        )

    def test_remember_true_saves_alias(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = self._ac_hass(temp_dir)
            start = _start_job(hass, entry, prompt="show me the air conditioning")
            self.assertEqual(start["snapshot"]["status"], "planning", start["snapshot"])

            poll = _snapshot_job(hass, entry, start["snapshot"]["job_id"])
            self.assertEqual(poll["snapshot"]["status"], "clarification_needed", poll["snapshot"])
            option_ids = {o["option_id"] for o in poll["snapshot"]["clarification"]["options"]}
            self.assertIn("climate_kitchen_ecobee", option_ids)
            # Every entity option is rememberable now.
            self.assertTrue(all(o["can_remember"] for o in poll["snapshot"]["clarification"]["options"]))

            answer = _answer_clarification(
                hass, entry, poll["snapshot"], "climate_kitchen_ecobee", remember=True
            )
            self.assertTrue(answer["accepted"], answer)

            store = semantic_memory_store_for(hass, entry.entry_id)
            self.assertIsNotNone(store)
            saved = [a for a in store["aliases"] if a["alias_id"] == "climate_kitchen_ecobee"]
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["meaning"], {"type": "entity", "entity_id": "climate.kitchen_ecobee"})
            self.assertEqual(saved[0]["source"], "user_confirmed")
            self.assertEqual(saved[0]["natural_names"], ["air conditioning"])

    def test_remember_false_saves_nothing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = self._ac_hass(temp_dir)
            start = _start_job(hass, entry, prompt="show me the air conditioning")
            poll = _snapshot_job(hass, entry, start["snapshot"]["job_id"])
            self.assertEqual(poll["snapshot"]["status"], "clarification_needed", poll["snapshot"])
            _answer_clarification(
                hass, entry, poll["snapshot"], "climate_kitchen_ecobee", remember=False
            )
            store = semantic_memory_store_for(hass, entry.entry_id)
            self.assertIsNone(store)

    def test_saved_alias_skips_clarification_on_next_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = self._ac_hass(temp_dir)
            start = _start_job(hass, entry, prompt="show me the air conditioning")
            poll = _snapshot_job(hass, entry, start["snapshot"]["job_id"])
            self.assertEqual(poll["snapshot"]["status"], "clarification_needed", poll["snapshot"])
            _answer_clarification(
                hass, entry, poll["snapshot"], "climate_kitchen_ecobee", remember=True
            )

            # New job, same concept worded differently: Tranche 1 injection fires.
            second = _start_job(hass, entry, prompt="when was the air conditioning on")
            self.assertTrue(second["accepted"], second)
            self.assertNotEqual(second["snapshot"]["status"], "clarification_needed", second["snapshot"])

            snapshot = _snapshot_job(hass, entry, second["snapshot"]["job_id"], message_id=11)
            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot["snapshot"])
            # Complete snapshot surfaces the matched alias.
            aliases = snapshot["snapshot"].get("aliases")
            self.assertEqual(aliases, [{"name": "air conditioning", "meaning": "climate.kitchen_ecobee (entity)"}])

    def test_save_failure_is_non_blocking(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = self._ac_hass(temp_dir)
            start = _start_job(hass, entry, prompt="show me the air conditioning")
            poll = _snapshot_job(hass, entry, start["snapshot"]["job_id"])
            self.assertEqual(poll["snapshot"]["status"], "clarification_needed", poll["snapshot"])

            # Force the save to fail by making the helper's save_alias raise.
            from custom_components.isolinear import semantic_memory

            helper = semantic_memory.get_semantic_memory_storage(hass)
            original = helper.save_alias
            helper.save_alias = lambda *a, **k: {"accepted": False, "error": "simulated"}
            try:
                answer = _answer_clarification(
                    hass, entry, poll["snapshot"], "climate_kitchen_ecobee", remember=True
                )
            finally:
                helper.save_alias = original

            # The job proceeds normally despite the save failure.
            self.assertTrue(answer["accepted"], answer)
            self.assertNotEqual(answer["snapshot"]["status"], "failed", answer["snapshot"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
