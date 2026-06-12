from __future__ import annotations

from .worker_health_polling_anchor_fixtures import *  # noqa: F403


def verify_worker_health_polling_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in WORKER_HEALTH_POLLING_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_setup_enqueues_post_setup_poll_without_worker_call(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-setup-entry",
        _accepted_health_response("ready"),
    )
    setup = setup_worker_health_polling(hass, entry, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    return {
        "setup": _polling_setup_summary(setup),
        "state": _polling_state_summary(state),
        "state_validation": _validate_polling_state(state, root),
        "storage": get_worker_health_polling_storage(hass).summary(),
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
    }


def verify_home_assistant_timer_schedules_post_setup_and_next_poll(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-scheduler-entry",
        _accepted_health_response("ready"),
    )
    scheduler = FakePollingScheduler().install(hass, executor=True)
    setup = setup_worker_health_polling(hass, entry, now=BASE_TIME)
    entry_data = _entry_data(hass, entry.entry_id)
    setup_timer = deepcopy(entry_data.get(DATA_WORKER_HEALTH_POLLING_TIMER))
    health_calls_after_setup = client.health_calls

    fired = scheduler.fire_next(BASE_TIME)
    state_after_fire = get_worker_health_polling_state(hass, entry.entry_id)
    next_timer = deepcopy(entry_data.get(DATA_WORKER_HEALTH_POLLING_TIMER))
    unload = unload_worker_health_polling(hass, entry.entry_id)

    return {
        "setup": _polling_setup_summary(setup),
        "setup_timer": setup_timer,
        "health_calls_after_setup": health_calls_after_setup,
        "fired_timer_delay_seconds": fired["delay_seconds"],
        "state_after_fire": _polling_state_summary(state_after_fire),
        "state_validation": _validate_polling_state(state_after_fire, root),
        "next_timer": next_timer,
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
        "created_task_count": scheduler.summary()["created_task_count"],
        "executor_job_count": scheduler.summary()["executor_job_count"],
        "unload": unload,
        "timer_absent_after_unload": DATA_WORKER_HEALTH_POLLING_TIMER not in entry_data,
        "scheduler": scheduler.summary(),
    }


def verify_scheduled_ready_poll_records_cadence(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-ready-entry",
        _accepted_health_response("ready"),
    )
    setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    entry_data = _entry_data(hass, entry.entry_id)
    return {
        "result": _polling_result_summary(result),
        "state": _polling_state_summary(state),
        "state_validation": _validate_polling_state(state, root),
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
        "explicit_health_state_written": "worker_health" in entry_data,
        "worker_health_setup_code": entry_data["worker_health_setup"]["code"],
        "next_poll_delay_seconds": _seconds_between(
            state["scheduler"]["last_poll_at"],
            state["scheduler"]["next_poll_not_before"],
        ),
        "ready_cadence_seconds": READY_POLL_CADENCE_SECONDS,
    }


def verify_next_poll_timing_blocks_early_duplicate_polls(root=None) -> dict[str, Any]:
    root = root or repo_root()
    ready_hass, ready_entry, ready_client, _ready_provision, _ready_setup = _ready_hass_with_fake_health_client(
        "worker-polling-early-ready-entry",
        _accepted_health_response("ready"),
    )
    setup_worker_health_polling(ready_hass, ready_entry, now=BASE_TIME)
    first_ready = run_worker_health_poll(ready_hass, ready_entry.entry_id, now=BASE_TIME)
    early_ready = run_worker_health_poll(
        ready_hass,
        ready_entry.entry_id,
        now=BASE_TIME + timedelta(seconds=60),
    )
    ready_state = get_worker_health_polling_state(ready_hass, ready_entry.entry_id)
    _entry_data(ready_hass, ready_entry.entry_id).pop(DATA_WORKER_RENDER_CLIENT, None)
    lost_precondition_ready = run_worker_health_poll(
        ready_hass,
        ready_entry.entry_id,
        now=BASE_TIME + timedelta(seconds=90),
    )
    lost_precondition_state = get_worker_health_polling_state(ready_hass, ready_entry.entry_id)

    not_ready_hass, not_ready_entry, not_ready_client, _provision, _setup = _ready_hass_with_fake_health_client(
        "worker-polling-early-not-ready-entry",
        _accepted_health_response("not_ready", rendering=False),
    )
    setup_worker_health_polling(not_ready_hass, not_ready_entry, now=BASE_TIME)
    first_not_ready = run_worker_health_poll(not_ready_hass, not_ready_entry.entry_id, now=BASE_TIME)
    early_not_ready = run_worker_health_poll(
        not_ready_hass,
        not_ready_entry.entry_id,
        now=BASE_TIME + timedelta(seconds=10),
    )
    not_ready_state = get_worker_health_polling_state(not_ready_hass, not_ready_entry.entry_id)

    return {
        "ready": {
            "first_result": _polling_result_summary(first_ready),
            "early_result": _polling_result_summary(early_ready),
            "state": _polling_state_summary(ready_state),
            "state_validation": _validate_polling_state(ready_state, root),
            "health_call_count": ready_client.health_calls,
            "next_poll_delay_seconds": _seconds_between(
                ready_state["scheduler"]["last_poll_at"],
                ready_state["scheduler"]["next_poll_not_before"],
            ),
            "lost_precondition_result": _polling_result_summary(lost_precondition_ready),
            "lost_precondition_state": _polling_state_summary(lost_precondition_state),
            "lost_precondition_validation": _validate_polling_state(lost_precondition_state, root),
        },
        "not_ready": {
            "first_result": _polling_result_summary(first_not_ready),
            "early_result": _polling_result_summary(early_not_ready),
            "state": _polling_state_summary(not_ready_state),
            "state_validation": _validate_polling_state(not_ready_state, root),
            "health_call_count": not_ready_client.health_calls,
            "consecutive_failures": not_ready_state["scheduler"]["consecutive_failures"],
            "backoff_seconds": not_ready_state["scheduler"]["backoff_seconds"],
        },
    }


def verify_failure_poll_results_use_bounded_backoff(root=None) -> dict[str, Any]:
    root = root or repo_root()
    not_ready_hass, not_ready_entry, not_ready_client, _provision, _setup = _ready_hass_with_fake_health_client(
        "worker-polling-not-ready-entry",
        _accepted_health_response("not_ready", rendering=False),
    )
    setup_worker_health_polling(not_ready_hass, not_ready_entry, now=BASE_TIME)
    first_not_ready = run_worker_health_poll(not_ready_hass, not_ready_entry.entry_id, now=BASE_TIME)
    second_not_ready = run_worker_health_poll(not_ready_hass, not_ready_entry.entry_id, now=SECOND_TIME)
    not_ready_state = get_worker_health_polling_state(not_ready_hass, not_ready_entry.entry_id)

    unavailable_hass, unavailable_entry, unavailable_client, _provision, _setup = _ready_hass_with_fake_health_client(
        "worker-polling-unavailable-entry",
        {
            "accepted": False,
            "code": "worker_connection_error",
            "message": "Connection refused by worker health endpoint.",
            "retry_safe": True,
        },
    )
    setup_worker_health_polling(unavailable_hass, unavailable_entry, now=BASE_TIME)
    unavailable_result = run_worker_health_poll(unavailable_hass, unavailable_entry.entry_id, now=BASE_TIME)
    unavailable_state = get_worker_health_polling_state(unavailable_hass, unavailable_entry.entry_id)

    return {
        "not_ready": {
            "first_result": _polling_result_summary(first_not_ready),
            "second_result": _polling_result_summary(second_not_ready),
            "state": _polling_state_summary(not_ready_state),
            "state_validation": _validate_polling_state(not_ready_state, root),
            "health_call_count": not_ready_client.health_calls,
            "render_call_count": not_ready_client.render_calls,
        },
        "unavailable": {
            "result": _polling_result_summary(unavailable_result),
            "state": _polling_state_summary(unavailable_state),
            "state_validation": _validate_polling_state(unavailable_state, root),
            "health_call_count": unavailable_client.health_calls,
            "render_call_count": unavailable_client.render_calls,
        },
        "expected_backoff_seconds": list(FAILURE_BACKOFF_SECONDS),
    }


def verify_missing_preconditions_block_before_worker_call(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-polling-blocked-entry")
    hass = _setup_readiness_hass(entry)
    setup = setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    return {
        "setup": _polling_setup_summary(setup),
        "result": _polling_result_summary(result),
        "state": _polling_state_summary(state),
        "state_validation": _validate_polling_state(state, root),
        "worker_client_present": DATA_WORKER_RENDER_CLIENT in _entry_data(hass, entry.entry_id),
    }


def verify_single_flight_guard_prevents_overlapping_poll(root=None) -> dict[str, Any]:
    root = root or repo_root()
    normal_poll = verify_normal_poll_marks_and_clears_in_flight_guard(root)
    hass, entry, client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-single-flight-entry",
        _accepted_health_response("ready"),
    )
    setup_worker_health_polling(hass, entry, now=BASE_TIME)
    mark = mark_worker_health_poll_in_flight(hass, entry.entry_id)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    return {
        "mark": _polling_result_summary(mark),
        "result": _polling_result_summary(result),
        "state": _polling_state_summary(state),
        "state_validation": _validate_polling_state(state, root),
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
        "normal_poll": normal_poll,
    }


def verify_normal_poll_marks_and_clears_in_flight_guard(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, _client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-normal-single-flight-entry",
        _accepted_health_response("ready"),
    )
    client = InspectingWorkerHealthClient(
        hass=hass,
        entry_id=entry.entry_id,
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token=WORKER_READINESS_TEST_TOKEN,
        response=_accepted_health_response("ready"),
    )
    _entry_data(hass, entry.entry_id)[DATA_WORKER_RENDER_CLIENT] = client
    setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    return {
        "result": _polling_result_summary(result),
        "state": _polling_state_summary(state),
        "state_validation": _validate_polling_state(state, root),
        "poll_in_flight_during_health_call": client.poll_in_flight_during_health_call,
        "poll_in_flight_after_poll": state["scheduler"]["poll_in_flight"],
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
    }


def verify_unload_removes_durable_polling_state(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = _worker_entry("worker-polling-unload-entry-a")
    entry_b = _worker_entry("worker-polling-unload-entry-b")
    _setup_entry_in_hass(hass, entry_a)
    _setup_entry_in_hass(hass, entry_b)
    _make_entry_ready_for_polling(hass, entry_a, _accepted_health_response("ready"), WORKER_READINESS_TEST_TOKEN)
    _make_entry_ready_for_polling(hass, entry_b, _accepted_health_response("ready"), WORKER_READINESS_SECOND_TOKEN)
    setup_worker_health_polling(hass, entry_a, now=BASE_TIME)
    setup_worker_health_polling(hass, entry_b, now=BASE_TIME)
    before_unload = get_worker_health_polling_storage(hass).summary()
    unload_result = _run(async_unload_entry(hass, entry_a))
    after_unload = get_worker_health_polling_storage(hass).summary()
    return {
        "before_unload": before_unload,
        "unload_result": unload_result,
        "after_unload": after_unload,
        "entry_a_state": get_worker_health_polling_state(hass, entry_a.entry_id),
        "entry_b_state": _polling_state_summary(get_worker_health_polling_state(hass, entry_b.entry_id)),
        "entry_b_validation": _validate_polling_state(get_worker_health_polling_state(hass, entry_b.entry_id), root),
    }


def verify_worker_health_polling_stays_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = _worker_entry("worker-polling-isolation-entry-a")
    entry_b = _worker_entry("worker-polling-isolation-entry-b")
    _setup_entry_in_hass(hass, entry_a)
    _setup_entry_in_hass(hass, entry_b)
    client_a = _make_entry_ready_for_polling(
        hass,
        entry_a,
        _accepted_health_response("ready"),
        WORKER_READINESS_TEST_TOKEN,
    )
    client_b = _make_entry_ready_for_polling(
        hass,
        entry_b,
        _accepted_health_response("not_ready", rendering=False),
        WORKER_READINESS_SECOND_TOKEN,
    )
    setup_worker_health_polling(hass, entry_a, now=BASE_TIME)
    setup_worker_health_polling(hass, entry_b, now=BASE_TIME)
    result_a = run_worker_health_poll(hass, entry_a.entry_id, now=BASE_TIME)
    result_b = run_worker_health_poll(hass, entry_b.entry_id, now=BASE_TIME)
    state_a = get_worker_health_polling_state(hass, entry_a.entry_id)
    state_b = get_worker_health_polling_state(hass, entry_b.entry_id)
    return {
        "entry_a": {
            "result": _polling_result_summary(result_a),
            "state": _polling_state_summary(state_a),
            "state_validation": _validate_polling_state(state_a, root),
            "health_call_count": client_a.health_calls,
            "raw_request_uses_own_token": (
                client_a.received_health_requests[0]["headers"]["authorization"]
                == f"Bearer {WORKER_READINESS_TEST_TOKEN}"
            ),
            "other_token_absent_from_request": WORKER_READINESS_SECOND_TOKEN
            not in str(client_a.received_health_requests[0]),
        },
        "entry_b": {
            "result": _polling_result_summary(result_b),
            "state": _polling_state_summary(state_b),
            "state_validation": _validate_polling_state(state_b, root),
            "health_call_count": client_b.health_calls,
            "raw_request_uses_own_token": (
                client_b.received_health_requests[0]["headers"]["authorization"]
                == f"Bearer {WORKER_READINESS_SECOND_TOKEN}"
            ),
            "other_token_absent_from_request": WORKER_READINESS_TEST_TOKEN
            not in str(client_b.received_health_requests[0]),
        },
    }


def verify_storage_load_merges_persisted_entries_without_dropping_unsaved(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass_a, entry_a, _client_a, _provision_a, _health_setup_a = _ready_hass_with_fake_health_client(
        "worker-polling-unsaved-entry",
        _accepted_health_response("ready"),
    )
    setup_worker_health_polling(hass_a, entry_a, now=BASE_TIME)
    unsaved_state = get_worker_health_polling_state(hass_a, entry_a.entry_id)

    hass_b, entry_b, _client_b, _provision_b, _health_setup_b = _ready_hass_with_fake_health_client(
        "worker-polling-persisted-entry",
        _accepted_health_response("ready"),
    )
    setup_worker_health_polling(hass_b, entry_b, now=BASE_TIME)
    persisted_state = get_worker_health_polling_state(hass_b, entry_b.entry_id)

    cadence_hass, cadence_entry, _cadence_client, _cadence_provision, _cadence_setup = (
        _ready_hass_with_fake_health_client(
            "worker-polling-invalid-cadence-source-entry",
            _accepted_health_response("ready"),
        )
    )
    setup_worker_health_polling(cadence_hass, cadence_entry, now=BASE_TIME)
    run_worker_health_poll(cadence_hass, cadence_entry.entry_id, now=BASE_TIME)
    invalid_cadence_state = get_worker_health_polling_state(cadence_hass, cadence_entry.entry_id)
    invalid_cadence_state["polling_id"] = "worker-polling-invalid-cadence-entry-worker-health-polling-001"
    invalid_cadence_state["config_entry_id"] = "worker-polling-invalid-cadence-entry"
    invalid_cadence_state["scheduler"]["next_poll_not_before"] = (
        BASE_TIME + timedelta(days=2)
    ).isoformat()

    token_missing_entry = _worker_entry("worker-polling-token-missing-entry")
    token_missing_hass = _setup_readiness_hass(token_missing_entry)
    provision = provision_integration_worker_token(
        token_missing_hass,
        token_missing_entry.entry_id,
        token_factory=CountingTokenFactory(WORKER_READINESS_TEST_TOKEN),
    )
    if not provision["accepted"]:
        raise AssertionError(f"Token provisioning failed for {token_missing_entry.entry_id}: {provision!r}")
    _entry_data(token_missing_hass, token_missing_entry.entry_id)[DATA_WORKER_RENDER_CLIENT] = FakeWorkerHealthClient(
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token="short",
        response=_accepted_health_response("ready"),
    )
    setup_worker_health_polling(token_missing_hass, token_missing_entry, now=BASE_TIME)
    token_missing_state = get_worker_health_polling_state(token_missing_hass, token_missing_entry.entry_id)

    invalid_bounds_state = deepcopy(persisted_state)
    invalid_bounds_state["polling_id"] = "worker-polling-invalid-bounds-entry-worker-health-polling-001"
    invalid_bounds_state["config_entry_id"] = "worker-polling-invalid-bounds-entry"
    invalid_bounds_state["scheduler"]["backoff_seconds"] = 901

    ha_store = FakeHomeAssistantPollingStore(
        {
            "version": 1,
            "entries": {
                entry_b.entry_id: persisted_state,
                token_missing_entry.entry_id: token_missing_state,
                "worker-polling-invalid-persisted-entry": {
                    "type": "not_a_valid_polling_state",
                    "config_entry_id": "worker-polling-invalid-persisted-entry",
                },
                "worker-polling-invalid-bounds-entry": invalid_bounds_state,
                "worker-polling-invalid-cadence-entry": invalid_cadence_state,
            },
        }
    )
    store = WorkerHealthPollingStorageHelper(ha_store=ha_store)
    store.write_state(entry_a.entry_id, unsaved_state)
    before_load = store.summary()
    after_load = _run(store.async_load())
    state_a_after_load = store.read_state(entry_a.entry_id)
    state_b_after_load = store.read_state(entry_b.entry_id)
    token_missing_state_after_load = store.read_state(token_missing_entry.entry_id)
    store.delete_state(entry_a.entry_id)
    ha_store.loaded_data["entries"][entry_a.entry_id] = unsaved_state
    after_unloaded_load = _run(store.async_load())
    return {
        "before_load": before_load,
        "after_load": after_load,
        "after_unloaded_load": after_unloaded_load,
        "unsaved_entry_present": entry_a.entry_id in after_load["entry_ids"],
        "persisted_entry_present": entry_b.entry_id in after_load["entry_ids"],
        "token_missing_entry_loaded": token_missing_entry.entry_id in after_load["entry_ids"],
        "invalid_entry_absent": "worker-polling-invalid-persisted-entry" not in after_load["entry_ids"],
        "invalid_bounds_entry_absent": "worker-polling-invalid-bounds-entry" not in after_load["entry_ids"],
        "invalid_cadence_entry_absent": "worker-polling-invalid-cadence-entry"
        not in after_load["entry_ids"],
        "unloaded_entry_not_remerged": entry_a.entry_id not in after_unloaded_load["entry_ids"],
        "persisted_entry_still_present_after_unloaded_load": entry_b.entry_id
        in after_unloaded_load["entry_ids"],
        "unsaved_state_preserved": state_a_after_load == unsaved_state,
        "persisted_state_loaded": state_b_after_load == persisted_state,
        "token_missing_state_loaded": token_missing_state_after_load == token_missing_state,
        "unloaded_state_not_loaded": store.read_state(entry_a.entry_id) is None,
        "invalid_state_not_loaded": store.read_state("worker-polling-invalid-persisted-entry") is None,
        "invalid_bounds_state_not_loaded": store.read_state("worker-polling-invalid-bounds-entry") is None,
        "invalid_cadence_state_not_loaded": store.read_state("worker-polling-invalid-cadence-entry") is None,
        "state_a_validation": _validate_polling_state(state_a_after_load, root),
        "state_b_validation": _validate_polling_state(state_b_after_load, root),
        "token_missing_validation": _validate_polling_state(token_missing_state_after_load, root),
        "save_delay_seconds": ha_store.save_delays[-1],
    }


def verify_setup_resumes_persisted_polling_cadence(root=None) -> dict[str, Any]:
    root = root or repo_root()
    source_hass, source_entry, source_client, _provision, _setup = _ready_hass_with_fake_health_client(
        "worker-polling-resume-entry",
        _accepted_health_response("not_ready", rendering=False),
    )
    setup_worker_health_polling(source_hass, source_entry, now=BASE_TIME)
    run_worker_health_poll(source_hass, source_entry.entry_id, now=BASE_TIME)
    run_worker_health_poll(source_hass, source_entry.entry_id, now=SECOND_TIME)
    persisted_state = get_worker_health_polling_state(source_hass, source_entry.entry_id)

    resumed_hass, resumed_entry, resumed_client, _resumed_provision, _resumed_health_setup = (
        _ready_hass_with_fake_health_client(
            source_entry.entry_id,
            _accepted_health_response("ready"),
        )
    )
    ha_store = FakeHomeAssistantPollingStore(
        {
            "version": 1,
            "entries": {
                source_entry.entry_id: persisted_state,
            },
        }
    )
    resumed_hass.data[DOMAIN][DATA_WORKER_HEALTH_POLLING_STORE] = WorkerHealthPollingStorageHelper(
        ha_store=ha_store
    )
    scheduler = FakePollingScheduler().install(resumed_hass, executor=True)
    resume_time = BASE_TIME + timedelta(seconds=90)
    setup = _run(async_setup_worker_health_polling(resumed_hass, resumed_entry, now=resume_time))
    resumed_state = get_worker_health_polling_state(resumed_hass, resumed_entry.entry_id)
    setup_timer = deepcopy(_entry_data(resumed_hass, resumed_entry.entry_id).get(DATA_WORKER_HEALTH_POLLING_TIMER))

    return {
        "setup": _polling_setup_summary(setup),
        "source_health_call_count": source_client.health_calls,
        "resumed_health_call_count": resumed_client.health_calls,
        "state": _polling_state_summary(resumed_state),
        "state_validation": _validate_polling_state(resumed_state, root),
        "setup_timer": setup_timer,
        "scheduler": scheduler.summary(),
        "persisted_next_poll_not_before": persisted_state["scheduler"]["next_poll_not_before"],
        "resumed_next_poll_not_before": resumed_state["scheduler"]["next_poll_not_before"],
        "cadence_preserved": resumed_state["scheduler"]["next_poll_not_before"]
        == persisted_state["scheduler"]["next_poll_not_before"],
        "consecutive_failures_preserved": resumed_state["scheduler"]["consecutive_failures"]
        == persisted_state["scheduler"]["consecutive_failures"],
        "backoff_seconds_preserved": resumed_state["scheduler"]["backoff_seconds"]
        == persisted_state["scheduler"]["backoff_seconds"],
    }


def verify_unload_races_do_not_resurrect_polling_state(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, _client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-unload-race-entry",
        _accepted_health_response("ready"),
    )
    client = UnloadingWorkerHealthClient(
        hass=hass,
        entry_id=entry.entry_id,
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token=WORKER_READINESS_TEST_TOKEN,
        response=_accepted_health_response("ready"),
    )
    _entry_data(hass, entry.entry_id)[DATA_WORKER_RENDER_CLIENT] = client
    setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    return {
        "result": _polling_result_summary(result),
        "state_after_poll": state,
        "state_absent_after_poll": state is None,
        "entry_data_absent_after_poll": entry.entry_id not in hass.data.get(DOMAIN, {}),
        "health_call_count": client.health_calls,
        "storage": get_worker_health_polling_storage(hass).summary(),
    }


def verify_in_flight_poll_does_not_write_after_same_entry_reload(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, _client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-reload-race-entry",
        _accepted_health_response("ready"),
    )
    client = ReloadingWorkerHealthClient(
        hass=hass,
        entry_id=entry.entry_id,
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token=WORKER_READINESS_TEST_TOKEN,
        response=_accepted_health_response("ready"),
    )
    _entry_data(hass, entry.entry_id)[DATA_WORKER_RENDER_CLIENT] = client
    setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    entry_data = _entry_data(hass, entry.entry_id)

    return {
        "result": _polling_result_summary(result),
        "state": _polling_state_summary(state),
        "state_validation": _validate_polling_state(state, root),
        "old_health_call_count": client.health_calls,
        "reloaded_health_call_count": (
            client.reloaded_client.health_calls if client.reloaded_client is not None else None
        ),
        "new_entry_is_current": entry_data.get("entry") is client.reloaded_entry,
        "old_worker_health_absent_from_reloaded_entry": "worker_health" not in entry_data,
        "stale_ready_state_absent": state["status"] == "scheduled",
        "stale_old_token_absent": WORKER_READINESS_TEST_TOKEN not in str(entry_data),
        "new_token_present_only_in_worker_client": (
            client.reloaded_client is not None
            and client.reloaded_client.worker_token == WORKER_READINESS_SECOND_TOKEN
        ),
        "storage": get_worker_health_polling_storage(hass).summary(),
    }


def verify_in_flight_poll_clears_after_worker_context_change(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, _client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-context-change-entry",
        _accepted_health_response("ready"),
    )
    client = RotatingWorkerHealthClient(
        hass=hass,
        entry_id=entry.entry_id,
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token=WORKER_READINESS_TEST_TOKEN,
        response=_accepted_health_response("ready"),
    )
    _entry_data(hass, entry.entry_id)[DATA_WORKER_RENDER_CLIENT] = client
    setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state_after_context_change = get_worker_health_polling_state(hass, entry.entry_id)
    follow_up_result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state_after_follow_up = get_worker_health_polling_state(hass, entry.entry_id)

    return {
        "result": _polling_result_summary(result),
        "state_after_context_change": _polling_state_summary(state_after_context_change),
        "context_state_validation": _validate_polling_state(state_after_context_change, root),
        "follow_up_result": _polling_result_summary(follow_up_result),
        "state_after_follow_up": _polling_state_summary(state_after_follow_up),
        "follow_up_state_validation": _validate_polling_state(state_after_follow_up, root),
        "old_health_call_count": client.health_calls,
        "replacement_health_call_count": (
            client.replacement_client.health_calls if client.replacement_client is not None else None
        ),
        "rotation_accepted": (
            isinstance(client.rotation_result, dict)
            and client.rotation_result.get("accepted") is True
        ),
        "in_flight_cleared": state_after_context_change["scheduler"]["poll_in_flight"] is False,
        "follow_up_poll_accepted": follow_up_result["accepted"] is True,
        "follow_up_used_replacement_client": (
            client.replacement_client is not None
            and client.replacement_client.health_calls == 1
        ),
        "storage": get_worker_health_polling_storage(hass).summary(),
    }


def verify_worker_health_polling_details_do_not_leak_to_card(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-leak-entry",
        _accepted_health_response("ready", message=f"Bearer {WORKER_READINESS_TEST_TOKEN} should not leak"),
    )
    setup = setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)

    endpoint_hass, endpoint_entry, _endpoint_client, _endpoint_provision, _endpoint_setup = _ready_hass_with_fake_health_client(
        "worker-polling-endpoint-message-entry",
        _accepted_health_response("ready", message=f"Worker ready at {WORKER_ENDPOINT_URL}"),
    )
    setup_worker_health_polling(endpoint_hass, endpoint_entry, now=BASE_TIME)
    endpoint_result = run_worker_health_poll(endpoint_hass, endpoint_entry.entry_id, now=BASE_TIME)
    endpoint_state = get_worker_health_polling_state(endpoint_hass, endpoint_entry.entry_id)

    endpoint_code_response = _accepted_health_response("ready")
    endpoint_code_response["health_result"]["code"] = f"{WORKER_ENDPOINT_URL}/v1/health"
    endpoint_code_hass, endpoint_code_entry, _endpoint_code_client, _endpoint_code_provision, _endpoint_code_setup = _ready_hass_with_fake_health_client(
        "worker-polling-endpoint-code-entry",
        endpoint_code_response,
    )
    setup_worker_health_polling(endpoint_code_hass, endpoint_code_entry, now=BASE_TIME)
    endpoint_code_result = run_worker_health_poll(
        endpoint_code_hass,
        endpoint_code_entry.entry_id,
        now=BASE_TIME,
    )
    endpoint_code_state = get_worker_health_polling_state(endpoint_code_hass, endpoint_code_entry.entry_id)

    bare_token_response = _accepted_health_response("ready", message=WORKER_READINESS_TEST_TOKEN)
    bare_token_response["health_result"]["code"] = WORKER_READINESS_TEST_TOKEN
    bare_token_hass, bare_token_entry, _bare_token_client, _bare_token_provision, _bare_token_setup = _ready_hass_with_fake_health_client(
        "worker-polling-bare-token-message-entry",
        bare_token_response,
    )
    setup_worker_health_polling(bare_token_hass, bare_token_entry, now=BASE_TIME)
    bare_token_result = run_worker_health_poll(bare_token_hass, bare_token_entry.entry_id, now=BASE_TIME)
    bare_token_state = get_worker_health_polling_state(bare_token_hass, bare_token_entry.entry_id)

    entry_data = _entry_data(hass, entry.entry_id)
    dashboard_metadata = entry_data["websocket_api"]
    model_provider_metadata = entry_data["model_provider_setup"]
    dashboard_visible_payload = {
        "websocket_api": dashboard_metadata,
        "card_snapshot_payload": {
            "accepted": True,
            "code": "no_card_polling_command",
            "worker_health_polling": None,
        },
    }
    evidence_payload = {
        "setup": _polling_setup_summary(setup),
        "result": _polling_result_summary(result),
        "polling_state": _polling_state_summary(state),
    }
    state_text = str(state)
    endpoint_state_text = str(endpoint_state)
    endpoint_code_state_text = str(endpoint_code_state)
    bare_token_state_text = str(bare_token_state)
    endpoint_evidence_payload = {
        "result": _polling_result_summary(endpoint_result),
        "polling_state": _polling_state_summary(endpoint_state),
    }
    bare_token_evidence_payload = {
        "result": _polling_result_summary(bare_token_result),
        "polling_state": _polling_state_summary(bare_token_state),
    }
    endpoint_code_evidence_payload = {
        "result": _polling_result_summary(endpoint_code_result),
        "polling_state": _polling_state_summary(endpoint_code_state),
    }
    dashboard_text = str(dashboard_visible_payload)
    return {
        "state_validation": _validate_polling_state(state, root),
        "endpoint_message_state_validation": _validate_polling_state(endpoint_state, root),
        "raw_worker_authorization_received": client.received_health_requests[0]["headers"]["authorization"].startswith(
            "Bearer "
        ),
        "token_absent_from_polling_state": WORKER_READINESS_TEST_TOKEN not in state_text,
        "token_absent_from_setup": WORKER_READINESS_TEST_TOKEN not in str(setup),
        "token_absent_from_evidence_payload": WORKER_READINESS_TEST_TOKEN not in str(evidence_payload),
        "token_absent_from_dashboard_card_metadata": WORKER_READINESS_TEST_TOKEN not in str(dashboard_metadata),
        "token_absent_from_model_provider_metadata": WORKER_READINESS_TEST_TOKEN not in str(model_provider_metadata),
        "endpoint_absent_from_polling_state": WORKER_ENDPOINT_URL not in state_text,
        "endpoint_message_absent_from_polling_state": WORKER_ENDPOINT_URL not in endpoint_state_text,
        "endpoint_message_url_scheme_absent": "http://" not in endpoint_state["health"]["message"],
        "endpoint_message_absent_from_evidence_payload": WORKER_ENDPOINT_URL not in str(endpoint_evidence_payload),
        "endpoint_code_absent_from_polling_state": "worker.local" not in endpoint_code_state_text,
        "endpoint_code_redacted": endpoint_code_state["code"] == "worker_health_redacted",
        "endpoint_health_code_redacted": endpoint_code_state["health"]["code"] == "worker_health_redacted",
        "endpoint_code_absent_from_evidence_payload": "worker.local" not in str(endpoint_code_evidence_payload),
        "bare_token_absent_from_polling_state": WORKER_READINESS_TEST_TOKEN not in bare_token_state_text,
        "bare_token_absent_from_evidence_payload": WORKER_READINESS_TEST_TOKEN not in str(bare_token_evidence_payload),
        "bare_token_code_redacted": bare_token_state["code"] == "worker_health_redacted",
        "bare_token_health_code_redacted": bare_token_state["health"]["code"] == "worker_health_redacted",
        "bare_token_message_redacted": bare_token_state["health"]["message"]
        == "Worker health endpoint response was sanitized.",
        "authorization_absent_from_polling_state": "Bearer " not in state_text,
        "request_absent_from_polling_state": "headers" not in state_text,
        "response_checks_absent_from_polling_state": "worker_process" not in state_text,
        "endpoint_absent_from_dashboard_payload": WORKER_ENDPOINT_URL not in dashboard_text,
        "polling_absent_from_dashboard_payload": "isolinear_worker_health_polling_state" not in dashboard_text,
        "repair_recommendation_absent_from_dashboard_payload": "recommendation" not in dashboard_text,
    }


def verify_worker_health_polling_side_effect_boundaries() -> dict[str, Any]:
    setup = verify_setup_enqueues_post_setup_poll_without_worker_call()
    scheduler = verify_home_assistant_timer_schedules_post_setup_and_next_poll()
    ready = verify_scheduled_ready_poll_records_cadence()
    failures = verify_failure_poll_results_use_bounded_backoff()
    blocked = verify_missing_preconditions_block_before_worker_call()
    single_flight = verify_single_flight_guard_prevents_overlapping_poll()
    isolation = verify_worker_health_polling_stays_config_entry_scoped()
    resume = verify_setup_resumes_persisted_polling_cadence()
    reload_race = verify_in_flight_poll_does_not_write_after_same_entry_reload()
    context_change = verify_in_flight_poll_clears_after_worker_context_change()

    observed = [
        {"name": "setup", **setup["setup"]["orchestration"]},
        {"name": "ha_timer_poll", **scheduler["state_after_fire"]["orchestration"]},
        {"name": "ready_poll", **ready["state"]["orchestration"]},
        {"name": "not_ready_poll", **failures["not_ready"]["state"]["orchestration"]},
        {"name": "unavailable_poll", **failures["unavailable"]["state"]["orchestration"]},
        {"name": "blocked_poll", **blocked["state"]["orchestration"]},
        {"name": "single_flight_guard", **single_flight["result"]["orchestration"]},
        {"name": "isolation_entry_a", **isolation["entry_a"]["state"]["orchestration"]},
        {"name": "isolation_entry_b", **isolation["entry_b"]["state"]["orchestration"]},
        {"name": "resume_setup", **resume["setup"]["orchestration"]},
        {"name": "reload_race", **reload_race["result"]["orchestration"]},
        {"name": "context_change", **context_change["state_after_context_change"]["orchestration"]},
    ]
    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in WORKER_HEALTH_POLLING_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "durable_health_storage_written": any(
            item.get("durable_health_storage_written") for item in observed
        ),
        "scheduler_bookkeeping_written": any(
            item.get("scheduler_bookkeeping_written") for item in observed
        ),
        "post_setup_poll_enqueued": any(item.get("post_setup_poll_enqueued") for item in observed),
        "worker_health_check_called": any(item.get("worker_health_check_called") for item in observed),
        "worker_health_request_validated": any(
            item.get("worker_health_request_validated") for item in observed
        ),
        "worker_health_response_validated": any(
            item.get("worker_health_response_validated") for item in observed
        ),
        "single_flight_guard_checked": any(
            item.get("single_flight_guard_checked") for item in observed
        ),
    }
    return {
        "expected_forbidden": {
            key: False for key in WORKER_HEALTH_POLLING_FORBIDDEN_SIDE_EFFECT_KEYS
        },
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }

__all__ = [name for name in globals() if name.startswith("verify_")]
