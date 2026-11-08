"""Home Assistant setup and preset editor."""

from uuid import uuid4

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .bridge import DOMAIN, MAX_TEXT, discover


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        errors = {}
        if user_input:
            prefix = user_input["prefix"].strip().strip("/")
            if not prefix or any(char in prefix for char in "#+\x00"):
                errors["prefix"] = "invalid_prefix"
            else:
                try:
                    await discover(self.hass, prefix)
                except HomeAssistantError:
                    errors["base"] = "bridge_unavailable"
                else:
                    return self.async_create_entry(
                        title="Ring Camera Messages", data={**user_input, "prefix": prefix}
                    )
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema({
                vol.Required("prefix", default="ring"): str,
                vol.Required("engine"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="tts")
                ),
            }),
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return PresetOptions()


class PresetOptions(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        self.presets = {
            preset["id"]: preset
            for preset in self.config_entry.options.get("presets", [])
        }
        choices = ["add"]
        if self.presets:
            choices.extend(["edit", "remove"])
        return self.async_show_menu(step_id="init", menu_options=choices)

    async def async_step_add(self, user_input=None):
        return await self._message_form("add", user_input, {})

    async def async_step_edit(self, user_input=None):
        if user_input:
            self.selected = self.presets[user_input["preset"]]
            return await self.async_step_message()
        return self._choose("edit")

    async def async_step_message(self, user_input=None):
        return await self._message_form("message", user_input, self.selected)

    async def async_step_remove(self, user_input=None):
        if user_input:
            del self.presets[user_input["preset"]]
            return self._save()
        return self._choose("remove")

    def _choose(self, step):
        return self.async_show_form(
            step_id=step,
            data_schema=vol.Schema({
                vol.Required("preset"): vol.In({
                    key: preset["name"] for key, preset in self.presets.items()
                })
            }),
        )

    async def _message_form(self, step, user_input, preset):
        if user_input:
            preset_id = preset.get("id") or uuid4().hex
            self.presets[preset_id] = {**user_input, "id": preset_id}
            return self._save()
        try:
            cameras = await discover(self.hass, self.config_entry.data["prefix"])
        except HomeAssistantError:
            return self.async_abort(reason="bridge_unavailable")
        schema = vol.Schema({
            vol.Required("name"): vol.All(str, vol.Length(min=1, max=80)),
            vol.Required("camera"): vol.In(cameras),
            vol.Required("message"): vol.All(str, vol.Length(min=1, max=MAX_TEXT)),
        })
        return self.async_show_form(
            step_id=step,
            data_schema=self.add_suggested_values_to_schema(schema, preset),
        )

    def _save(self):
        return self.async_create_entry(data={"presets": list(self.presets.values())})
