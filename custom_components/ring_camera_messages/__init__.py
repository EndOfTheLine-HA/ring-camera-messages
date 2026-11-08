"""Set up Ring Camera Messages."""

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .bridge import DOMAIN, MAX_TEXT, Bridge, discover

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass, config):
    async def speak(call):
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("Configure Ring Camera Messages first")
        await entries[0].runtime_data.speak(call.data["camera"], call.data["message"])

    async def cameras(call):
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("Configure Ring Camera Messages first")
        return {"cameras": await discover(hass, entries[0].data["prefix"])}

    hass.services.async_register(
        DOMAIN,
        "speak",
        speak,
        schema=vol.Schema({
            vol.Required("camera"): cv.string,
            vol.Required("message"): vol.All(cv.string, vol.Length(min=1, max=MAX_TEXT)),
        }),
    )
    hass.services.async_register(
        DOMAIN, "cameras", cameras, supports_response=SupportsResponse.ONLY
    )
    return True


async def async_setup_entry(hass, entry):
    entry.runtime_data = Bridge(hass, entry.data["prefix"], entry.data["engine"])
    entry.async_on_unload(entry.add_update_listener(_reload))
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.BUTTON])
    return True


async def _reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, [Platform.BUTTON])
