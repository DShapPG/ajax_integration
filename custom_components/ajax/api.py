import aiohttp
import logging
import time
import functools
from aiohttp import ClientResponseError

_LOGGER = logging.getLogger(__name__)

class AjaxAPIError(Exception):
    pass

def handle_unauthorized(func):
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except ClientResponseError as e:
            if e.status == 401:
                _LOGGER.warning("🔒 Unauthorized! Trying to refresh token...")
                try:
                    await self.update_refresh_token()
                    return await func(self, *args, **kwargs)
                except Exception as refresh_error:
                    _LOGGER.error("🔁 Token refresh failed: %s", refresh_error)
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

    def is_token_expired(self):
        # Token expires after 14 minutes
        return time.time() - self.session_created_at > 14 * 60

    async def ensure_token_valid(self):
        if self.is_token_expired():
            _LOGGER.debug("Token expired, refreshing...")
            await self.update_refresh_token()

    async def update_refresh_token(self):
        _LOGGER.debug("Refreshing token")
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
                    raise AjaxAPIError(f"Failed refresh token: HTTP {resp.status}")
                data = await resp.json()

        if ("sessionToken" not in data or
            "refreshToken" not in data or
            data.get("message") == "User is not authorized"):
            _LOGGER.error(f"Failed to refresh token! Response: {data}")
            raise AjaxAPIError(f"Failed to refresh token: {data}")

        self.session_token = data["sessionToken"]
        self.refresh_token = data["refreshToken"]
        self.headers["X-Session-Token"] = self.session_token
        self.session_created_at = time.time()

        # Save new tokens to config entry
        if self.hass and self.entry:
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={
                    **self.entry.data,
                    "session_token": self.session_token,
                    "refresh_token": self.refresh_token,
                    "token_created_at": self.session_created_at,
                }
            )
        # Also update runtime data cache
        if hasattr(self.hass, "data") and hasattr(self.entry, "domain"):
            self.hass.data[self.entry.domain][self.entry.entry_id].update({
                "session_token": self.session_token,
                "refresh_token": self.refresh_token,
                "token_created_at": self.session_created_at,
            })

    @handle_unauthorized
    async def get_hubs(self):
        await self.ensure_token_valid()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/user/{self.user_id}/hubs",
                headers=self.headers
            ) as resp:
                data = await resp.json()
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
