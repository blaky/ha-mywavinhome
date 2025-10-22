"""Sensor platform for HVAC System."""
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HVAC sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Create temperature and humidity sensors for each room
    entities = []
    if coordinator.data:
        for room_id, room_data in coordinator.data.items():
            entities.append(HVACTemperatureSensor(coordinator, entry, room_id, room_data))
            entities.append(HVACHumiditySensor(coordinator, entry, room_id, room_data))
    
    async_add_entities(entities)

class HVACTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Temperature sensor for a room."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, entry, room_id, room_data):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.room_id = room_id
        self._attr_unique_id = f"{entry.entry_id}_{room_id}_temperature"
        # Use room_id as the name since that's the actual room name from the API
        self._attr_name = f"{room_id} Temperature"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{room_id}")},
            "name": room_id,  # room_id is actually the room name
            "manufacturer": "Wavin",
            "model": f"Room Sensor - {room_id}",
        }

    @property
    def native_value(self):
        """Return the temperature."""
        if self.coordinator.data and self.room_id in self.coordinator.data:
            return self.coordinator.data[self.room_id].get("temperature")
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.room_id in self.coordinator.data
        )


class HVACHumiditySensor(CoordinatorEntity, SensorEntity):
    """Humidity sensor for a room."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, entry, room_id, room_data):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.room_id = room_id
        self._attr_unique_id = f"{entry.entry_id}_{room_id}_humidity"
        # Use room_id as the name since that's the actual room name from the API
        self._attr_name = f"{room_id} Humidity"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{room_id}")},
            "name": room_id,  # room_id is actually the room name
            "manufacturer": "Wavin",
            "model": f"Room Sensor - {room_id}",
        }

    @property
    def native_value(self):
        """Return the humidity."""
        if self.coordinator.data and self.room_id in self.coordinator.data:
            return self.coordinator.data[self.room_id].get("humidity")
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.room_id in self.coordinator.data
        )