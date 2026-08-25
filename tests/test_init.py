"""Test component setup."""

from unittest.mock import MagicMock, patch

from aiohttp.client_exceptions import ClientConnectorError
from aiohttp.client_reqrep import ConnectionKey
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest

from custom_components.watersmart.client import AuthenticationError
from custom_components.watersmart.const import DOMAIN
from custom_components.watersmart.statistics import statistic_id_for


async def test_async_setup(hass: HomeAssistant):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.mark.asyncio
async def test_remove_entry_clears_statistics(hass: HomeAssistant, init_integration):
    """Removing the config entry clears the external statistics series."""
    entry = init_integration

    mock_recorder = MagicMock()
    with patch(
        "custom_components.watersmart.statistics.get_instance",
        return_value=mock_recorder,
    ):
        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

    mock_recorder.async_clear_statistics.assert_called_once_with(
        [statistic_id_for(entry.entry_id)]
    )


async def test_authentication_failure_starts_reauth(
    hass: HomeAssistant,
    init_integration,
    mock_watersmart_client,
):
    """An authentication failure on refresh starts the reauth flow."""

    mock_watersmart_client.async_get_hourly_data.side_effect = AuthenticationError(
        ["invalid credentials"]
    )

    coordinator = init_integration.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_connection_failure_does_not_start_reauth(
    hass: HomeAssistant,
    init_integration,
    mock_watersmart_client,
):
    """A connection failure fails the update without starting reauth."""

    mock_watersmart_client.async_get_hourly_data.side_effect = ClientConnectorError(
        connection_key=ConnectionKey(
            host="test",
            port=443,
            is_ssl=True,
            ssl=None,
            proxy=None,
            proxy_auth=None,
            proxy_headers_hash=None,
        ),
        os_error=OSError("connection refused"),
    )

    coordinator = init_integration.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []
