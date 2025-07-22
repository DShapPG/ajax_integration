import aiohttp
import logging
_LOGGER = logging.getLogger(__name__)
class AjaxAPI:
    base_url = "https://api.ajax.systems/api"

    def __init__(self, data):
        self.session_token = data["session_token"]
        self.api_key = data["api_key"]
        self.user_id = data["user_id"]


        self.headers = {
                "X-Session-Token": self.session_token,
                "X-Api-Key": self.api_key
            }

    async def get_hubs(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/user/{self.user_id}/hubs",
                headers=self.headers
            ) as resp:
                hubs = await resp.json()



        return hubs
        

    
    async def get_hub_info(self, hub_id):
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
        url = f"{self.base_url}/user/{self.user_id}/hubs/{hub_id}/devices"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status == 204:
                    _LOGGER.info("Command sent successfully, no content returned.")
                    return None  
                else:
                    result = await resp.json()
                    return result
