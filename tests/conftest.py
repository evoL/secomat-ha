"""Shared fixtures for testing at the Krüger cloud HTTP boundary."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.secomat.const import DOMAIN

PLC_URL = "https://seco.krueger.ch:8080/app1/v1/plc"
SECOMAT_STATE = {
    "ambient_temperature": 21.5,
    "humidity": 48,
    "target_humidity_level": 2,
    "fw_version": "1.2.3",
    "eye_seeing_object": 1,
    "room_drying_enabled": 1,
    "operating_mode": 1,
}


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to discover this custom integration."""


@pytest.fixture
def cloud_api(aioclient_mock):
    """Serve a representative Secomat state without contacting the cloud."""
    aioclient_mock.get(PLC_URL, json={"payload": SECOMAT_STATE})
    return aioclient_mock


@pytest.fixture
def config_entry():
    """An existing Secomat, not yet added to Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Secomat",
        unique_id="00.00000",
        data={"secomat_id": "00.00000", "claim_token": "old-token", "name": "Secomat"},
    )
