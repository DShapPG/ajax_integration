from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging
import time

from .const import DOMAIN
from .api import AjaxAPI
from .device_mapper import map_ajax_device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Ensure required fields exist in config entry
    required_fields = ["session_token", "refresh_token", "user_id", "api_key"]
    if not all(entry.data.get(k) for k in required_fields):
        _LOGGER.error("Missing required config entry fields. Setup aborted.")
        return False

    # Initialize domain storage if not already
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "session_token": entry.data["session_token"],
        "refresh_token": entry.data["refresh_token"],
        "token_created_at": entry.data.get("token_created_at", time.time()),
        "user_id": entry.data["user_id"],
        "api_key": entry.data["api_key"],
        "hubs": None,
        "devices": None,
    }

    # Create API instance
    api = AjaxAPI(hass.data[DOMAIN][entry.entry_id], hass, entry)
    hass.data[DOMAIN][entry.entry_id]["api"] = api

    # Refresh token before continuing
    await api.update_refresh_token()

    try:
        # Get list of hubs
        hubs = await api.get_hubs()
        if not hubs:
            _LOGGER.error("No hubs returned from API.")
            return False

        hass.data[DOMAIN][entry.entry_id]["hubs"] = hubs
        _LOGGER.info("Received hubs: %s", hubs)

        # Get devices per hub
        devices_by_hub = {}
        all_devices = []

        for hub in hubs:
            hub_id = hub["hubId"]
            _LOGGER.debug("Fetching devices for hub: %s", hub_id)
            devices = await api.get_hub_devices(hub_id)
            devices_by_hub[hub_id] = devices
            all_devices.extend(devices)

        # Store devices in memory
        hass.data[DOMAIN][entry.entry_id]["devices_by_hub"] = devices_by_hub

    except Exception as e:
        _LOGGER.exception("Failed to fetch hubs or devices: %s", e)
        return False

    # Determine required platforms based on device types
    platforms = set()
    for device in all_devices:
        mappings = map_ajax_device(device)
        for platform, _ in mappings:
            platforms.add(platform)

    # Ensure alarm panel is always registered
    platforms.add("alarm_control_panel")

    # Forward setup to all required platforms
    await hass.config_entries.async_forward_entry_setups(entry, list(platforms))

    return True
