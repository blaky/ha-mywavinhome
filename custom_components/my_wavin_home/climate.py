"""Climate platform for HVAC System."""
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
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
    """Set up HVAC climate entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Create a climate entity for each room
    entities = []
    if coordinator.data:
        for room_id, room_data in coordinator.data.items():
            entities.append(HVACClimate(coordinator, entry, room_id, room_data))
    
    async_add_entities(entities)

class HVACClimate(CoordinatorEntity, ClimateEntity):
    """Climate entity for a room."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    # Removing TARGET_TEMPERATURE feature for now since API doesn't support setting it yet
    _attr_supported_features = 0  # Read-only for now
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 5.0
    _attr_max_temp = 35.0

    def __init__(self, coordinator, entry, room_id, room_data):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self.room_id = room_id
        self._attr_unique_id = f"{entry.entry_id}_{room_id}_climate"
        # Use room_id as the name since that's the actual room name from the API
        self._attr_name = f"{room_id} Climate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{room_id}")},
            "name": room_data.get("name"),
            "manufacturer": "Wavin",
            "model": f"WTC-NET1 - {room_id}",
        }


    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data and self.room_id in self.coordinator.data:
            return self.coordinator.data[self.room_id].get("temperature")
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if self.coordinator.data and self.room_id in self.coordinator.data:
            return self.coordinator.data[self.room_id].get("target_temperature")
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        if self.coordinator.data and self.room_id in self.coordinator.data:
            room_data = self.coordinator.data[self.room_id]
            # For now, always return HEAT mode when temperature data is available
            # You can extend this logic based on your API's response structure
            if room_data.get("temperature") is not None:
                return HVACMode.HEAT
        return HVACMode.OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        # TODO: Implement API call to set target temperature
        # This requires extending your API client with a set_target_temperature method
        _LOGGER.warning(
            "Setting temperature not yet implemented. "
            "Room: %s, Target: %s°C", 
            self.room_id, 
            temperature
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        # TODO: Implement API call to set HVAC mode
        # This requires extending your API client with room control methods
        _LOGGER.warning(
            "Setting HVAC mode not yet implemented. "
            "Room: %s, Mode: %s", 
            self.room_id, 
            hvac_mode
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.room_id in self.coordinator.data
        )