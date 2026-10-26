"""Verify the integration through config entries, registries, states, and services."""

import asyncio
from datetime import timedelta

import aiohttp
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_fire_time_changed_exact,
)

from custom_components.secomat.const import DOMAIN

from .conftest import PLC_URL, SECOMAT_STATE, cloud_response

EXPECTED_ENTITIES = {
    "sensor.secomat_temperature": ("temperature", "Temperature", "21.5"),
    "sensor.secomat_humidity": ("humidity", "Humidity", "48"),
    "sensor.secomat_target_humidity_level": ("target_humidity_level", "Target humidity level", "2"),
    "sensor.secomat_firmware_version": ("fw_version", "Firmware version", "1.2.3"),
    "binary_sensor.secomat_laundry_detected": ("eye_seeing_object", "Laundry detected", "on"),
    "binary_sensor.secomat_room_drying_enabled": (
        "room_drying_enabled", "Room drying enabled", "on"
    ),
    "binary_sensor.secomat_connectivity": ("connectivity", "Connectivity", "on"),
    "switch.secomat_auto_dry": ("auto_dry_switch", "Auto dry", "on"),
    "switch.secomat_room_drying": ("room_drying_switch", "Room drying", "on"),
    "select.secomat_power_mode": ("power_mode", "Power mode", "Auto"),
}


async def test_setup_registers_device_and_ten_entities(hass, config_entry, cloud_api):
    """One Secomat groups all entities without changing their existing identities."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert device.identifiers == {(DOMAIN, "00.00000")}
    assert device.name == "Secomat"
    assert device.manufacturer == "Krüger + Co. AG"
    assert device.model == "Secomat"
    assert device.serial_number == "00.00000"
    assert device.sw_version == "1.2.3"

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    assert {entity.entity_id for entity in entities} == set(EXPECTED_ENTITIES)
    for entity_id, (key, relative_name, state) in EXPECTED_ENTITIES.items():
        entity = entity_registry.async_get(entity_id)
        assert entity.device_id == device.id
        assert entity.unique_id == f"secomat_00.00000_{key}"
        assert entity.original_name == relative_name
        assert hass.states.get(entity_id).state == state
        if key in {"target_humidity_level", "fw_version", "connectivity"}:
            assert entity.entity_category.value == "diagnostic"

    connectivity = hass.states.get("binary_sensor.secomat_connectivity")
    assert connectivity.attributes["device_class"] == "connectivity"
    assert connectivity.attributes["source"] == "ws"
    assert connectivity.attributes["age"] == "2026-10-26T12:00:00Z"


async def test_legacy_entity_registry_records_are_reused(hass, config_entry, cloud_api):
    """Moving to UI setup retains entity IDs, including a user-renamed entity."""
    registry = er.async_get(hass)
    legacy_entities = {}
    for entity_id, (key, _, _) in EXPECTED_ENTITIES.items():
        domain, suggested_id = entity_id.split(".")
        if key == "temperature":
            suggested_id = "laundry_temperature"
        entity = registry.async_get_or_create(
            domain, DOMAIN, f"secomat_00.00000_{key}", suggested_object_id=suggested_id
        )
        legacy_entities[entity.entity_id] = entity.id

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entities = er.async_entries_for_config_entry(registry, config_entry.entry_id)
    assert {entity.entity_id: entity.id for entity in entities} == legacy_entities
    assert hass.states.get("sensor.laundry_temperature").state == "21.5"
    assert hass.states.get("sensor.secomat_temperature") is None
    assert all(entity.device_id is not None for entity in entities)


async def test_remove_entry_cleans_up_device_and_entities(hass, config_entry, cloud_api, freezer):
    """Removing a Secomat from the UI leaves no device, entities, or polling behind."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    registry = dr.async_get(hass)
    device = dr.async_entries_for_config_entry(registry, config_entry.entry_id)[0]
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(config_entry.entry_id) is None
    assert registry.async_get(device.id) is None
    assert not er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    assert all(hass.states.get(entity_id) is None for entity_id in EXPECTED_ENTITIES)
    cloud_api.clear_requests()
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert cloud_api.call_count == 0


@pytest.mark.parametrize("status", [401, 403, 503])
async def test_first_refresh_failure(hass, config_entry, aioclient_mock, status):
    """Setup retries outages and prompts for a new Claim Token on authentication failure."""
    aioclient_mock.get(PLC_URL, status=status)
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert not er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    if status == 503:
        assert config_entry.state is ConfigEntryState.SETUP_RETRY
        assert not hass.config_entries.flow.async_progress()
    else:
        assert config_entry.state is ConfigEntryState.SETUP_ERROR
        [flow] = hass.config_entries.flow.async_progress()
        assert flow["context"]["source"] == "reauth"
        assert flow["context"]["entry_id"] == config_entry.entry_id


@pytest.mark.parametrize("status", [401, 403, 503])
@pytest.mark.parametrize("initial_source", ["ws", "db"])
@pytest.mark.parametrize("recovery_source", ["ws", "db"])
async def test_polling_failure_and_recovery(
    hass, config_entry, aioclient_mock, freezer, status, initial_source, recovery_source
):
    """Only rejected Claim Tokens start reauth; transient outages recover on the next poll."""
    cloud_api = aioclient_mock
    cloud_api.get(PLC_URL, json=cloud_response(source=initial_source))
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    cloud_api.clear_requests()
    cloud_api.get(PLC_URL, status=status)

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert cloud_api.call_count == 1
    assert all(hass.states.get(entity_id).state == "unavailable" for entity_id in EXPECTED_ENTITIES)

    if status == 503:
        assert not hass.config_entries.flow.async_progress()
        cloud_api.clear_requests()
        cloud_api.get(PLC_URL, json=cloud_response(source=recovery_source))
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done(wait_background_tasks=True)
    else:
        [flow] = hass.config_entries.flow.async_progress()
        assert flow["context"]["source"] == "reauth"
        assert flow["context"]["entry_id"] == config_entry.entry_id
        cloud_api.clear_requests()
        cloud_api.get(PLC_URL, json=cloud_response(source=recovery_source))
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"claim_token": "replacement-token"}
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert not hass.config_entries.flow.async_progress()
    for entity_id, (_, _, live_state) in EXPECTED_ENTITIES.items():
        if entity_id == "binary_sensor.secomat_connectivity":
            assert hass.states.get(entity_id).state == ("on" if recovery_source == "ws" else "off")
            assert hass.states.get(entity_id).attributes["source"] == recovery_source
        else:
            expected_state = live_state if recovery_source == "ws" else "unavailable"
            assert hass.states.get(entity_id).state == expected_state


@pytest.mark.parametrize("source", ["ws", "db"])
async def test_firmware_version_tracks_latest_poll(hass, config_entry, cloud_api, freezer, source):
    """The Device Registry follows firmware metadata from both live and cached state."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    cloud_api.clear_requests()
    cloud_api.get(
        PLC_URL, json=cloud_response({**SECOMAT_STATE, "fw_version": "2.0.0"}, source=source)
    )
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    expected_state = "2.0.0" if source == "ws" else "unavailable"
    assert hass.states.get("sensor.secomat_firmware_version").state == expected_state
    device = dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)[0]
    assert device.sw_version == "2.0.0"


async def test_unload_stops_polling_and_reload_preserves_entities(
    hass, config_entry, cloud_api, freezer
):
    """Unload all four platforms, cancel polling, and keep entity identities on reload."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert all(
        hass.states.get(entity_id) is None or hass.states.get(entity_id).state == "unavailable"
        for entity_id in EXPECTED_ENTITIES
    )
    cloud_api.clear_requests()
    cloud_api.get(PLC_URL, json=cloud_response())
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert cloud_api.call_count == 0

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entities = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    assert {entity.entity_id for entity in entities} == set(EXPECTED_ENTITIES)
    assert hass.states.get("sensor.secomat_temperature").state == "21.5"


async def test_multiple_entries_are_independent(hass, config_entry, cloud_api, freezer):
    """Each Secomat has its own coordinator, device, and unload lifecycle."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Upstairs",
        unique_id="00.00001",
        data={"secomat_id": "00.00001", "claim_token": "upstairs-token", "name": "Upstairs"},
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    device_registry = dr.async_get(hass)
    first_device = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)[0]
    second_device = dr.async_entries_for_config_entry(device_registry, second.entry_id)[0]
    assert first_device.id != second_device.id
    assert second_device.name == "Upstairs"
    assert second_device.identifiers == {(DOMAIN, "00.00001")}
    assert hass.states.get("sensor.upstairs_temperature").state == "21.5"

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    cloud_api.clear_requests()
    cloud_api.get(PLC_URL, json=cloud_response({**SECOMAT_STATE, "ambient_temperature": 24}))
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert cloud_api.call_count == 1
    assert cloud_api.mock_calls[0][3]["claim-token"] == "upstairs-token"
    assert hass.states.get("sensor.upstairs_temperature").state == "24"


@pytest.mark.parametrize("status", [200, 204])
@pytest.mark.parametrize(
    ("entity_id", "service", "extra", "command", "payload", "expected_state"),
    [
        ("switch.secomat_auto_dry", "turn_on", {}, "WASH_AUTO", {"operating_mode": 1}, "on"),
        ("switch.secomat_auto_dry", "turn_off", {}, "OFF", {"operating_mode": 0}, "off"),
        ("switch.secomat_room_drying", "turn_on", {}, "ROOM_ON", {"room_drying_enabled": 1}, "on"),
        (
            "switch.secomat_room_drying", "turn_off", {}, "ROOM_OFF",
            {"room_drying_enabled": 0}, "off",
        ),
        (
            "select.secomat_power_mode", "select_option", {"option": "Off"},
            "OFF", {"operating_mode": 0}, "Off",
        ),
        (
            "select.secomat_power_mode", "select_option", {"option": "Auto"},
            "WASH_AUTO", {"operating_mode": 1}, "Auto",
        ),
        (
            "select.secomat_power_mode", "select_option", {"option": "Manual on"},
            "WASH_MANUAL_ON", {"operating_mode": 2}, "Manual on",
        ),
    ],
)
async def test_entity_commands(
    hass, config_entry, cloud_api, freezer,
    entity_id, service, extra, command, payload, expected_state, status,
):
    """Every control waits two seconds before fetching and publishing its new state."""
    cloud_api.clear_requests()
    initial_payload = {
        **SECOMAT_STATE, **{key: 0 if value else 1 for key, value in payload.items()}
    }
    cloud_api.get(PLC_URL, json=cloud_response(initial_payload))
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    initial_state = hass.states.get(entity_id).state
    assert initial_state != expected_state
    cloud_api.clear_requests()
    cloud_api.post(PLC_URL, status=status)
    cloud_api.get(PLC_URL, json=cloud_response({**SECOMAT_STATE, **payload}))
    service_task = asyncio.create_task(
        hass.services.async_call(
            entity_id.split(".")[0], service, {"entity_id": entity_id, **extra}, blocking=True
        )
    )
    try:
        # Let the service send its POST and schedule the delay without waiting for timers.
        for _ in range(20):
            await asyncio.sleep(0)
        assert cloud_api.call_count == 1
        assert cloud_api.mock_calls[0][0].lower() == "post"
        expected_args = {"prg_wash_starttime": 0} if command == "WASH_MANUAL_ON" else {}
        assert cloud_api.mock_calls[0][2] == {"command": command, "args": expected_args}
        assert cloud_api.mock_calls[0][3]["claim-token"] == "old-token"
        assert hass.states.get(entity_id).state == initial_state

        freezer.tick(timedelta(seconds=1.9))
        async_fire_time_changed_exact(hass, dt_util.utcnow())
        for _ in range(20):
            await asyncio.sleep(0)
        assert cloud_api.call_count == 1
        assert hass.states.get(entity_id).state == initial_state

        freezer.tick(timedelta(seconds=0.1))
        async_fire_time_changed_exact(hass, dt_util.utcnow())
        await service_task
        await hass.async_block_till_done()
        assert [call[0].lower() for call in cloud_api.mock_calls] == ["post", "get"]
        assert hass.states.get(entity_id).state == expected_state
    finally:
        service_task.cancel()
        await asyncio.gather(service_task, return_exceptions=True)


@pytest.mark.parametrize(
    ("entity_id", "service", "extra"),
    [
        ("select.secomat_power_mode", "select_option", {"option": "Off"}),
        ("switch.secomat_auto_dry", "turn_off", {}),
        ("switch.secomat_room_drying", "turn_off", {}),
    ],
)
@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"status": 400}, id="bad-request"),
        pytest.param({"status": 500}, id="server-error"),
        pytest.param({"status": 503}, id="unavailable"),
        pytest.param({"exc": aiohttp.ClientConnectionError("Connection lost")}, id="connection"),
        pytest.param({"exc": TimeoutError("Command timed out")}, id="timeout"),
    ],
)
async def test_failed_command_surfaces_service_error_without_refresh(
    hass, config_entry, cloud_api, freezer, entity_id, service, extra, response
):
    """API and transport failures notify the user without changing state or starting reauth."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    initial_state = hass.states.get(entity_id).state
    cloud_api.clear_requests()
    cloud_api.post(PLC_URL, **response)
    cloud_api.get(
        PLC_URL,
        json=cloud_response({**SECOMAT_STATE, "operating_mode": 0, "room_drying_enabled": 0}),
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            entity_id.split(".")[0], service, {"entity_id": entity_id, **extra}, blocking=True
        )
    await hass.async_block_till_done()
    assert not hass.config_entries.flow.async_progress()
    assert [call[0].lower() for call in cloud_api.mock_calls] == ["post"]

    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert [call[0].lower() for call in cloud_api.mock_calls] == ["post"]
    assert hass.states.get(entity_id).state == initial_state


@pytest.mark.parametrize("status", [401, 403])
@pytest.mark.parametrize(
    ("entity_id", "service", "extra"),
    [
        ("select.secomat_power_mode", "select_option", {"option": "Manual on"}),
        ("switch.secomat_auto_dry", "turn_off", {}),
        ("switch.secomat_room_drying", "turn_off", {}),
    ],
)
async def test_command_rejected_claim_token_starts_reauth_and_raises_service_error(
    hass, config_entry, cloud_api, freezer, entity_id, service, extra, status
):
    """Command authentication failures prompt immediately, without waiting for the next poll."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    cloud_api.clear_requests()
    cloud_api.post(PLC_URL, status=status)
    cloud_api.get(PLC_URL, json=cloud_response())

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            entity_id.split(".")[0], service, {"entity_id": entity_id, **extra}, blocking=True
        )
    await hass.async_block_till_done()
    [flow] = hass.config_entries.flow.async_progress()
    assert flow["context"]["source"] == "reauth"
    assert flow["context"]["entry_id"] == config_entry.entry_id
    assert config_entry.data["claim_token"] == "old-token"
    assert [call[0].lower() for call in cloud_api.mock_calls] == ["post"]

    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert [call[0].lower() for call in cloud_api.mock_calls] == ["post"]


async def test_add_offline_secomat_and_recover_on_poll(hass, aioclient_mock, freezer):
    """Cached state validates a Claim Token without publishing stale measurements."""
    aioclient_mock.get(PLC_URL, json=cloud_response(source="db"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={"claim_token": "new-token"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == "00.00000"
    assert entry.state is ConfigEntryState.LOADED
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    assert device.sw_version == "1.2.3"
    connectivity = hass.states.get("binary_sensor.secomat_connectivity")
    assert connectivity.state == "off"
    assert connectivity.attributes["source"] == "db"
    assert connectivity.attributes["age"] == "2026-10-26T12:00:00Z"
    for entity_id in EXPECTED_ENTITIES:
        if entity_id != "binary_sensor.secomat_connectivity":
            assert hass.states.get(entity_id).state == "unavailable"

    aioclient_mock.clear_requests()
    aioclient_mock.get(PLC_URL, json=cloud_response(age="2026-10-26T12:01:00Z"))
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert aioclient_mock.call_count == 1
    for entity_id, (_, _, state) in EXPECTED_ENTITIES.items():
        assert hass.states.get(entity_id).state == state
    connectivity = hass.states.get("binary_sensor.secomat_connectivity")
    assert connectivity.attributes["source"] == "ws"
    assert connectivity.attributes["age"] == "2026-10-26T12:01:00Z"


async def test_polling_interval_is_thirty_seconds(hass, config_entry, cloud_api, freezer):
    """No early poll, then updated state is visible after the 30-second interval."""
    freezer.move_to("2026-10-26T12:00:00Z")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    cloud_api.clear_requests()
    cloud_api.get(PLC_URL, json=cloud_response({**SECOMAT_STATE, "ambient_temperature": 24}))

    freezer.tick(timedelta(seconds=29))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert cloud_api.call_count == 0
    assert hass.states.get("sensor.secomat_temperature").state == "21.5"

    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert cloud_api.call_count == 1
    assert hass.states.get("sensor.secomat_temperature").state == "24"


@pytest.mark.parametrize(
    "metadata",
    [
        {"src": "db", "age": "2026-10-26T11:00:00Z"},
        {"src": "unexpected", "age": "2026-10-26T11:30:00Z"},
        {"src": None, "age": None},
        {},
    ],
    ids=["cached", "unknown-source", "null-metadata", "missing-metadata"],
)
async def test_source_changes_gate_all_appliance_entities(
    hass, config_entry, cloud_api, freezer, metadata
):
    """Only explicitly live state stays available; any other source is conservative offline."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    cloud_api.clear_requests()
    cloud_api.get(
        PLC_URL, json={**metadata, "payload": {**SECOMAT_STATE, "ambient_temperature": 99}}
    )
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert cloud_api.call_count == 1
    for entity_id in EXPECTED_ENTITIES:
        if entity_id != "binary_sensor.secomat_connectivity":
            assert hass.states.get(entity_id).state == "unavailable"
    connectivity = hass.states.get("binary_sensor.secomat_connectivity")
    assert connectivity.state == "off"
    assert connectivity.attributes["source"] == metadata.get("src")
    assert connectivity.attributes["age"] == metadata.get("age")

    cloud_api.clear_requests()
    cloud_api.get(PLC_URL, json=cloud_response(age="2026-10-26T12:02:00Z"))
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert cloud_api.call_count == 1
    for entity_id, (_, _, state) in EXPECTED_ENTITIES.items():
        assert hass.states.get(entity_id).state == state
    connectivity = hass.states.get("binary_sensor.secomat_connectivity")
    assert connectivity.attributes["source"] == "ws"
    assert connectivity.attributes["age"] == "2026-10-26T12:02:00Z"
