import aiohttp
import logging
import time
import functools
from aiohttp import ClientResponseError
_LOGGER = logging.getLogger(__name__)
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


    def is_token_expired(self):
        return time.time() - self.session_created_at > 14 * 60

    async def ensure_token_valid(self):
        _LOGGER.error(f"refresh_token checked {self.session_created_at}, time: {time.time()}")
        if self.is_token_expired():
            await self.update_refresh_token()

    async def update_refresh_token(self):
        _LOGGER.error("refresh_token called")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/refresh",
                json={
                    "userId": self.user_id,
                    "refreshToken": self.refresh_token
                    },
                headers=self.headers
            ) as resp:
                data = await resp.json()
        self.session_token = data["sessionToken"]
        self.refresh_token = data["refreshToken"]
        self.headers["X-Session-Token"] = self.session_token
        self.session_created_at = time.time()
        # save new tokens to config_entry
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
                hubs = await resp.json()
        return hubs
        

    @handle_unauthorized
    async def get_hub_info(self, hub_id):
        await self.ensure_token_valid()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/user/{self.user_id}/hubs/{hub_id}",
                headers=self.headers
            ) as resp:
                info  = await resp.json()
        _LOGGER.info("DATA_HUB_STATE: %s", hub_id)
        # Если сервер вернул ошибку авторизации в теле
        if info.get("message") == "User is not authorized":
            _LOGGER.warning("User is not authorized in hub_info body, trying to refresh token...")
            await self.update_refresh_token()
            # Повторяем запрос с новым токеном
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/user/{self.user_id}/hubs/{hub_id}",
                    headers=self.headers
                ) as resp:
                    info  = await resp.json()
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
        _LOGGER.info("ARM/DISARM result: %s", result)
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
                    _LOGGER.info("ARM/DISARM result: %s", result)
        _LOGGER.info("DISARM result: %s", result)
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
        _LOGGER.info("ARM_NIGHT result: %s", result)
        return result

    @handle_unauthorized
    async def get_hub_devices(self, hub_id):
        await self.ensure_token_valid()
        url = f"{self.base_url}/user/{self.user_id}/hubs/{hub_id}/devices"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status == 204:
                    _LOGGER.info("Command sent successfully, no content returned.")
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
                    _LOGGER.info("Command sent successfully, no content returned.")
                    return None  
                else:
                    result = await resp.json()
                    return result


    
  
