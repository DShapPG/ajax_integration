from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging
import time
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from .const import DOMAIN
from .api import AjaxAPI
from .device_mapper import map_ajax_device
from homeassistant.core import CoreState

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.error(f"async_setup_entry started, hass.state={hass.state}")
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

    async def do_setup():
        _LOGGER.warning("DO SETUP")
            # Create API instance
        api = AjaxAPI(entry.data, hass, entry)
        hass.data[DOMAIN][entry.entry_id]["api"] = api

        # Check if refresh token might be expired (older than 7 days)
        token_age = time.time() - entry.data.get("token_created_at", 0)
        if token_age > 7 * 24 * 60 * 60:  # 7 days in seconds
            _LOGGER.warning("Refresh token is %d days old, triggering reauth flow", token_age // (24 * 60 * 60))
            # Trigger reauth flow automatically
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "reauth", "entry_id": entry.entry_id},
                    data=entry.data,
                )
            )
            return False  # Don't continue setup, wait for reauth
        elif token_age > 6 * 24 * 60 * 60:  # 6 days in seconds
            _LOGGER.warning("Refresh token is %d days old, may need re-authentication soon", token_age // (24 * 60 * 60))

        _LOGGER.error("HASS STARTED")
        _LOGGER.error(f"INIT HASS: {hass!r} ({bool(hass)}) ENTRY: {entry!r} ({bool(entry)})")
        # Only refresh token if session token is expired or close to expiring
        if api.is_token_expired():
            try:
                await api.update_refresh_token()
            except Exception as e:
                _LOGGER.error("Failed to refresh token during setup: %s", e)
                return False
        try:
            # Get list of hubs
            hubs = await api.get_hubs()
            if not hubs or not isinstance(hubs, list):
                _LOGGER.error("No hubs returned from API or invalid format. Got: %s", type(hubs))
                return False

            hass.data[DOMAIN][entry.entry_id]["hubs"] = hubs
            _LOGGER.error("Received %d hubs", len(hubs))

            # Get devices per hub
            devices_by_hub = {}
            all_devices = []

            for hub in hubs:
                hub_id = hub["hubId"]
                _LOGGER.warning("Fetching devices for hub: %s", hub_id)
                devices = await api.get_hub_devices(hub_id)
                devices_by_hub[hub_id] = devices
                all_devices.extend(devices)

            # Store devices in memory
            hass.data[DOMAIN][entry.entry_id]["devices_by_hub"] = devices_by_hub

        except Exception as e:
            _LOGGER.exception("Failed to fetch hubs or devices: %s", e)
            return True

        # Determine required platforms based on device types
        platforms = set()
        for device in all_devices:
            mappings = map_ajax_device(device)
            for platform, _ in mappings:
                platforms.add(platform)

        # Ensure alarm panel is always registered
        platforms.add("alarm_control_panel")
        

        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                "platforms": list(platforms)  # save platforms to memory
            }
        )
        # Forward setup to all required platforms
        await hass.config_entries.async_forward_entry_setups(entry, list(platforms))
        hass.data[DOMAIN][entry.entry_id]["loaded_platforms"] = list(platforms)
        
        return True
    
    

    _LOGGER.error(f"HASS STATE BEFORE:{hass.state}")   
    if hass.state == CoreState.running:
        _LOGGER.error("HASS already running, run setup now")
        setup_result = await do_setup()
    else:
        _LOGGER.error("Waiting for HASS to start...")
        async def _handle_started(event):
            await do_setup()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _handle_started)
        setup_result = True
    
    return setup_result

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    

    # Remove platforms (sensor, binary_sensor, etc.)
    platforms = entry.data.get("platforms", [])
    _LOGGER.error(f"PLATFORMS:{platforms}")
    loaded_platforms = hass.data[DOMAIN][entry.entry_id].get("loaded_platforms", [])
    _LOGGER.error(f"Loaded platforms to unload: {loaded_platforms}")

    if platforms:
        _LOGGER.error("PLATFORMS TRUE")
        unload_ok = await hass.config_entries.async_unload_platforms(entry, loaded_platforms)
        _LOGGER.error("PLATFORMS FALSE")
        unload_ok = True

    _LOGGER.error(f"UNLOAD:{unload_ok}")
    return bool(unload_ok)