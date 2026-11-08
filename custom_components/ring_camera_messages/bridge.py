"""Render speech in Home Assistant and send it to Ring-MQTT."""

import asyncio
import base64
import io
import json
import wave
from uuid import uuid4

from homeassistant.components import mqtt, tts
from homeassistant.exceptions import HomeAssistantError

DOMAIN = "ring_camera_messages"
MAX_TEXT = 240
MAX_FRAMES = 17 * 48000


def stereo_wave(audio: bytes) -> bytes:
    """Write canonical PCM with identical full-level channels."""
    output = io.BytesIO()
    try:
        with wave.open(io.BytesIO(audio), "rb") as source:
            if (
                source.getnchannels() != 1
                or source.getsampwidth() != 2
                or source.getframerate() != 48000
                or not 0 < source.getnframes() <= MAX_FRAMES
            ):
                raise HomeAssistantError("Expected mono 48 kHz PCM, up to 17 seconds")
            frames = source.readframes(source.getnframes())
            if len(frames) != source.getnframes() * 2:
                raise HomeAssistantError("Incomplete speech audio")
    except (EOFError, wave.Error) as err:
        raise HomeAssistantError("Could not read the TTS audio as WAV") from err

    stereo = bytearray(len(frames) * 2)
    stereo[0::4] = stereo[2::4] = frames[0::2]
    stereo[1::4] = stereo[3::4] = frames[1::2]
    with wave.open(output, "wb") as target:
        target.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
        target.writeframes(stereo)
    return output.getvalue()


async def request(hass, prefix, operation, data):
    """Exchange a correlated request with the bridge."""
    request_id = uuid4().hex
    future = hass.loop.create_future()

    def on_result(message):
        if future.done() or message.retain:
            return
        try:
            result = json.loads(message.payload)
        except (ValueError, TypeError):
            return
        if isinstance(result, dict) and result.get("status") != "accepted":
            future.set_result(result)

    topic = f"{prefix}/speaker/v1"
    unsubscribe = await mqtt.async_subscribe(
        hass, f"{topic}/result/{request_id}", on_result, qos=1
    )
    try:
        async with asyncio.timeout(8 if operation == "discover" else 40):
            await mqtt.async_publish(
                hass,
                f"{topic}/{operation}",
                json.dumps({"id": request_id, **data}),
                qos=1,
                retain=False,
            )
            return await future
    except TimeoutError as err:
        raise HomeAssistantError("Ring-MQTT did not reply. Check the bridge and MQTT.") from err
    finally:
        unsubscribe()


async def discover(hass, prefix):
    """Read camera IDs and labels."""
    result = await request(hass, prefix, "discover", {})
    cameras = {
        camera["id"]: f"{camera['name']} ({camera['id']})"
        for camera in result.get("cameras", [])
        if isinstance(camera, dict)
        and isinstance(camera.get("id"), str)
        and isinstance(camera.get("name"), str)
    }
    if not cameras:
        raise HomeAssistantError("Ring-MQTT has no cameras available for playback")
    return cameras


class Bridge:
    """Play one Home Assistant message through Ring-MQTT."""

    def __init__(self, hass, prefix, engine):
        self.hass = hass
        self.prefix = prefix
        self.engine = engine

    async def speak(self, camera, text, *, cache=False):
        text = text.strip()
        if not 1 <= len(text) <= MAX_TEXT:
            raise HomeAssistantError(f"Message must be 1 to {MAX_TEXT} characters")
        media_id = tts.generate_media_source_id(
            self.hass,
            text,
            engine=self.engine,
            cache=cache,
            options={
                "preferred_format": "wav",
                "preferred_sample_rate": 48000,
                "preferred_sample_channels": 1,
                "preferred_sample_bytes": 2,
            },
        )
        try:
            async with asyncio.timeout(30):
                _, audio = await tts.async_get_media_source_audio(self.hass, media_id)
        except (TimeoutError, ValueError) as err:
            raise HomeAssistantError("Could not generate the speech audio") from err
        encoded = await self.hass.async_add_executor_job(
            lambda: base64.b64encode(stereo_wave(audio)).decode("ascii")
        )
        result = await request(
            self.hass, self.prefix, "play", {"camera": camera, "audio": encoded}
        )
        if result.get("status") == "busy":
            raise HomeAssistantError("Ring-MQTT is already playing a message")
        if result.get("status") != "ended":
            raise HomeAssistantError(result.get("error", "Ring-MQTT playback failed"))
