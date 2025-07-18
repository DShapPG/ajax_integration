import aiohttp
import logging
_LOGGER = logging.getLogger(__name__)
class AjaxAPI:
    base_url = "https://api.ajax.systems/api"

    def __init__(self, data):
        self.session_token = data["session_token"]
        self.api_key = data["api_key"]
        self.user_id = data["user_id"]
        self.hub_id = data["hubs"]

        self.headers = {
                "X-Session-Token": self.session_token,
                "X-Api-Key": self.api_key
            }

    async def get_hub_id(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/user/{self.user_id}/hubs",
                headers=self.headers
            ) as resp:
                hubs = await resp.json()
        hub_id = hubs[0]["hubId"]
        self.hub_id = hub_id
        _LOGGER.info("HUBID: %s", hub_id)
        return hub_id
        

    
    async def get_hub_state(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/user/{self.user_id}/hubs/{self.hub_id}",
                headers=self.headers
            ) as resp:
                info  = await resp.json()
        _LOGGER.info("DATA_HUB_STATE: %s", self.hub_id)
        if "state" not in info:
            _LOGGER.error("No 'state' in hub info response: %s", info)
            return None
        return info["state"]

    async def arm_hub(self):
        url = f"{self.base_url}/user/{self.user_id}/hubs/{self.hub_id}/commands/arming"
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

    async def disarm_hub(self):
        url = f"{self.base_url}/user/{self.user_id}/hubs/{self.hub_id}/commands/arming"
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