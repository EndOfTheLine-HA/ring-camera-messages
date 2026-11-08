"""Buttons for saved Ring camera messages."""

from homeassistant.components.button import ButtonEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        MessageButton(entry.runtime_data, entry.entry_id, preset)
        for preset in entry.options.get("presets", [])
    )


class MessageButton(ButtonEntity):
    _attr_icon = "mdi:bullhorn-outline"

    def __init__(self, bridge, entry_id, preset):
        self.bridge = bridge
        self.preset = preset
        self._attr_name = preset["name"]
        self._attr_unique_id = f"{entry_id}_{preset['id']}"

    async def async_press(self):
        await self.bridge.speak(
            self.preset["camera"],
            self.preset["message"],
            cache=True,
            gain_db=self.preset.get("gain_db", 0),
        )
