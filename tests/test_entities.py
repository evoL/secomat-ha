"""Secomat readings and settings observed through Home Assistant's public state API."""

from datetime import timedelta

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import PLC_URL, SECOMAT_STATE, cloud_response


@pytest.mark.parametrize(
    ("raw", "running", "label", "raw_state"),
    [
        (0, "off", "Idle", "0"),
        (2, "on", "Fan only", "2"),
        (6, "on", "Drying", "6"),
        (12, "on", "Drying", "12"),
        (15, "off", "Idle", "15"),
        (4, "unknown", "Unknown", "4"),
        (None, "unknown", "unknown", "unknown"),
        ("missing", "unknown", "unknown", "unknown"),
    ],
)
@pytest.mark.parametrize(("power_mode", "room_drying"), [(2, 0), (1, 1)])
async def test_drying_state_readings(
    hass, config_entry, aioclient_mock, raw, running, label, raw_state, power_mode, room_drying
):
    """Physical Drying State preserves unseen integers and missing readings without averaging."""
    payload = {
        **SECOMAT_STATE,
        "secomat_state": raw,
        "operating_mode": power_mode,
        "room_drying_enabled": room_drying,
    }
    if raw == "missing":
        del payload["secomat_state"]
    aioclient_mock.get(PLC_URL, json=cloud_response(payload))
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    drying = hass.states.get("binary_sensor.secomat_drying")
    assert drying is not None
    assert drying.state == running
    assert drying.attributes["device_class"] == "running"
    state = hass.states.get("sensor.secomat_drying_state")
    assert state.state == label
    assert state.attributes["device_class"] == "enum"
    assert state.attributes["options"] == ["Idle", "Fan only", "Drying", "Unknown"]
    raw_reading = hass.states.get("sensor.secomat_drying_state_raw")
    assert raw_reading.state == raw_state
    assert "state_class" not in raw_reading.attributes
    assert "unit_of_measurement" not in raw_reading.attributes


async def test_problem_follows_active_errors(hass, config_entry, aioclient_mock, freezer):
    """Warnings/errors appear as attributes and clear when empty or missing on a later poll."""
    errors = ["FILTER_CLEANING", "SENSOR_FAULT"]
    aioclient_mock.get(PLC_URL, json=cloud_response({**SECOMAT_STATE, "error_list": errors}))
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    problem = hass.states.get("binary_sensor.secomat_problem")
    assert problem is not None
    assert problem.state == "on"
    assert problem.attributes["device_class"] == "problem"
    assert problem.attributes["errors"] == ["FILTER_CLEANING", "SENSOR_FAULT"]

    missing_errors = {key: value for key, value in SECOMAT_STATE.items() if key != "error_list"}
    for payload in ({**SECOMAT_STATE, "error_list": []}, missing_errors):
        aioclient_mock.clear_requests()
        aioclient_mock.get(PLC_URL, json=cloud_response(payload))
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done(wait_background_tasks=True)
        assert aioclient_mock.call_count == 1
        problem = hass.states.get("binary_sensor.secomat_problem")
        assert problem.state == "off"
        assert problem.attributes["errors"] == []
