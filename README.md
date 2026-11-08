# Ring Camera Messages

Play text-to-speech messages through Ring camera speakers from Home Assistant.
Save reusable messages as buttons or generate a message in an automation.

## Install

1. Use a Ring-MQTT build with the [speaker request protocol](https://github.com/endoftheline818/ring-mqtt/pull/3). Set `"enable_speaker_requests": true` in its standalone configuration and restart the bridge.
2. Connect Home Assistant and Ring-MQTT to the same MQTT broker. Only trusted publishers should have write access to the bridge's `<ring_topic>/speaker/v1/play` topic. For maximum-length clips the broker must accept an MQTT payload of about 4.36 MB.
3. Add this repository in HACS as a custom repository of type **Integration**, install it and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → Ring Camera Messages**. Select an installed TTS entity and enter the bridge's topic prefix, usually `ring`.
5. Open the integration's **Configure** menu to add, edit or remove messages. Each message has its own text and camera. Add the resulting button entities to a dashboard.

The camera needs Two-Way Talk and enabled Live View. This initial release
supports one bridge per Home Assistant instance. The bridge plays one
clip at a time, with a limit of 17 seconds. Saved presets use Home
Assistant's TTS cache. Dynamic messages are generated on demand.
For quiet presets, edit the message and set a volume boost from 0 to 18 dB.
A limiter caps peaks, so the audible increase can be less than the selected gain.

## Automations

Use the **List cameras** action to find a stable camera ID. Pass it to
**Speak through Ring camera** with plain text or a Home Assistant template.

```yaml
action: ring_camera_messages.speak
data:
  camera: "123456789"
  message: "Thank you for the delivery."
```

See [the Frigate greeting example](examples/frigate-greeting.yaml) for a
face event, explicit name mapping and cooldown. Replace the example
camera names and ID before enabling it. A Frigate face update can be
published more than once and can be below the recognition threshold.

If playback fails, inspect the Home Assistant action trace and Ring-MQTT
logs. A successful action means the Ring playback session ended. Check
speaker volume and audibility at the camera.
