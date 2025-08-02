import aiohttp
import logging
import time
import functools
from aiohttp import ClientResponseError
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState

_LOGGER = logging.getLogger(__name__)

class AjaxAPIError(Exception):
    """Exception raised for Ajax API errors."""
    pass

def handle_unauthorized(func):
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except ClientResponseError as e:
            if e.status == 401:
                _LOGGER.warning("Unauthorized! Trying to refresh token...")
                try:
                    await self.update_refresh_token()
                    return await func(self, *args, **kwargs)
                except Exception as refresh_error:
                    _LOGGER.error("Token refresh failed: %s", refresh_error)
                    raise
            raise
    return wrapper

class AjaxAPI:
    base_url = "https://api.ajax.systems/api"

    def __init__(self, data, hass=None, entry=None):
        self.session_token = data["session_token"]
        self.api_key = data["api_key"]
        self.user_id = data["user_id"]
        self.refresh_token = data["refresh_token"]
        self.hass = hass
        self.entry = entry
        self.headers = {
            "X-Session-Token": self.session_token,
            "X-Api-Key": self.api_key
        }
        self.session_created_at = data.get("token_created_at", time.time())
        self._reauth_in_progress = False

    def is_token_expired(self):
        # Token expires after 14 minutes
        return time.time() - self.session_created_at > 14 * 60
    
    def is_refresh_token_old(self):
        # Refresh token expires after 7 days
        token_created_at = self.entry.data.get("token_created_at", 0) if self.entry else 0
        return time.time() - token_created_at > 7 * 24 * 60 * 60

    async def ensure_token_valid(self):
        _LOGGER.error("Token is valid check")
        if self.is_token_expired():
            _LOGGER.error("Token expired, refreshing...")
            await self.update_refresh_token()


    async def update_refresh_token(self):
        _LOGGER.error("Refreshing token")
        _LOGGER.error(f"{self.hass.state}")
        # if self.hass.state != "RUNNING":
        #     _LOGGER.warning("HA not running yet, skipping token refresh")
        #     return
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/refresh",
                json={
                    "userId": self.user_id,
                    "refreshToken": self.refresh_token
                },
                headers=self.headers
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.error(f"Failed refresh token: HTTP {resp.status} - {text}")
                    # If HTTP 401, trigger reauth flow (only once)
                    if resp.status == 401 and hasattr(self, 'hass') and self.hass and hasattr(self, 'entry') and self.entry:
                        if not self._reauth_in_progress:
                           await self._create_reauth_notification()
                    raise AjaxAPIError(f"Failed refresh token: HTTP {resp.status}")
                data = await resp.json()

        if ("sessionToken" not in data or
            "refreshToken" not in data or
            data.get("message") == "User is not authorized"):
            _LOGGER.error(f"Failed to refresh token! Response: {data}")
            # Check if refresh token is expired (older than 7 days)
            if hasattr(self, 'hass') and self.hass and hasattr(self, 'entry') and self.entry:
                if not self._reauth_in_progress:
                   await self._create_reauth_notification()
            raise AjaxAPIError(f"Refresh token expired or invalid. Please re-authenticate: {data}")

        self.session_token = data["sessionToken"]
        self.refresh_token = data["refreshToken"]
        self.headers["X-Session-Token"] = self.session_token
        self.session_created_at = time.time()
        # Reset reauth flag on successful refresh
        _LOGGER.error("BEFORE REAUTH FLAG")
        self._reauth_in_progress = False
        _LOGGER.error("REAUTH FLAG PASSED")

        # Save new tokens to config entry
        _LOGGER.error(f"HASS: {self.hass!r} ({bool(self.hass)}) ENTRY: {self.entry!r} ({bool(self.entry)})")
        if self.hass and self.entry:
            _LOGGER.error("TRUE")
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={
                    **self.entry.data,
                    "session_token": self.session_token,
                    "refresh_token": self.refresh_token,
                    "token_created_at": self.session_created_at,
                }
            )
            _LOGGER.error("Entry updated with new tokens")
            return True
        # Also update runtime data cache
        if hasattr(self.hass, "data") and hasattr(self.entry, "domain"):
            self.hass.data[self.entry.domain][self.entry.entry_id].update({
                "session_token": self.session_token,
                "refresh_token": self.refresh_token,
                "token_created_at": self.session_created_at,
            })
            _LOGGER.error("Hass updated with new tokens")
            return True
        

    @handle_unauthorized
    async def get_hubs(self):
        await self.ensure_token_valid()
        _LOGGER.error("HEADERS: %s", self.headers)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/user/{self.user_id}/hubs",
                headers=self.headers
            ) as resp:
                data = await resp.json()
                
        
        # Check if response contains error
        if isinstance(data, dict) and data.get("message") == "User is not authorized":
            _LOGGER.warning("User is not authorized in get_hubs response: %s", data)

            try:
                # Try to refresh the token
                refreshed = await self.update_refresh_token()
                _LOGGER.error(f"REFRESHED:{refreshed}")
            except Exception as e:
                _LOGGER.error("Token refresh failed: %s", e)
                refreshed = False

            if not refreshed:
                # Create notification if refresh failed and no reauth in progress
                if not self._reauth_in_progress:
                    await self._create_reauth_notification()
                raise AjaxAPIError(f"User is not authorized and token refresh failed: {data}")

            #Retry the request with new token
            return await self.get_hubs()
        
        # Ensure we return a list
        if not isinstance(data, list):
            _LOGGER.error("Expected list of hubs, got: %s", type(data))
            _LOGGER.error("HUBS got: %s", data)
            return []
            
        return data

    @handle_unauthorized
    async def get_hub_info(self, hub_id):
        await self.ensure_token_valid()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/user/{self.user_id}/hubs/{hub_id}",
                headers=self.headers
            ) as resp:
                info = await resp.json()
        if info.get("message") == "User is not authorized":
            _LOGGER.warning("User not authorized in hub_info body, refreshing token...")
            await self.update_refresh_token()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/user/{self.user_id}/hubs/{hub_id}",
                    headers=self.headers
                ) as resp:
                    info = await resp.json()
        if "state" not in info:
            _LOGGER.error("No 'state' in hub info response: %s", info)
            return None
        return info

    @handle_unauthorized
    async def arm_hub(self, hub_id):
        await self.ensure_token_valid()
        url = f"{self.base_url}/user/{self.user_id}/hubs/{hub_id}/commands/arming"
        payload = {
            "command": "ARM",
            "ignoreProblems": True
        }
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=payload, headers=self.headers) as resp:
                if resp.status == 204:
                    _LOGGER.info("Command sent successfully, no content returned.")
                    return None
                else:
                    result = await resp.json()
        _LOGGER.info("Arm hub result: %s", result)
        return result

    @handle_unauthorized
    async def disarm_hub(self, hub_id):
        await self.ensure_token_valid()
        url = f"{self.base_url}/user/{self.user_id}/hubs/{hub_id}/commands/arming"
        payload = {
            "command": "DISARM",
            "ignoreProblems": True
        }
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=payload, headers=self.headers) as resp:
                if resp.status == 204:
                    _LOGGER.info("Command sent successfully, no content returned.")
                    return None
                else:
                    result = await resp.json()
        _LOGGER.info("Disarm hub result: %s", result)
        return result

    @handle_unauthorized
    async def arm_hub_night(self, hub_id):
        await self.ensure_token_valid()
        url = f"{self.base_url}/user/{self.user_id}/hubs/{hub_id}/commands/arming"
        payload = {
            "command": "NIGHT_MODE_ON",
            "ignoreProblems": True
        }
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=payload, headers=self.headers) as resp:
                if resp.status == 204:
                    _LOGGER.info("Night mode command sent successfully, no content returned.")
                    return None
                else:
                    result = await resp.json()
        _LOGGER.info("Arm hub night result: %s", result)
        return result

    @handle_unauthorized
    async def get_hub_devices(self, hub_id):
        await self.ensure_token_valid()
        url = f"{self.base_url}/user/{self.user_id}/hubs/{hub_id}/devices"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status == 204:
                    _LOGGER.info("No content returned for devices.")
                    return None
                else:
                    result = await resp.json()
        return result

    async def _create_reauth_notification(self):
        """Trigger reauth flow for expired refresh token, ensuring HA is fully started first."""
        if not self.hass or not self.entry:
            return

        self._reauth_in_progress = True
        _LOGGER.warning("Ajax refresh token expired, triggering reauth flow")

        async def trigger_reauth():
            await self.hass.config_entries.flow.async_init(
                self.entry.domain,
                context={"source": "reauth", "entry_id": self.entry.entry_id},
                data=self.entry.data,
            )

        if self.hass.state == CoreState.running:
            _LOGGER.error("API STATE TRUE.")
            self.hass.async_create_task(trigger_reauth())
        else:
            _LOGGER.error("API STATE FALSE.")
            # Wait for HASS to fully start before showing UI
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED,
                lambda event: self.hass.async_create_task(trigger_reauth())
            )

        await self.update_refresh_token()

            

    @handle_unauthorized
    async def get_device_info(self, hub_id, device_id):
        await self.ensure_token_valid()
        url = f"{self.base_url}/user/{self.user_id}/hubs/{hub_id}/devices/{device_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status == 204:
                    _LOGGER.info("No content returned for device info.")
                    return None
                else:
                    result = await resp.json()
        return result

