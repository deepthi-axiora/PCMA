import asyncio
import json
import math
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import settings


class STTError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


@dataclass(frozen=True)
class ProviderSegment:
    start_seconds: float
    end_seconds: float
    text: str
    confidence: float


@dataclass(frozen=True)
class ProviderTranscript:
    language: str
    segments: list[ProviderSegment]
    model: str


class SpeechToTextProvider(Protocol):
    name: str
    model: str

    async def transcribe(self, audio: bytes, content_type: str) -> ProviderTranscript: ...


class LocalFasterWhisperProvider:
    """Free, local speech-to-text adapter using faster-whisper."""

    name = "local"
    _model_cache: dict[tuple[str, str, str], Any] = {}

    def __init__(self, model: str, device: str, compute_type: str):
        self._model_name = model
        self.model = model
        self._device = device
        self._compute_type = compute_type

    def _get_model(self) -> Any:
        cache_key = (self._model_name, self._device, self._compute_type)
        if cache_key not in self._model_cache:
            try:
                import sys, types
                if "av" not in sys.modules:
                    try:
                        import av
                    except Exception:
                        d = types.ModuleType("av")
                        d.logging = types.ModuleType("logging")
                        sys.modules["av"] = d

                from faster_whisper import WhisperModel
                self._model_cache[cache_key] = WhisperModel(
                    self._model_name,
                    device=self._device,
                    compute_type=self._compute_type,
                )
            except Exception as exc:
                raise STTError("stt_model_load_failed", f"Failed to load local Whisper model '{self._model_name}': {exc}", retryable=False) from exc
        return self._model_cache[cache_key]

    async def transcribe(self, audio: bytes, content_type: str) -> ProviderTranscript:
        if not audio:
            raise STTError("empty_audio", "Audio payload is empty", retryable=False)

        model_obj = self._get_model()

        def _run_transcription() -> ProviderTranscript:
            import io, wave, math
            import numpy as np

            try:
                with wave.open(io.BytesIO(audio), "rb") as wav_file:
                    n_channels = wav_file.getnchannels()
                    sampwidth = wav_file.getsampwidth()
                    pcm_bytes = wav_file.readframes(wav_file.getnframes())

                if sampwidth == 2:
                    raw_samples = np.frombuffer(pcm_bytes, dtype=np.int16)
                    audio_float32 = raw_samples.astype(np.float32) / 32768.0
                elif sampwidth == 4:
                    raw_samples = np.frombuffer(pcm_bytes, dtype=np.int32)
                    audio_float32 = raw_samples.astype(np.float32) / 2147483648.0
                else:
                    raw_samples = np.frombuffer(pcm_bytes, dtype=np.uint8)
                    audio_float32 = (raw_samples.astype(np.float32) - 128.0) / 128.0

                if n_channels > 1:
                    audio_float32 = audio_float32.reshape(-1, n_channels).mean(axis=1)

            except Exception:
                raw_samples = np.frombuffer(audio, dtype=np.int16)
                audio_float32 = raw_samples.astype(np.float32) / 32768.0

            segments_iter, info = model_obj.transcribe(
                audio_float32,
                beam_size=5,
                temperature=0.0,
            )
            segments_list = list(segments_iter)
            language = (getattr(info, "language", None) or "en").strip().lower()

            provider_segments = []
            for seg in segments_list:
                text = str(seg.text).strip()
                if not text:
                    continue
                start = float(seg.start)
                end = float(seg.end)
                avg_logprob = float(getattr(seg, "avg_logprob", -0.2))
                confidence = max(0.0, min(1.0, math.exp(min(0.0, avg_logprob))))
                provider_segments.append(ProviderSegment(start, end, text, confidence))

            return ProviderTranscript(
                language=language,
                segments=provider_segments,
                model=self._model_name,
            )

        try:
            return await asyncio.to_thread(_run_transcription)
        except STTError:
            raise
        except Exception as exc:
            raise STTError("stt_provider_request_failed", f"Local faster-whisper transcription failed: {exc}", retryable=True) from exc


class OpenAIWhisperProvider:
    """Configurable adapter for the OpenAI-compatible Audio Transcriptions API."""

    name = "openai_whisper"

    def __init__(self, api_key: str, base_url: str, model: str, timeout_seconds: float):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self.model = model
        self._timeout_seconds = timeout_seconds

    async def transcribe(self, audio: bytes, content_type: str) -> ProviderTranscript:
        boundary = f"pcma-{uuid.uuid4().hex}"
        fields = {
            "model": self._model,
            "response_format": "verbose_json",
            "temperature": "0",
            "timestamp_granularities[]": "segment",
        }
        body = bytearray()
        for name, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            body.extend(value.encode())
            body.extend(b"\r\n")
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n')
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(audio)
        body.extend(f"\r\n--{boundary}--\r\n".encode())
        url = f"{self._base_url}/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(url, content=bytes(body), headers=headers)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise STTError("stt_provider_unavailable", "Speech-to-text provider is unavailable",
                           retryable=True) from exc
        if response.status_code >= 400:
            retryable = response.status_code in {408, 409, 425, 429} or response.status_code >= 500
            raise STTError("stt_provider_request_failed", "Speech-to-text request failed",
                           retryable=retryable)
        try:
            payload = response.json()
            language = payload["language"]
            source_segments = payload["segments"]
            segments = []
            for segment in source_segments:
                start = float(segment["start"])
                end = float(segment["end"])
                text = str(segment["text"]).strip()
                average_log_probability = float(segment["avg_logprob"])
                confidence = max(0.0, min(1.0, math.exp(min(0.0, average_log_probability))))
                segments.append(ProviderSegment(start, end, text, confidence))
            if not isinstance(language, str) or not language.strip() or not segments:
                raise ValueError("missing language or segments")
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise STTError("stt_invalid_provider_response", "Speech-to-text response was incomplete",
                           retryable=False) from exc
        return ProviderTranscript(language=language.strip().lower(), segments=segments,
                                  model=self._model)


def create_stt_provider(name: str | None = None, model: str | None = None) -> SpeechToTextProvider:
    provider_name = (name or settings.stt_provider).strip().lower()
    if provider_name in ("local", "local_faster_whisper", "faster_whisper"):
        return LocalFasterWhisperProvider(
            model=model or settings.local_stt_model,
            device=settings.local_stt_device,
            compute_type=settings.local_stt_compute_type,
        )
    elif provider_name == "openai_whisper":
        if not settings.stt_api_key:
            raise STTError("stt_provider_not_configured", "Configure STT_API_KEY before processing audio",
                           retryable=False)
        return OpenAIWhisperProvider(
            api_key=settings.stt_api_key,
            base_url=settings.stt_api_base_url,
            model=model or settings.stt_model,
            timeout_seconds=settings.stt_timeout_seconds,
        )
    else:
        raise STTError("stt_provider_not_supported", f"Configured speech-to-text provider '{provider_name}' is not supported",
                       retryable=False)
