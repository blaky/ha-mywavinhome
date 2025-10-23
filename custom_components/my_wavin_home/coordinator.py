"""DataUpdateCoordinator for HVAC System."""
import logging
from datetime import timedelta
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import HVACApiClient, ConnectionError

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=10)

class HVACDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching HVAC data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.api_client = HVACApiClient(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            hass
        )
        
        super().__init__(
            hass,
            _LOGGER,
            name="My Wavin home",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            temperatures = await self.api_client.get_room_temperatures()
            outside_temperature = await self.api_client.get_outside_temperature()
            if outside_temperature is not None:
                temperatures["outside_temperature"] = {
                    "name": "Outside",
                    "temperature": outside_temperature,
                    "humidity": None
                }
            return temperatures
        except ConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_shutdown(self) -> None:
        """Shutdown coordinator."""
        await self.api_client.close()