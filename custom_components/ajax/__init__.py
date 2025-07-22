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


    # Сохраняем устройства в hass.data
    hass.data[DOMAIN][entry.entry_id]["devices_by_hub"] = devices_by_hub

    # Определяем платформы, которые нужно загрузить
    platforms = set()

    for device in devices:
        mappings = map_ajax_device(device)
        for platform, _ in mappings:
            platforms.add(platform)

    # Запускаем нужные платформы
    for platform in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    # creating alarm panels

    hass.async_create_task(
    hass.config_entries.async_forward_entry_setup(entry, "alarm_control_panel")
)

    return True