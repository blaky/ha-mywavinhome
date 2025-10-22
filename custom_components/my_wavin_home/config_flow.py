"""Config flow for HVAC System integration."""
import logging
import voluptuous as vol
from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .api import HVACApiClient, AuthenticationError, ConnectionError as APIConnectionError

_LOGGER = logging.getLogger(__name__)

DOMAIN = "my_wavin_home"

class HVACConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for My Wavin Home."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Test the credentials
                api_client = HVACApiClient(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    self.hass
                )
                await api_client.authenticate()
                
                # Create the entry
                return self.async_create_entry(
                    title=f"HVAC ({user_input[CONF_USERNAME]})",
                    data=user_input
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except APIConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.exception("Unexpected exception: %s", e)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }),
            errors=errors,
        )
