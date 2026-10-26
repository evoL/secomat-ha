"""The cloud HTTP boundary distinguishes authentication from availability errors."""

import aiohttp
import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.secomat.api import SecomatApiError, SecomatAuthError, SecomatClient

from .conftest import PLC_URL


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("status", [401, 403, 400, 500, 503])
async def test_http_errors(hass, aioclient_mock, method, status):
    """Only rejected Claim Tokens raise the dedicated authentication exception."""
    aioclient_mock.request(method, PLC_URL, status=status, text="Request rejected")
    client = SecomatClient(async_get_clientsession(hass), "secret-token")

    with pytest.raises(SecomatApiError) as error:
        if method == "get":
            await client.async_get_state()
        else:
            await client.async_send_command("OFF")

    assert type(error.value) is (SecomatAuthError if status in (401, 403) else SecomatApiError)


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("exception", [aiohttp.ClientConnectionError(), TimeoutError()])
async def test_transport_errors(hass, aioclient_mock, method, exception):
    """Connection failures and timeouts remain ordinary API errors."""
    aioclient_mock.request(method, PLC_URL, exc=exception)
    client = SecomatClient(async_get_clientsession(hass), "secret-token")

    with pytest.raises(SecomatApiError) as error:
        if method == "get":
            await client.async_get_state()
        else:
            await client.async_send_command("OFF")

    assert type(error.value) is SecomatApiError
