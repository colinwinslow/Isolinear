"""ADR-0026: model entity selection runs in the pollable planning phase.

job/start (and job/retry) return ``planning`` immediately and make no model
call; the first job/snapshot poll resolves D1 → semantic alias → D2 selection
under the planning lock, then either returns a clarification/failure terminal
snapshot or proceeds to planning/render. These tests pin the relocated phase
boundary; the resolution semantics themselves are unchanged (ADR-0024).
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import custom_components.isolinear.job_orchestration as job_orchestration  # noqa: E402
from custom_components.isolinear.const import (  # noqa: E402
    COMMAND_RETRY_JOB,
    INTEGRATION_WS_VERSION,
)
from custom_components.isolinear.entity_catalog import DATA_ENTITY_CATALOG  # noqa: E402
from custom_components.isolinear.job_orchestration import (  # noqa: E402
    ENTITY_SELECTION_PENDING_STAGE,
)
from custom_components.isolinear.websocket_api import handle_registered_ws_command  # noqa: E402

from test_first_real_vertical_slice import (  # noqa: E402
    DOMAIN,
    _D2FakePlanner,
    _THERMOSTAT_METADATA,
    _orchestration_store,
    _snapshot_job,
    _start_job,
    configured_real_slice_hass,
)

THERMOSTAT_PROMPT = "show thermostat history"


class JobStartDefersSelectionTests(unittest.TestCase):
    def test_job_start_returns_planning_without_model_call(self):
        """Anchor: job/start returns planning, makes zero model calls (ADR-0026 D1)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = _D2FakePlanner(selects=None)  # abstains if ever called
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=Path(temp_dir),
                extra_metadata_by_entity=_THERMOSTAT_METADATA,
            )

            start = _start_job(hass, entry, prompt=THERMOSTAT_PROMPT)

            self.assertTrue(start["accepted"], start)
            self.assertEqual(start["snapshot"]["status"], "planning", start["snapshot"])
            self.assertEqual(
                start["snapshot"]["progress"]["stage"],
                ENTITY_SELECTION_PENDING_STAGE,
                start["snapshot"]["progress"],
            )
            # No entities resolved yet and, crucially, the model was not called.
            self.assertNotIn("entities", start["snapshot"])
            self.assertNotIn("clarification", start["snapshot"])
            self.assertEqual(planner.select_calls, 0)
            self.assertEqual(planner.plan_calls, 0)
            self.assertFalse(start["orchestration"]["model_provider_called"])

    def test_clarification_is_a_first_poll_outcome(self):
        """job/start returns planning; first poll surfaces the abstain clarification (D3)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = _D2FakePlanner(selects=None)
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=Path(temp_dir),
                extra_metadata_by_entity=_THERMOSTAT_METADATA,
            )

            start = _start_job(hass, entry, prompt=THERMOSTAT_PROMPT)
            self.assertEqual(start["snapshot"]["status"], "planning")

            poll = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(poll["accepted"], poll)
            self.assertEqual(poll["snapshot"]["status"], "clarification_needed", poll["snapshot"])
            option_ids = {o["option_id"] for o in poll["snapshot"]["clarification"]["options"]}
            self.assertIn("climate_upstairs_thermostat", option_ids)
            self.assertIn("climate_downstairs_thermostat", option_ids)
            # D2 ran exactly once on the poll; the chart planner never ran.
            self.assertEqual(planner.select_calls, 1)
            self.assertEqual(planner.plan_calls, 0)

    def test_deferred_success_renders_on_first_poll(self):
        """D2 picks on the poll → planning/render proceed under the same lock."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = _D2FakePlanner(selects="climate.upstairs_thermostat")
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=Path(temp_dir),
                extra_metadata_by_entity=_THERMOSTAT_METADATA,
            )

            start = _start_job(hass, entry, prompt=THERMOSTAT_PROMPT)
            self.assertEqual(start["snapshot"]["status"], "planning")
            self.assertEqual(planner.select_calls, 0)  # nothing resolved at start

            poll = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(poll["accepted"], poll)
            self.assertEqual(poll["snapshot"]["status"], "complete", poll["snapshot"])
            self.assertEqual(planner.select_calls, 1)
            self.assertEqual(planner.plan_calls, 1)


class SelectionIdempotencyTests(unittest.TestCase):
    def test_repeated_polls_do_not_recall_the_model(self):
        """Idempotency: re-polling a resolved job reuses the result (ADR-0026 D4)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = _D2FakePlanner(selects="climate.upstairs_thermostat")
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=Path(temp_dir),
                extra_metadata_by_entity=_THERMOSTAT_METADATA,
            )

            start = _start_job(hass, entry, prompt=THERMOSTAT_PROMPT)
            job_id = start["snapshot"]["job_id"]

            first = _snapshot_job(hass, entry, job_id, message_id=2)
            self.assertEqual(first["snapshot"]["status"], "complete")

            # Several more polls must not re-run selection or planning.
            for message_id in range(3, 7):
                again = _snapshot_job(hass, entry, job_id, message_id=message_id)
                self.assertEqual(again["snapshot"]["status"], "complete", again["snapshot"])

            self.assertEqual(planner.select_calls, 1)
            self.assertEqual(planner.plan_calls, 1)

    def test_clarification_poll_is_stable_and_calls_model_once(self):
        """An abstain clarification is reached once; re-polling does not re-call D2."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = _D2FakePlanner(selects=None)
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=Path(temp_dir),
                extra_metadata_by_entity=_THERMOSTAT_METADATA,
            )

            start = _start_job(hass, entry, prompt=THERMOSTAT_PROMPT)
            job_id = start["snapshot"]["job_id"]

            first = _snapshot_job(hass, entry, job_id, message_id=2)
            self.assertEqual(first["snapshot"]["status"], "clarification_needed")

            second = _snapshot_job(hass, entry, job_id, message_id=3)
            self.assertEqual(second["snapshot"]["status"], "clarification_needed", second["snapshot"])
            # Selection ran exactly once; the stable clarification snapshot is replayed.
            self.assertEqual(planner.select_calls, 1)


class SynchronousRejectionTests(unittest.TestCase):
    def test_empty_catalog_fails_synchronously_on_start(self):
        """A pre-model structural rejection (empty catalog) stays on job/start (ADR-0026)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = _D2FakePlanner(selects="climate.upstairs_thermostat")
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=Path(temp_dir),
                extra_metadata_by_entity=_THERMOSTAT_METADATA,
            )
            # Empty the approved catalog after setup so job/start sees no entities.
            hass.data[DOMAIN][entry.entry_id][DATA_ENTITY_CATALOG]["items"] = []

            start = _start_job(hass, entry, prompt=THERMOSTAT_PROMPT)

            self.assertTrue(start["accepted"], start)
            self.assertEqual(start["snapshot"]["status"], "failed", start["snapshot"])
            self.assertEqual(
                start["snapshot"]["failure"]["code"],
                "no_approved_entities_available",
                start["snapshot"]["failure"],
            )
            # Failed synchronously without any model call or deferred planning snapshot.
            self.assertEqual(planner.select_calls, 0)
            self.assertNotEqual(
                start["snapshot"]["progress"]["stage"], ENTITY_SELECTION_PENDING_STAGE
            )


class RetryDefersSelectionTests(unittest.TestCase):
    """ADR-0026 D5: job/retry defers re-resolution to the planning poll like start."""

    def _seed_retryable_failure(self, hass, entry, job_id):
        job = job_orchestration._job_for_command(
            hass, entry.entry_id, {"config_entry_id": entry.entry_id, "job_id": job_id}
        )
        job_orchestration._append_failed_snapshot(
            job,
            code="model_provider_connection_error",
            stage="model_provider_planning",
            message="The model provider could not be reached.",
            checks=[
                {"name": "integration_job_state_scaffold", "status": "pass"},
                {"name": "model_provider", "status": "fail"},
            ],
        )

    def _retry_job(self, hass, entry, job_id, *, message_id):
        return handle_registered_ws_command(
            hass,
            {
                "id": message_id,
                "type": COMMAND_RETRY_JOB,
                "version": INTEGRATION_WS_VERSION,
                "config_entry_id": entry.entry_id,
                "job_id": job_id,
            },
        )

    def test_retry_returns_planning_and_resolves_on_poll(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = _D2FakePlanner(selects="climate.upstairs_thermostat")
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=Path(temp_dir),
                extra_metadata_by_entity=_THERMOSTAT_METADATA,
            )
            start = _start_job(hass, entry, prompt=THERMOSTAT_PROMPT)
            job_id = start["snapshot"]["job_id"]
            # Drive the job to a retryable failed state, then reset call counters so
            # the retry path's model usage is measured in isolation.
            self._seed_retryable_failure(hass, entry, job_id)
            planner.select_calls = 0
            planner.plan_calls = 0

            retry = self._retry_job(hass, entry, job_id, message_id=2)

            self.assertTrue(retry["accepted"], retry)
            self.assertEqual(retry["snapshot"]["status"], "planning", retry["snapshot"])
            self.assertEqual(
                retry["snapshot"]["progress"]["stage"], ENTITY_SELECTION_PENDING_STAGE
            )
            # Retry made no model call; selection is deferred to the poll.
            self.assertEqual(planner.select_calls, 0)

            poll = _snapshot_job(hass, entry, job_id, message_id=3)
            self.assertEqual(poll["snapshot"]["status"], "complete", poll["snapshot"])
            self.assertEqual(planner.select_calls, 1)
            self.assertEqual(planner.plan_calls, 1)


if __name__ == "__main__":
    unittest.main()
