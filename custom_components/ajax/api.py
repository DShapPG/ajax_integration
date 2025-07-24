import aiohttp
import logging
import time
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


    def is_token_expired(self):
        return time.time() - self.session_created_at > 14 * 60

    async def ensure_token_valid(self):
        # _LOGGER.error(f"refresh_token checked {self.session_created_at}, time: {time.time()}")
        if self.is_token_expired():
            await self.update_refresh_token()


    async def update_refresh_token(self):
        # _LOGGER.error("refresh_token called")
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

    async def get_hubs(self):
        await self.ensure_token_valid()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/user/{self.user_id}/hubs",
                headers=self.headers
            ) as resp:
                hubs = await resp.json()
        return hubs
        

    
    async def get_hub_info(self, hub_id):
        await self.ensure_token_valid()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/user/{self.user_id}/hubs/{hub_id}",
                headers=self.headers
            ) as resp:
                info  = await resp.json()
        _LOGGER.info("DATA_HUB_STATE: %s", hub_id)
        if "state" not in info:
            _LOGGER.error("No 'state' in hub info response: %s", info)
            return None
        return info


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
