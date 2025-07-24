from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging
from .device_mapper import map_ajax_device
from .const import DOMAIN
from .api import AjaxAPI

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "session_token": entry.data["session_token"],
        "refresh_token": entry.data["refresh_token"],
        "user_id": entry.data["user_id"],
        "api_key": entry.data["api_key"],
        "hubs": None,
        "devices": None,  # или []
    }
    api = AjaxAPI(hass.data[DOMAIN][entry.entry_id])
    try:
        hubs = await api.get_hubs()

        hass.data[DOMAIN][entry.entry_id]["hubs"] = hubs
        _LOGGER.info("Received hubs: %s", hubs)

    except Exception as e:
        _LOGGER.error("Failed to fetch hubs: %s", e)

    
    devices_by_hub = {}
    for hub in hubs:
        hub_id = hub["hubId"]
        _LOGGER.error("HUB_ID: %s",  hub_id)
        devices = await api.get_hub_devices(hub_id)
        devices_by_hub[hub_id] = devices


    # save devices hass.data
    hass.data[DOMAIN][entry.entry_id]["devices_by_hub"] = devices_by_hub

    # setting platforms
    platforms = set()

    for device in devices:
        mappings = map_ajax_device(device)
        for platform, _ in mappings:
            platforms.add(platform)

    platforms.add("alarm_control_panel")
    await hass.config_entries.async_forward_entry_setups(entry, list(platforms))

    return True