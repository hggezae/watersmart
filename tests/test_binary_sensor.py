"""Test WaterSmart binary sensor."""

from homeassistant.core import HomeAssistant
import pytest
from syrupy.assertion import SnapshotAssertion


from .conftest import MockConfigEntry

ENTITY_ID = "binary_sensor.watersmart_test_leak_detected"


@pytest.fixture
def client_leak_flagged(mock_watersmart_client):
    """Utility flags the most recent hour with leak gallons."""
    hourly = mock_watersmart_client.async_get_hourly_data.return_value
    hourly[-1]["leak_gallons"] = 40


@pytest.fixture
def client_continuous_flow(mock_watersmart_client, fixture_loader):
    """Usage runs continuously for at least the leak threshold hours."""
    base = fixture_loader.realtime_api_response_obj["data"]["series"][0]
    mock_watersmart_client.async_get_hourly_data.return_value = [
        {
            "read_datetime": base["read_datetime"] + hour * 3600,
            "gallons": 1.5,
            "leak_gallons": 0,
            "flags": None,
        }
        for hour in range(8)
    ]


@pytest.mark.usefixtures("init_integration")
def test_leak_sensor_off(
    hass: HomeAssistant, mock_watersmart_client, snapshot: SnapshotAssertion
):
    """Test the leak sensor stays off with normal usage."""
    state = hass.states.get(ENTITY_ID)

    assert state is not None
    assert state.state == "off"
    assert snapshot == state


@pytest.mark.usefixtures("client_leak_flagged", "init_integration")
def test_leak_sensor_utility_flagged(
    hass: HomeAssistant, mock_watersmart_client, snapshot: SnapshotAssertion
):
    """Test the leak sensor turns on when the utility flagged hours."""
    state = hass.states.get(ENTITY_ID)

    assert state is not None
    assert state.state == "on"
    assert snapshot == state


@pytest.mark.usefixtures("client_continuous_flow", "init_integration")
def test_leak_sensor_continuous_flow(
    hass: HomeAssistant, mock_watersmart_client, snapshot: SnapshotAssertion
):
    """Test the leak sensor turns on for continuously running usage."""
    state = hass.states.get(ENTITY_ID)

    assert state is not None
    assert state.state == "on"
    assert snapshot == state


@pytest.mark.usefixtures("init_integration")
async def test_leak_sensor_with_no_data(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_watersmart_client
):
    """Test the leak sensor goes unavailable when history fetch yields no records."""

    mock_watersmart_client.async_get_hourly_data.return_value = []

    coordinator = init_integration.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)

    assert state is not None
    assert state.state == "unavailable"
    assert "flagged" not in state.attributes
