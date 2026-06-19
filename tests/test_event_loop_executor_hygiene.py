"""Event-loop / executor hygiene for schema loads and recorder reads.

These cover the 0.1.23 packet that removed two classes of Home Assistant
blocking-call warnings:

* bundled JSON Schema files were read and parsed on the event loop on every
  contract validation (now memoized + preloaded from an executor at setup);
* recorder reads ran on Home Assistant's general executor instead of the
  recorder's dedicated database executor.
"""

import asyncio
import json
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear import _paths  # noqa: E402
from custom_components.isolinear._paths import (  # noqa: E402
    SCHEMAS_DIR,
    load_schema_document,
    preload_schema_documents,
    schema_path,
)
from custom_components.isolinear import history_retrieval  # noqa: E402


class CachedSchemaLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        _paths._load_schema_document_cached.cache_clear()

    def test_load_matches_direct_parse(self) -> None:
        path = schema_path("entity-catalog-item.schema.json")
        self.assertEqual(
            load_schema_document(path),
            json.loads(path.read_text(encoding="utf-8")),
        )

    def test_file_read_once_per_path(self) -> None:
        path = schema_path("history-series.schema.json")
        with patch.object(_paths.json, "loads", wraps=_paths.json.loads) as parse:
            load_schema_document(path)
            load_schema_document(path)
            load_schema_document(path)
        # Memoized: three validations, one parse (and therefore one file read).
        self.assertEqual(parse.call_count, 1)

    def test_returns_isolated_copies(self) -> None:
        path = schema_path("history-series.schema.json")
        first = load_schema_document(path)
        first["__mutated_by_caller__"] = True
        second = load_schema_document(path)
        self.assertNotIn("__mutated_by_caller__", second)

    def test_preload_warms_every_bundled_schema(self) -> None:
        expected = len(list(SCHEMAS_DIR.glob("*.schema.json")))
        self.assertGreater(expected, 0)
        loaded = preload_schema_documents()
        self.assertEqual(loaded, expected)
        self.assertEqual(
            _paths._load_schema_document_cached.cache_info().currsize, expected
        )


class FakeRecorderInstance:
    """Stand-in recorder whose executor runs the read on a worker thread.

    Mirrors Home Assistant's recorder ``async_add_executor_job``: the read is
    dispatched onto a thread distinct from the loop, so the test exercises the
    real cross-thread round-trip rather than running the read inline.
    """

    def __init__(self) -> None:
        self.dispatched = 0

    async def async_add_executor_job(self, func, *args):
        self.dispatched += 1
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args)


class RecorderExecutorSeamTests(unittest.TestCase):
    def test_runs_inline_without_recorder_or_loop(self) -> None:
        calls = []

        def read():
            calls.append("ran")
            return "value"

        with patch.object(history_retrieval, "_recorder_db_instance", return_value=None):
            result = history_retrieval._read_via_recorder_executor(
                SimpleNamespace(), read
            )

        self.assertEqual(result, "value")
        self.assertEqual(calls, ["ran"])

    def test_dispatches_through_recorder_executor(self) -> None:
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        instance = FakeRecorderInstance()
        calls = []
        caller_thread = threading.get_ident()
        read_thread = []

        def read():
            calls.append("ran")
            read_thread.append(threading.get_ident())
            return {"sensor.x": ["point"]}

        try:
            with patch.object(
                history_retrieval, "_recorder_db_instance", return_value=instance
            ):
                result = history_retrieval._read_via_recorder_executor(
                    SimpleNamespace(loop=loop), read
                )
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=5)
            loop.close()

        # The read ran exactly once, dispatched through the recorder executor,
        # and on a different thread than the caller (true cross-thread bounce).
        self.assertEqual(result, {"sensor.x": ["point"]})
        self.assertEqual(calls, ["ran"])
        self.assertEqual(instance.dispatched, 1)
        self.assertNotIn(caller_thread, read_thread)


if __name__ == "__main__":
    unittest.main()
