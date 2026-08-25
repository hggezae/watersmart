"""Support for WaterSmart binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WaterSmartConfigEntry
from .const import ATTRIBUTION, SensorKey
from .coordinator import CoordinatorData, WaterSmartUpdateCoordinator
from .types import SensorData


@dataclass(frozen=True, kw_only=True)
class WaterSmartBinarySensorDescription(BinarySensorEntityDescription):
    """Class describing WaterSmart binary sensor entities."""

    is_on_fn: Callable[[SensorData], bool]


BINARY_SENSOR_TYPES: tuple[WaterSmartBinarySensorDescription, ...] = (
    WaterSmartBinarySensorDescription(
        key=SensorKey.LEAK_DETECTED,
        is_on_fn=lambda data: cast("bool", data),
        device_class=BinarySensorDeviceClass.MOISTURE,
        translation_key="leak_detected",
    ),
)


async def async_setup_entry(  # noqa: RUF029
    hass: HomeAssistant,  # noqa: ARG001
    entry: WaterSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WaterSmart binary sensor entities based on a config entry."""

    coordinator = entry.runtime_data.coordinator

    entities: list[WaterSmartBinarySensor] = [
        WaterSmartBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_TYPES
    ]

    async_add_entities(entities)


class WaterSmartBinarySensor(
    CoordinatorEntity[WaterSmartUpdateCoordinator], BinarySensorEntity
):
    """Abstract class for a WaterSmart binary sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: WaterSmartBinarySensorDescription

    def __init__(
        self,
        coordinator: WaterSmartUpdateCoordinator,
        description: WaterSmartBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._sensor_data = self._get_sensor_data(coordinator.data, description.key)
        self._attr_unique_id = (
            f"{coordinator.hostname}-{coordinator.username}-{description.key}".lower()
        )
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        """Return true if a leak is detected."""
        return self.entity_description.is_on_fn(self._sensor_data["state"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._sensor_data.get("attrs", {})

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._sensor_data = self._get_sensor_data(
            self.coordinator.data, self.entity_description.key
        )
        super()._handle_coordinator_update()

    @staticmethod
    def _get_sensor_data(
        coordinator_data: CoordinatorData,
        kind: SensorKey,
    ) -> SensorData:
        """Get sensor data.

        Returns:
            The actual sensor data.
        """
        return cast("dict[str, SensorData]", coordinator_data)[kind]
