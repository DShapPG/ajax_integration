from homeassistant.components.binary_sensor import BinarySensorEntity
from .const import DOMAIN
from .device_mapper import map_ajax_device


async def async_setup_entry(hass, entry, async_add_entities):
    devices_by_hub = hass.data[DOMAIN][entry.entry_id]["devices_by_hub"]
    entities = []

    for hub_id, devices in devices_by_hub.items():
        for device in devices:
            for platform, meta in map_ajax_device(device):
                if platform != "binary_sensor":
                    continue
                entity = AjaxBinarySensor(device, meta, hub_id)
                entities.append(entity)

    async_add_entities(entities)



class AjaxBinarySensor(BinarySensorEntity):
    def __init__(self, device, meta, hub_id):
        self.hub_id = hub_id
        self._device = device
        self._attr_name = device.get("name")
        self._attr_unique_id = f"ajax_{device.get('id')}_{meta.get('device_class')}"
        self._attr_device_class = meta.get("device_class")

    @property
    def is_on(self):
        return self._device.get("state") == "active"