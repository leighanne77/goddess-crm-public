"""ElevenLabs implementation of TTSProvider.

Calls https://api.elevenlabs.io/v1/text-to-speech/{voice_id} directly
via httpx rather than the `elevenlabs` SDK — the endpoint is small
and avoiding the SDK keeps the dependency surface tight.

Auth: per-request `xi-api-key` header, sourced from
`settings.elevenlabs_api_key`. Voice selection: `voice_id` arg
overrides the configured default (`settings.elevenlabs_voice_id`),
which lets a single account host multiple voices later.

Output: MP3 at 44.1kHz 128kbps (ElevenLabs default). The browser
`<audio>` element plays MP3 natively across every desktop and mobile
browser the team uses.
"""

from __future__ import annotations

import httpx

from app.services.voice.tts_base import RawAudio, TTSConfigError, TTSProviderError

_API_BASE = "https://api.elevenlabs.io/v1"
_PROVIDER_NAME = "elevenlabs"
_HTTP_TIMEOUT_SEC = 30.0


class TTSElevenLabsProvider:
    """Sync TTS via ElevenLabs."""

    def __init__(
        self,
        *,
        api_key: str,
        default_voice_id: str,
        model_id: str = "eleven_turbo_v2_5",
        speed: float = 1.0,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise TTSConfigError("elevenlabs_api_key not configured")
        if not default_voice_id:
            raise TTSConfigError("elevenlabs_voice_id not configured")
        self._api_key = api_key
        self._default_voice_id = default_voice_id
        self._model_id = model_id
        self._speed = speed
        self._stability = stability
        self._similarity_boost = similarity_boost
        self._style = style
        self._client = client or httpx.Client(timeout=_HTTP_TIMEOUT_SEC)

    def speak(self, text: str, *, voice_id: str | None = None) -> RawAudio:
        effective_voice = voice_id or self._default_voice_id
        url = f"{_API_BASE}/text-to-speech/{effective_voice}"
        headers = {
            "xi-api-key": self._api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": {
                "speed": self._speed,
                "stability": self._stability,
                "similarity_boost": self._similarity_boost,
                "style": self._style,
            },
        }
        try:
            response = self._client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise TTSProviderError(f"ElevenLabs request failed: {exc}") from exc

        if response.status_code != 200:
            # ElevenLabs error responses come back as JSON with a `detail` field.
            # Truncate the body so a verbose error doesn't bloat our logs.
            body = response.text[:500]
            raise TTSProviderError(
                f"ElevenLabs returned HTTP {response.status_code}: {body}"
            )

        audio_bytes = response.content
        return RawAudio(
            audio_bytes=audio_bytes,
            content_type="audio/mpeg",
            char_count=len(text),
            provider=_PROVIDER_NAME,
            model_id=self._model_id,
            voice_id=effective_voice,
        )
