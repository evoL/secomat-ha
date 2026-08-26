"""Krüger Secomat integration.

YAML-configured (no config_flow, mirrors the bluesecur integration's conventions).
Reads a `credentials_file` JSON (see credentials.example.json) produced by extracting
the official app's local state, one entry per claimed device, and sets up a polling
coordinator + sensor/binary_sensor/select/switch entities per device.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SecomatApiError, SecomatClient
from .const import (
    CONF_CREDENTIALS_FILE,
    CONF_SCAN_INTERVAL,
    DEFAULT_API_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SELECT, Platform.SWITCH]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CREDENTIALS_FILE): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class SecomatCoordinator(DataUpdateCoordinator):
    """Polls one Secomat device's state."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SecomatClient,
        secomat_id: str,
        name: str,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"secomat_{secomat_id}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.secomat_id = secomat_id
        self.device_name = name

    async def _async_update_data(self):
        try:
            return await self.client.async_get_state()
        except SecomatApiError as err:
            raise UpdateFailed(str(err)) from err


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up from YAML."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    credentials_file = conf[CONF_CREDENTIALS_FILE]
    scan_interval = conf[CONF_SCAN_INTERVAL]

    def _load_credentials() -> dict:
        with open(credentials_file, encoding="utf-8") as f:
            return json.load(f)

    try:
        creds = await hass.async_add_executor_job(_load_credentials)
    except (OSError, json.JSONDecodeError) as err:
        _LOGGER.error("Could not read secomat credentials_file %s: %s", credentials_file, err)
        return False

    base_url = creds.get("api_base_url", DEFAULT_API_BASE_URL)
    devices = creds.get("devices", {})
    if not devices:
        _LOGGER.error("No devices found in secomat credentials_file %s", credentials_file)
        return False

    session = async_get_clientsession(hass)
    hass.data.setdefault(DOMAIN, {})

    for secomat_id, dev in devices.items():
        token = dev.get("claiming_token")
        if not token:
            _LOGGER.warning("Skipping secomat device %s: no claiming_token", secomat_id)
            continue
        client = SecomatClient(session, token, base_url)
        name = dev.get("name") or secomat_id
        coordinator = SecomatCoordinator(hass, client, secomat_id, name, scan_interval)
        await coordinator.async_refresh()
        hass.data[DOMAIN][secomat_id] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            discovery.async_load_platform(hass, platform, DOMAIN, {}, config)
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """No config-entry flow for this integration; present for forward-compat only."""
    return False
