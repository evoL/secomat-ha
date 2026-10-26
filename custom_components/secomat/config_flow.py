"""Configure a Secomat and validate its Claim Token against the cloud API."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import SecomatApiError, SecomatAuthError, SecomatClient
from .const import CONF_CLAIM_TOKEN, CONF_SECOMAT_ID, DEFAULT_NAME, DOMAIN

# Home Assistant replaced voluptuous with probatio in 2026. Keep older hosts supported.
try:
    import probatio as vol
except ImportError:
    import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

CLAIM_TOKEN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLAIM_TOKEN): CLAIM_TOKEN_SELECTOR,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
    }
)
CLAIM_TOKEN_SCHEMA = vol.Schema({vol.Required(CONF_CLAIM_TOKEN): CLAIM_TOKEN_SELECTOR})


class SecomatConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle UI configuration for one Secomat."""

    VERSION = 1

    async def _async_validate_claim_token(
        self, claim_token: str
    ) -> tuple[str | None, dict[str, str]]:
        """Discover the Secomat ID or return an inline form error."""
        client = SecomatClient(async_get_clientsession(self.hass), claim_token)
        try:
            state = await client.async_get_state()
            serial_number = state.get("payload", {}).get("serial_number")
            if not isinstance(serial_number, str) or not (secomat_id := serial_number.strip()):
                return None, {"base": "cannot_connect"}
        except SecomatAuthError:
            return None, {"base": "invalid_auth"}
        except SecomatApiError:
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error validating the Secomat Claim Token")
            return None, {"base": "unknown"}
        return secomat_id, {}

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Add a Secomat from Devices & Services."""
        errors = {}
        if user_input is not None:
            secomat_id, errors = await self._async_validate_claim_token(
                user_input[CONF_CLAIM_TOKEN]
            )
            if not errors:
                await self.async_set_unique_id(secomat_id)
                self._abort_if_unique_id_configured()
                name = user_input.get(CONF_NAME, "").strip() or DEFAULT_NAME
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_SECOMAT_ID: secomat_id,
                        CONF_CLAIM_TOKEN: user_input[CONF_CLAIM_TOKEN],
                        CONF_NAME: name,
                    },
                )
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reconfigure(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Manually replace the Claim Token without changing the Secomat ID."""
        return await self._async_step_claim_token(
            "reconfigure", self._get_reconfigure_entry(), user_input
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start reauthentication when polling rejects the Claim Token."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Replace a rejected Claim Token in-place."""
        return await self._async_step_claim_token(
            "reauth_confirm", self._get_reauth_entry(), user_input
        )

    async def _async_step_claim_token(
        self, step_id: str, entry: ConfigEntry, user_input: dict | None
    ) -> ConfigFlowResult:
        """Validate a replacement Claim Token, update the entry, and reload it."""
        errors = {}
        if user_input is not None:
            secomat_id, errors = await self._async_validate_claim_token(
                user_input[CONF_CLAIM_TOKEN]
            )
            if not errors and secomat_id != (entry.unique_id or entry.data[CONF_SECOMAT_ID]):
                errors = {"base": "wrong_secomat"}
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_CLAIM_TOKEN: user_input[CONF_CLAIM_TOKEN]}
                )
        return self.async_show_form(
            step_id=step_id, data_schema=CLAIM_TOKEN_SCHEMA, errors=errors
        )
