from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN
from .device_mapper import map_ajax_device
from .api import AjaxAPI
import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    devices_by_hub = hass.data[DOMAIN][entry.entry_id]["devices_by_hub"]
    entities = []
    data = hass.data[DOMAIN][entry.entry_id]
    api = AjaxAPI(data, hass, entry)

    for hub_id, devices in devices_by_hub.items():
        for device in devices:
            for platform, meta in map_ajax_device(device):
                if platform != "sensor":
                    continue
                if meta.get("device_class") == "temperature":
                    entity = FireProtectSensor(device, meta, hub_id, api)
                else:
                    entity = AjaxSensor(device, meta, hub_id, api)
                entities.append(entity)

    async_add_entities(entities)


class AjaxSensor(SensorEntity):
    def __init__(self, device, meta, hub_id, api):
        self._device = device
        self.hub_id = hub_id
        self._meta = meta
        self._attr_name = device.get("deviceName") + f" ({device.get('id')})"
        self._attr_unique_id = f"ajax_{device.get('id')}_{meta.get('device_class')}"
        self._attr_device_class = meta.get("device_class")
        self._attr_native_unit_of_measurement = meta.get("unit")
        self.api = api
        self._battery = None
        self._native_value = None

    @property
    def native_value(self):     
        return self._native_value
    @property
    def extra_state_attributes(self):
        return {
            "battery_level": self._battery,
        }

    async def async_update(self):
        device_info = await self.api.get_device_info(self.hub_id, self._device.get('id'))
        self._battery = device_info.get('batteryChargeLevelPercentage')

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"ajax_{self._device.get('id')}_{self._meta.get('device_class')}")},
            "name": self._attr_name,
            "manufacturer": "Ajax",
            "model": self._meta.get("device_class", "Unknown"),
        }
      



class FireProtectSensor(AjaxSensor):
    def __init__(self, device, meta, hub_id, api):
        super().__init__(device, meta, hub_id, api)
        self._temperature = None


    @property
    def native_value(self):
        return self._temperature

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes.copy()
        # attrs.update({
        #     "smoke_alarm": self._smoke_alarm,
        #     "temperature_alarm": self._temperature_alarm,
        # })
        return attrs

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"ajax_{self._device.get('id')}")},
            "name": "Ajax FireProtectPlus",
            "manufacturer": "Ajax",
            "model": "FireProtectPlus",
        }

    async def async_update(self):
        await super().async_update() # updating in parent class
        device_info = await self.api.get_device_info(self.hub_id, self._device.get('id'))
        self._temperature = device_info.get('temperature')

            
            

