from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = {
        "session_token": entry.data["session_token"],
        "user_id": entry.data["user_id"],
        "api_key": entry.data["api_key"],
        "hubs": None
    }

    
    await hass.config_entries.async_forward_entry_setups(entry, ["alarm_control_panel"])
    

    return True