from homeassistant import config_entries

from homeassistant.core import callback
import voluptuous as vol
import aiohttp
import logging
from typing import Any

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class AjaxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://api.ajax.systems/api/login",
                        json={
                            "login": user_input["login"],
                            "passwordHash": user_input["password"]
                        },
                        headers={"X-Api-Key": user_input["api_key"]},
                    ) as resp:
                        data = await resp.json()

                if resp.status != 200 or "sessionToken" not in data:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=self._get_schema(),
                        errors={"base": "auth_failed"}
                    )

                return self.async_create_entry(
                    title="Ajax Alarm",
                    data={
                        "api_key": user_input["api_key"],
                        "session_token": data["sessionToken"],
                        "user_id": data["userId"],
                        "refresh_token": data["refreshToken"]
                    },
                )

            except Exception as e:
                _LOGGER.exception("Login error: %s", e)
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_schema(),
                    errors={"base": "connection_error"}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema()
        )

    @callback
    def _get_schema(self):
        return vol.Schema({
            vol.Required("login"): str,
            vol.Required("password"): str,
            vol.Required("api_key"): str,
        })
