"""Test services for WaterSmart integration."""

import re
from typing import cast

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from custom_components.watersmart.const import DOMAIN
from custom_components.watersmart.services import (
    ATTR_CONFIG_ENTRY,
    HOURLY_HISTORY_SERVICE_NAME,
)

from .conftest import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
def test_has_services(
    hass: HomeAssistant,
) -> None:
    """Test the existence of the WaterSmart Service."""
    assert hass.services.has_service(DOMAIN, HOURLY_HISTORY_SERVICE_NAME)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("service", [HOURLY_HISTORY_SERVICE_NAME])
@pytest.mark.parametrize(
    ("cached", "update_call_count"),
    [({"cached": False}, 2), ({"cached": True}, 1), ({}, 1)],
)
@pytest.mark.parametrize(
    "start",
    [
        {"start": "2024-06-19T19:30:00-07:00"},
        {"start": "2024-06-19 19:30:00"},
        {"start": "2024-06-20T02:30:00.000Z"},
        {"start": 1718850600},
        {},
    ],
)
@pytest.mark.parametrize(
    "end",
    [
        {"end": "2024-06-19T21:30:00-07:00"},
        {"end": "2024-06-19 21:30:00"},
        {"end": "2024-06-20T04:30:00.000Z"},
        {"end": 1718857800},
        {},
    ],
)
async def test_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_watersmart_client,
    snapshot: SnapshotAssertion,
    service: str,
    cached: dict[str, bool],
    update_call_count: int,
    start: dict[str, str],
    end: dict[str, str],
):
    entry = {ATTR_CONFIG_ENTRY: mock_config_entry.entry_id}

    data = entry | cached | start | end

    assert snapshot == await hass.services.async_call(
        DOMAIN,
        service,
        data,
        blocking=True,
        return_response=True,
    )

    assert mock_watersmart_client.async_get_hourly_data.call_count == update_call_count


@pytest.mark.usefixtures("init_integration")
async def test_service_includes_leak_gallons(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_watersmart_client,
) -> None:
    """Service responses include utility leak data; entity attributes do not."""
    mock_watersmart_client.async_get_hourly_data.return_value = [
        {
            "read_datetime": 1718823600,
            "gallons": 7.48,
            "leak_gallons": 0,
            "flags": None,
        },
        {
            "read_datetime": 1718827200,
            "gallons": 3.0,
            "leak_gallons": 40,
            "flags": None,
        },
        {
            "read_datetime": 1718830800,
            "gallons": None,
            "leak_gallons": None,
            "flags": None,
        },
    ]

    response = await hass.services.async_call(
        DOMAIN,
        HOURLY_HISTORY_SERVICE_NAME,
        {ATTR_CONFIG_ENTRY: mock_config_entry.entry_id, "cached": False},
        blocking=True,
        return_response=True,
    )

    assert response == {
        "history": [
            {"start": "2024-06-19T19:00:00-07:00", "gallons": 7.48, "leak_gallons": 0},
            {"start": "2024-06-19T20:00:00-07:00", "gallons": 3.0, "leak_gallons": 40},
            {"start": "2024-06-19T21:00:00-07:00", "gallons": 0, "leak_gallons": 0},
        ]
    }

    states_with_related = [
        state
        for state in hass.states.async_all("sensor")
        if "related" in state.attributes
    ]
    assert states_with_related, "expected a sensor exposing related records"
    assert "leak_gallons" not in states_with_related[0].attributes["related"][0]


@pytest.fixture
def config_entry_data(
    mock_config_entry: MockConfigEntry, request: pytest.FixtureRequest
) -> dict[str, str]:
    """Fixture for the config entry."""
    if "config_entry" in request.param and request.param["config_entry"] is True:
        return {"config_entry": mock_config_entry.entry_id}

    return cast("dict[str, str]", request.param)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("service", [HOURLY_HISTORY_SERVICE_NAME])
@pytest.mark.parametrize(
    ("config_entry_data", "service_data", "error", "error_message"),
    [
        ({}, {}, vol.er.Error, "required key not provided .+"),
        (
            {"config_entry": True},
            {"cached": "incorrect cache value"},
            vol.er.Error,
            "expected bool for dictionary value .+",
        ),
        (
            {"config_entry": "incorrect entry"},
            {},
            ServiceValidationError,
            "Invalid config entry.+",
        ),
        (
            {"config_entry": True},
            {
                "start": "incorrect date",
            },
            ServiceValidationError,
            "Invalid date provided. Got incorrect date",
        ),
        (
            {"config_entry": True},
            {
                "end": "incorrect date",
            },
            ServiceValidationError,
            "Invalid date provided. Got incorrect date",
        ),
    ],
    indirect=["config_entry_data"],
)
async def test_service_validation(
    hass: HomeAssistant,
    service: str,
    config_entry_data: dict[str, str],
    service_data: dict[str, str],
    error: type[Exception],
    error_message: str,
) -> None:
    """Test the WaterSmart Service validation."""

    with pytest.raises(error) as exc:
        await hass.services.async_call(
            DOMAIN,
            service,
            config_entry_data | service_data,
            blocking=True,
            return_response=True,
        )
    assert re.match(error_message, str(exc.value))


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("service", [HOURLY_HISTORY_SERVICE_NAME])
async def test_service_called_with_unloaded_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test service calls with unloaded config entry."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    data = {"config_entry": mock_config_entry.entry_id}

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            service,
            data,
            blocking=True,
            return_response=True,
        )
