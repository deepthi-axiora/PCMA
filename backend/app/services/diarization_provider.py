import asyncio
import json
import logging
import math
import os
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger("pcma.diarization_provider")


class DiarizationError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


@dataclass(frozen=True)
class DiarizationInputSegment:
    id: int
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class SpeakerAssignment:
    segment_id: int
    speaker_label: str
    confidence: float


class DiarizationProvider(Protocol):
    name: str
    model: str

    async def diarize(self, audio: bytes, content_type: str,
                      segments: list[DiarizationInputSegment]) -> list[SpeakerAssignment]: ...


class HttpJsonDiarizationProvider:
    """Configurable adapter contract: POST /diarizations with audio and timed segments."""

    name = "http_json"

    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: float):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def diarize(self, audio: bytes, content_type: str,
                      segments: list[DiarizationInputSegment]) -> list[SpeakerAssignment]:
        payload = [{"segment_id": item.id, "start_ms": item.start_ms,
                    "end_ms": item.end_ms, "text": item.text} for item in segments]
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/diarizations",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data={"model": self.model, "segments": json.dumps(payload)},
                    files={"file": ("recording.audio", audio, content_type)},
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise DiarizationError("diarization_provider_unavailable",
                                   "Speaker diarization service is unavailable", retryable=True) from exc
        if response.status_code >= 400:
            retryable = response.status_code in {408, 409, 425, 429} or response.status_code >= 500
            raise DiarizationError("diarization_provider_request_failed",
                                   "Speaker diarization request failed", retryable=retryable)
        try:
            body = response.json()
            raw_assignments = body["assignments"]
            assignments = [SpeakerAssignment(
                segment_id=int(row["segment_id"]),
                speaker_label=str(row["speaker_label"]).strip(),
                confidence=float(row["confidence"]),
            ) for row in raw_assignments]
            if not isinstance(raw_assignments, list) or any(
                not item.speaker_label or not math.isfinite(item.confidence)
                or not 0 <= item.confidence <= 1 for item in assignments
            ):
                raise ValueError("invalid assignment")
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise DiarizationError("diarization_invalid_response",
                                   "Speaker diarization response was incomplete", retryable=False) from exc
        return assignments


class LocalPyannoteDiarizationProvider:
    """Free local speaker diarization using pyannote.audio running on CPU by default."""

    name = "local"

    def __init__(self, model: str | None = None, device: str | None = None, hf_token: str | None = None):
        self.model = model or getattr(settings, "local_diarization_model", "pyannote/speaker-diarization-3.1")
        self.device = device or getattr(settings, "local_diarization_device", "cpu")
        raw_token = hf_token or getattr(settings, "huggingface_token", None) or os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
        self.hf_token = raw_token.strip() if raw_token and isinstance(raw_token, str) and raw_token.strip() else None
        self._pipeline = None

    def _load_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline

        try:
            from pyannote.audio import Pipeline
        except ImportError as exc:
            raise DiarizationError(
                "diarization_provider_not_configured",
                "pyannote.audio and torch packages are required for local diarization.",
                retryable=False,
            ) from exc

        try:
            kwargs = {}
            if self.hf_token:
                kwargs["token"] = self.hf_token

            try:
                pipeline = Pipeline.from_pretrained(self.model, **kwargs)
            except TypeError:
                if "token" in kwargs:
                    token_val = kwargs.pop("token")
                    kwargs["use_auth_token"] = token_val
                pipeline = Pipeline.from_pretrained(self.model, **kwargs)
        except Exception as exc:
            err_str = str(exc).lower()
            if any(k in err_str for k in ("gated", "unauthorized", "401", "403", "token", "credentials")):
                raise DiarizationError(
                    "diarization_credentials_missing",
                    "Hugging Face access token is missing or unauthorized for pyannote diarization model.",
                    retryable=False,
                ) from exc
            elif any(k in err_str for k in ("timeout", "connection", "network", "offline")):
                raise DiarizationError(
                    "diarization_model_download_failed",
                    "Failed to download pyannote diarization model due to network connection issues.",
                    retryable=True,
                ) from exc
            else:
                raise DiarizationError(
                    "diarization_model_unavailable",
                    f"Could not load pyannote diarization model '{self.model}'.",
                    retryable=False,
                ) from exc

        if pipeline is None:
            raise DiarizationError(
                "diarization_credentials_missing" if not self.hf_token else "diarization_model_unavailable",
                "Pyannote diarization pipeline could not be loaded. Ensure HUGGINGFACE_TOKEN is valid and user terms accepted.",
                retryable=False,
            )

        try:
            import torch
            device_obj = torch.device(self.device)
            pipeline.to(device_obj)
        except Exception as exc:
            logger.warning("diarization_device_assignment_warning device=%s error=%s", self.device, exc)

        self._pipeline = pipeline
        return self._pipeline

    async def diarize(
        self, audio: bytes, content_type: str, segments: list[DiarizationInputSegment]
    ) -> list[SpeakerAssignment]:
        if not segments:
            return []

        pipeline = self._load_pipeline()

        try:
            import io
            import wave
            import numpy as np
            import torch

            try:
                with wave.open(io.BytesIO(audio), "rb") as wav_file:
                    sample_rate = wav_file.getframerate()
                    num_channels = wav_file.getnchannels()
                    nframes = wav_file.getnframes()
                    frames = wav_file.readframes(nframes)
                    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                    if num_channels > 1:
                        samples = samples.reshape(-1, num_channels).T
                    else:
                        samples = samples.reshape(1, -1)
                    waveform = torch.from_numpy(samples)
            except Exception:
                try:
                    proc = await asyncio.create_subprocess_exec(
                        settings.stt_ffmpeg_path,
                        "-nostdin", "-v", "error", "-i", "pipe:0",
                        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    pcm_bytes, _ = await proc.communicate(audio)
                    if proc.returncode != 0 or not pcm_bytes:
                        raise ValueError("FFmpeg conversion failed")
                    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    waveform = torch.from_numpy(samples).reshape(1, -1)
                    sample_rate = 16000
                except Exception:
                    max_ms = max((seg.end_ms for seg in segments), default=1000)
                    sample_count = max(16000, int((max_ms / 1000.0) * 16000))
                    samples = np.zeros(sample_count, dtype=np.float32)
                    waveform = torch.from_numpy(samples).reshape(1, -1)
                    sample_rate = 16000

            diarization_result = await asyncio.to_thread(pipeline, {"waveform": waveform, "sample_rate": sample_rate})
        except Exception as exc:
            if isinstance(exc, DiarizationError):
                raise exc
            logger.error("local_diarization_inference_failed model=%s error_type=%s", self.model, type(exc).__name__)
            raise DiarizationError(
                "diarization_processing_failed",
                "Local speaker diarization inference failed.",
                retryable=False,
            ) from exc

        if hasattr(diarization_result, "speaker_diarization"):
            annotation = diarization_result.speaker_diarization
        else:
            annotation = diarization_result

        turns: list[tuple[float, float, str]] = []
        try:
            for turn, _, speaker_label in annotation.itertracks(yield_label=True):
                turns.append((float(turn.start), float(turn.end), str(speaker_label).strip()))
        except Exception as exc:
            raise DiarizationError(
                "diarization_invalid_response",
                "Local diarization output format was invalid.",
                retryable=False,
            ) from exc

        assignments: list[SpeakerAssignment] = []
        for seg in segments:
            seg_start_s = seg.start_ms / 1000.0
            seg_end_s = seg.end_ms / 1000.0
            seg_duration_s = max(0.001, seg_end_s - seg_start_s)

            overlaps: dict[str, float] = {}
            for t_start, t_end, spk in turns:
                overlap = max(0.0, min(seg_end_s, t_end) - max(seg_start_s, t_start))
                if overlap > 0:
                    overlaps[spk] = overlaps.get(spk, 0.0) + overlap

            if overlaps:
                best_spk, max_overlap = max(overlaps.items(), key=lambda item: item[1])
                confidence = min(1.0, max(0.0, max_overlap / seg_duration_s))
            else:
                best_spk = turns[0][2] if turns else "SPEAKER_00"
                confidence = 0.0

            assignments.append(SpeakerAssignment(
                segment_id=seg.id,
                speaker_label=best_spk,
                confidence=confidence,
            ))

        return assignments


def create_diarization_provider(name: str | None = None,
                                model: str | None = None) -> DiarizationProvider:
    provider_name = (name or settings.diarization_provider).strip().lower()
    if provider_name in ("local", "local_pyannote", "pyannote"):
        return LocalPyannoteDiarizationProvider(
            model=model or settings.local_diarization_model,
            device=settings.local_diarization_device,
            hf_token=settings.huggingface_token,
        )
    elif provider_name == "http_json":
        if not settings.diarization_api_base_url or not settings.diarization_api_key or not (model or settings.diarization_model):
            raise DiarizationError("diarization_provider_not_configured",
                                   "Configure the diarization provider URL, key, and model", retryable=False)
        return HttpJsonDiarizationProvider(settings.diarization_api_base_url,
                                           settings.diarization_api_key,
                                           model or settings.diarization_model,
                                           settings.diarization_timeout_seconds)
    else:
        raise DiarizationError("diarization_provider_not_supported",
                               "Configured diarization provider is not supported", retryable=False)
