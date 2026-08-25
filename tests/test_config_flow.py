"""Test the Simple Integration config flow."""

from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.watersmart.client import AuthenticationError
from custom_components.watersmart.const import DOMAIN

from .conftest import MockConfigEntry


async def test_successful_flow(hass: HomeAssistant, mock_watersmart_client):
    """Test we get the form."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "custom_components.watersmart.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        configured_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "test",
                "username": "test@home-assistant.io",
                "password": "Passw0rd",
            },
        )

    assert configured_result["type"] == "create_entry"
    assert configured_result["title"] == "test (test@home-assistant.io)"
    assert configured_result["data"] == {
        "host": "test",
        "username": "test@home-assistant.io",
        "password": "Passw0rd",
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_errors"),
    [
        (None, {"base": "invalid_auth"}),
        (TimeoutError("timeout"), {"base": "cannot_connect"}),
        (
            AuthenticationError(["invalid credentials"]),
            {
                "base": "invalid_auth",
            },
        ),
        (
            Exception("unknown error"),
            {
                "base": "unknown",
            },
        ),
    ],
    ids=["no_account_number", "client_timeout", "auth_error", "unknown_error"],
)
async def test_error(
    hass: HomeAssistant,
    mock_watersmart_client,
    side_effect,
    expected_errors,
):
    """Test we get the form."""

    mock_watersmart_client.async_get_account_number.return_value = None
    mock_watersmart_client.async_get_account_number.side_effect = side_effect

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "custom_components.watersmart.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        configured_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "test",
                "username": "test@home-assistant.io",
                "password": "Passw0rd",
            },
        )

    assert "title" not in configured_result
    assert "data" not in configured_result

    assert configured_result["type"] == "form"
    assert configured_result["errors"] == expected_errors
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 0


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and set up a config entry for flow tests."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test",
        data={
            "host": "test",
            "username": "test@home-assistant.io",
            "password": "Passw0rd",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_reauth_flow(hass: HomeAssistant, mock_watersmart_client):
    """Test the reauth flow updates the stored password."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = await _setup_entry(hass)

    entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {"password": "NewPassw0rd"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "NewPassw0rd"  # noqa: S105


async def test_reauth_flow_invalid_password(
    hass: HomeAssistant, mock_watersmart_client
):
    """Test the reauth flow shows an error for a bad password."""

    mock_watersmart_client.async_get_account_number.side_effect = AuthenticationError(
        ["invalid credentials"]
    )

    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = await _setup_entry(hass)

    entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1

    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {"password": "WrongPassword"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data["password"] == "Passw0rd"  # noqa: S105


async def test_reconfigure_flow(hass: HomeAssistant, mock_watersmart_client):
    """Test the reconfigure flow updates the entry."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = await _setup_entry(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "newhost",
            "username": "new@home-assistant.io",
            "password": "NewPassw0rd",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        "host": "newhost",
        "username": "new@home-assistant.io",
        "password": "NewPassw0rd",
    }


async def test_reconfigure_flow_invalid_password(
    hass: HomeAssistant, mock_watersmart_client
):
    """Test the reconfigure flow shows an error for bad credentials."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = await _setup_entry(hass)
    mock_watersmart_client.async_get_account_number.side_effect = AuthenticationError(
        ["invalid credentials"]
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "test",
            "username": "test@home-assistant.io",
            "password": "WrongPassword",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data["password"] == "Passw0rd"  # noqa: S105
