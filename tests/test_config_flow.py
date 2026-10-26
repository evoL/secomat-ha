"""Exercise setup and Claim Token replacement through Home Assistant's flow manager."""

import aiohttp
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.secomat.const import DOMAIN

from .conftest import PLC_URL, SECOMAT_STATE


@pytest.mark.parametrize("name", [None, "Laundry room", ""])
@pytest.mark.parametrize("source", ["ws", "db"])
async def test_user_creates_entry(hass, aioclient_mock, name, source):
    """Discover the Secomat ID from a Claim Token, even with cached cloud state."""
    aioclient_mock.get(
        PLC_URL,
        json={"src": source, "payload": {**SECOMAT_STATE, "serial_number": " 00.00000 "}},
    )
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    schema = {str(key): value for key, value in result["data_schema"].schema.items()}
    assert set(schema) == {"claim_token", "name"}
    assert schema["claim_token"].config["type"] == "password"
    assert result["data_schema"]({"claim_token": "new-token"})["name"] == "Secomat"

    user_input = {"claim_token": "new-token"}
    if name is not None:
        user_input["name"] = name
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == "00.00000"
    assert entry.title == (name or "Secomat")
    assert dict(entry.data) == {
        "secomat_id": "00.00000",
        "claim_token": "new-token",
        "name": name or "Secomat",
    }
    assert aioclient_mock.mock_calls[0][3]["claim-token"] == "new-token"
    await hass.async_block_till_done()


async def test_duplicate_secomat_id(hass, config_entry, cloud_api):
    """A different Claim Token cannot configure the same discovered Secomat ID twice."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={"claim_token": "other-token"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert cloud_api.call_count == 1
    assert cloud_api.mock_calls[0][3]["claim-token"] == "other-token"


@pytest.mark.parametrize(
    "identity",
    [{}, {"serial_number": None}, {"serial_number": ""}, {"serial_number": " \t\n"}],
    ids=["missing", "null", "empty", "whitespace"],
)
@pytest.mark.parametrize("source", ["user", "reconfigure", "reauth"])
async def test_missing_secomat_id_cannot_connect(
    hass, config_entry, aioclient_mock, identity, source
):
    """A successful HTTP response must identify a Secomat before accepting a Claim Token."""
    payload = {key: value for key, value in SECOMAT_STATE.items() if key != "serial_number"}
    aioclient_mock.get(PLC_URL, json={"payload": {**payload, **identity}})

    context = {"source": source}
    if source != "user":
        config_entry.add_to_hass(hass)
        context["entry_id"] = config_entry.entry_id
    result = await hass.config_entries.flow.async_init(DOMAIN, context=context)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"claim_token": "new-token"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    if source == "user":
        assert not hass.config_entries.async_entries(DOMAIN)
    else:
        assert config_entry.data["claim_token"] == "old-token"
        assert config_entry.unique_id == "00.00000"


@pytest.mark.parametrize("source", ["user", "reconfigure", "reauth"])
@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        ({"status": 401}, "invalid_auth"),
        ({"status": 403}, "invalid_auth"),
        ({"status": 500}, "cannot_connect"),
        ({"exc": aiohttp.ClientConnectionError()}, "cannot_connect"),
        ({"exc": TimeoutError()}, "cannot_connect"),
        ({"exc": ValueError("Unexpected response")}, "unknown"),
    ],
)
async def test_validation_failure_and_retry(
    hass, config_entry, aioclient_mock, source, response, expected_error
):
    """All forms distinguish errors, preserve the existing token, and allow retry."""
    config_entry.add_to_hass(hass)
    aioclient_mock.get(PLC_URL, **response)
    context = {"source": source}
    if source != "user":
        context["entry_id"] = config_entry.entry_id
    result = await hass.config_entries.flow.async_init(DOMAIN, context=context)
    user_input = {"claim_token": "replacement-token"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert config_entry.data["claim_token"] == "old-token"

    aioclient_mock.clear_requests()
    secomat_id = "00.00001" if source == "user" else "00.00000"
    aioclient_mock.get(
        PLC_URL, json={"payload": {**SECOMAT_STATE, "serial_number": secomat_id}}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
    if source == "user":
        assert result["type"] is FlowResultType.CREATE_ENTRY
    else:
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == f"{source}_successful"
        assert config_entry.data["claim_token"] == "replacement-token"
        assert config_entry.unique_id == "00.00000"
    await hass.async_block_till_done()


@pytest.mark.parametrize("source", ["reconfigure", "reauth"])
@pytest.mark.parametrize("unique_id", ["00.00000", None])
async def test_replacement_claim_token_rejects_different_secomat(
    hass, config_entry, cloud_api, source, unique_id
):
    """A Claim Token for another Secomat cannot replace the existing token or identity."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, unique_id=unique_id)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    original_data = dict(config_entry.data)
    cloud_api.clear_requests()
    cloud_api.get(PLC_URL, json={"payload": {**SECOMAT_STATE, "serial_number": "00.00001"}})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source, "entry_id": config_entry.entry_id}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"claim_token": "other-secomat-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == ("reauth_confirm" if source == "reauth" else "reconfigure")
    assert result["errors"] == {"base": "wrong_secomat"}
    assert dict(config_entry.data) == original_data
    assert config_entry.unique_id == unique_id
    assert config_entry.state is ConfigEntryState.LOADED
    assert cloud_api.call_count == 1  # Rejection must not reload the existing entry.

    cloud_api.clear_requests()
    cloud_api.get(PLC_URL, json={"payload": {**SECOMAT_STATE, "serial_number": " 00.00000 "}})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"claim_token": "replacement-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == f"{source}_successful"
    assert config_entry.data["claim_token"] == "replacement-token"
    assert config_entry.unique_id == unique_id


@pytest.mark.parametrize("source", ["reconfigure", "reauth"])
async def test_claim_token_replacement_reloads_existing_entry(
    hass, config_entry, cloud_api, source
):
    """Replacing a Claim Token reloads the same device and entity identities."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_registry = er.async_get(hass)
    entities_before = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    identities_before = {
        (entity.id, entity.entity_id, entity.device_id) for entity in entities_before
    }
    device_before = dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)[0]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source, "entry_id": config_entry.entry_id}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == ("reauth_confirm" if source == "reauth" else "reconfigure")
    schema = {str(key): value for key, value in result["data_schema"].schema.items()}
    assert set(schema) == {"claim_token"}
    assert schema["claim_token"].config["type"] == "password"

    cloud_api.clear_requests()
    cloud_api.get(PLC_URL, json={"payload": {**SECOMAT_STATE, "ambient_temperature": 23}})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"claim_token": "replacement-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == f"{source}_successful"
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.unique_id == "00.00000"
    assert config_entry.title == "Secomat"
    assert dict(config_entry.data) == {
        "secomat_id": "00.00000", "claim_token": "replacement-token", "name": "Secomat"
    }
    assert cloud_api.call_count == 2  # Validation and the reloaded entry's first refresh.
    assert all(call[3]["claim-token"] == "replacement-token" for call in cloud_api.mock_calls)
    entities_after = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    assert {(entity.id, entity.entity_id, entity.device_id) for entity in entities_after} == (
        identities_before
    )
    device_after = dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)[0]
    assert device_after.id == device_before.id
    assert hass.states.get("sensor.secomat_temperature").state == "23"
