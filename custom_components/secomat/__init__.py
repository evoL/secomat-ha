"""Krüger Secomat integration, configured through Home Assistant's UI."""

from __future__ import annotations

from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SecomatClient
from .const import CONF_CLAIM_TOKEN, CONF_SECOMAT_ID, DOMAIN
from .coordinator import SecomatConfigEntry, SecomatCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SELECT, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: SecomatConfigEntry) -> bool:
    """Set up one Secomat and its entities."""
    client = SecomatClient(async_get_clientsession(hass), entry.data[CONF_CLAIM_TOKEN])
    coordinator = SecomatCoordinator(
        hass, entry, client, entry.data[CONF_SECOMAT_ID], entry.data[CONF_NAME]
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SecomatConfigEntry) -> bool:
    """Unload all Secomat platforms and stop polling."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
