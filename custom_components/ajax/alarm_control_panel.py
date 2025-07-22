from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelEntityFeature
from homeassistant.const import STATE_UNKNOWN


import logging
from .api import AjaxAPI

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    data = hass.data[DOMAIN][config_entry.entry_id]
    api = AjaxAPI(data)
    hubs = data.get("hubs", [])
    # try:
    #     hubs = await api.get_hub_id()

    #     hass.data[DOMAIN][config_entry.entry_id]["hubs"] = hubs
    #     _LOGGER.info("Received hubs: %s", hubs)

    # except Exception as e:
    #     _LOGGER.error("Failed to fetch hubs: %s", e)
        
    entities = []
    for hub in hubs:
        hub_id = hub["hubId"]
        entities.append(AjaxAlarmPanel(api, hub_id))

    async_add_entities(entities)


   # await hass.config_entries.async_forward_entry_setups(config_entry, ["sensor"])


class AjaxAlarmPanel(AlarmControlPanelEntity):
    def __init__(self, api, hub_id):
        self._attr_name = "Ajax Hub"
        self._attr_state = STATE_UNKNOWN  
        self.api = api
        self._attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
        self.hub_id = hub_id

    def map_ajax_state_to_ha(self,state):
        if state == "DISARMED_NIGHT_MODE_OFF":
            return "disarmed"
        if state == "ARMED_NIGHT_MODE_OFF":
            return "armed_away"
    
        return STATE_UNKNOWN

    async def async_added_to_hass(self):
        await self.async_update()  

    async def async_update(self):
        hub_info = await self.api.get_hub_info(self.hub_id)
        raw_state = hub_info["state"]
        self._attr_state = self.map_ajax_state_to_ha(raw_state)
        self._attr_name = hub_info["name"] + " " + f"({hub_info["id"]})"

    async def async_alarm_disarm(self, code=None):
        _LOGGER.info("Disarm called")
        result = await self.api.disarm_hub(self.hub_id)
        _LOGGER.info("Disarm result: %s", result)
        await self.async_update()
        self.async_write_ha_state()

    async def async_alarm_arm_away(self, code=None):
        _LOGGER.info("Arm away called")
        result = await self.api.arm_hub(self.hub_id)
        _LOGGER.info("Arm result: %s", result)
        await self.async_update()
        self.async_write_ha_state()

    @property
    def code_format(self):
        """Return None if no code is required."""
        return None

    @property
    def code_arm_required(self):
        """Return False to indicate that arming does not require a code."""
        return False

    @property
    def code_disarm_required(self):
        """Return False to indicate that disarming does not require a code."""
        return False