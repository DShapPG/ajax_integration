from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Ajax sensor entity."""
    hub_id = hass.data[DOMAIN][config_entry.entry_id].get("hubs", [])
    if hub_id is None:
        hub_id = []
    sensor = AjaxHubListSensor(hub_id)

    async_add_entities([sensor], update_before_add=True)

class AjaxHubListSensor(SensorEntity):
    """Sensor to show list of Ajax hubs."""

    def __init__(self, hub_list):
        self._attr_name = "Ajax Hubs"
        self._hub_list = hub_list

    @property
    def state(self):
        """Return a string representation of hub names."""
        return ", ".join(str(hub) for hub in self._hub_list)

    @property
    def extra_state_attributes(self):
        """Return full list of hubs as attribute."""
        return {
            "hubs": self._hub_list
        }