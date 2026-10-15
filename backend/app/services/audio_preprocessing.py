import io
import logging
import math
import asyncio
import shutil
import sys
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.services.stt_provider import STTError

logger = logging.getLogger("pcma.audio_preprocessing")


@dataclass(frozen=True)
class AudioChunk:
    index: int
    start_ms: int
    end_ms: int
    audio: bytes


def create_speech_chunks(audio: bytes) -> tuple[list[AudioChunk], int]:
    """Apply deterministic PCM-WAV VAD, merge brief gaps, and split long speech runs."""
    logger.info("audio_parse_started input_bytes=%d", len(audio))
    try:
        source = wave.open(io.BytesIO(audio), "rb")
        with source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            sample_rate = source.getframerate()
            frame_count = source.getnframes()
            compression = source.getcomptype()
            raw_frames = source.readframes(frame_count)
            params = source.getparams()
    except (wave.Error, EOFError) as exc:
        logger.info("audio_wav_parse_rejected error_type=%s input_bytes=%d",
                    type(exc).__name__, len(audio))
        raise STTError("unsupported_audio_encoding", "Transcription currently requires PCM WAV audio",
                       retryable=False) from exc
    logger.info(
        "audio_wav_header sample_rate=%d channels=%d sample_width=%d frame_count=%d raw_data_bytes=%d",
        sample_rate, channels, sample_width, frame_count, len(raw_frames),
    )
    if compression != "NONE" or sample_width != 2 or channels not in {1, 2}:
        raise STTError("unsupported_audio_encoding", "Transcription requires uncompressed 16-bit mono or stereo WAV",
                       retryable=False)
    if sample_rate < 8000 or sample_rate > 48000 or frame_count == 0:
        raise STTError("invalid_audio_quality", "Audio sample rate or duration is not supported",
                       retryable=False)
    duration_ms = int(frame_count * 1000 / sample_rate)
    if duration_ms < settings.stt_min_audio_duration_ms:
        raise STTError("audio_too_short", "Audio is shorter than the configured minimum duration",
                       retryable=False)

    samples = array("h")
    samples.frombytes(raw_frames)
    if sys.byteorder == "big":
        samples.byteswap()
    if len(samples) != frame_count * channels:
        logger.error(
            "audio_sample_count_mismatch frame_count=%d channels=%d sample_count=%d raw_data_bytes=%d",
            frame_count, channels, len(samples), len(raw_frames),
        )
        raise STTError("audio_file_truncated", "The uploaded audio file is incomplete", retryable=False)
    if channels == 2:
        frame_samples = [
            (samples[pos] + samples[pos + 1]) // 2
            for pos in range(0, len(samples) - 1, 2)
        ]
    else:
        frame_samples = samples

    frames_per_vad_window = max(1, sample_rate * 30 // 1000)
    active_windows: list[int] = []
    for frame_start in range(0, frame_count, frames_per_vad_window):
        frame_end = min(frame_count, frame_start + frames_per_vad_window)
        values = frame_samples[frame_start:frame_end]
        if not values:
            continue
        mean_square = sum(value * value for value in values) // len(values)
        if math.isqrt(mean_square) >= settings.stt_vad_rms_threshold:
            active_windows.append(frame_start // frames_per_vad_window)
    if not active_windows:
        raise STTError("no_speech_detected", "No speech was detected in the uploaded audio",
                       retryable=False)

    max_gap_windows = max(0, settings.stt_vad_silence_ms // 30)
    runs: list[tuple[int, int]] = []
    run_start = previous = active_windows[0]
    for window_index in active_windows[1:]:
        if window_index - previous - 1 > max_gap_windows:
            runs.append((run_start, previous + 1))
            run_start = window_index
        previous = window_index
    runs.append((run_start, previous + 1))

    pad_windows = max(0, settings.stt_vad_padding_ms // 30)
    max_chunk_frames = max(1, settings.stt_max_chunk_duration_seconds * sample_rate)
    chunks: list[AudioChunk] = []
    for run_start, run_end in runs:
        start_frame = max(0, run_start * frames_per_vad_window - pad_windows * frames_per_vad_window)
        end_frame = min(frame_count, run_end * frames_per_vad_window + pad_windows * frames_per_vad_window)
        cursor = start_frame
        while cursor < end_frame:
            chunk_end = min(end_frame, cursor + max_chunk_frames)
            start_byte = cursor * channels * sample_width
            end_byte = chunk_end * channels * sample_width
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as output:
                output.setparams(params)
                output.writeframes(raw_frames[start_byte:end_byte])
            chunks.append(AudioChunk(
                index=len(chunks),
                start_ms=int(cursor * 1000 / sample_rate),
                end_ms=int(chunk_end * 1000 / sample_rate),
                audio=buffer.getvalue(),
            ))
            cursor = chunk_end
    logger.info("audio_vad_completed duration_ms=%d chunks=%d chunk_durations_ms=%s",
                duration_ms, len(chunks),
                ",".join(str(chunk.end_ms - chunk.start_ms) for chunk in chunks))
    return chunks, duration_ms


async def prepare_speech_chunks(audio: bytes) -> tuple[list[AudioChunk], int]:
    logger.info("audio_preprocessing_started input_bytes=%d", len(audio))
    try:
        return await asyncio.to_thread(create_speech_chunks, audio)
    except STTError as error:
        if error.code not in {"unsupported_audio_encoding", "invalid_audio_quality"}:
            logger.error("audio_preprocessing_failed stage=direct_wav_parse code=%s", error.code)
            raise
        logger.info("audio_conversion_required code=%s input_bytes=%d", error.code, len(audio))
    from app.core.config import settings
    try:
        ffmpeg_is_file = Path(settings.stt_ffmpeg_path).is_file()
    except OSError:
        ffmpeg_is_file = False
    try:
        ffmpeg_on_path = shutil.which(settings.stt_ffmpeg_path) is not None
    except OSError:
        ffmpeg_on_path = False
    ffmpeg_resolved = ffmpeg_is_file or ffmpeg_on_path
    logger.info("ffmpeg_started configured=%s resolved=%s input_bytes=%d",
                bool(settings.stt_ffmpeg_path), ffmpeg_resolved, len(audio))
    try:
        process = await asyncio.create_subprocess_exec(
            settings.stt_ffmpeg_path,
            "-nostdin", "-v", "error", "-i", "pipe:0",
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        converted_pcm, _stderr = await asyncio.wait_for(
            process.communicate(audio), timeout=settings.stt_timeout_seconds
        )
    except (FileNotFoundError, asyncio.TimeoutError, OSError) as exc:
        logger.error("ffmpeg_unavailable error_type=%s", type(exc).__name__)
        raise STTError("audio_conversion_unavailable",
                       "Audio format conversion is unavailable; install/configure FFmpeg",
                       retryable=False) from exc

    # If piping to stdin produced no audio or failed (e.g. 3GP/MP4 containers with index atoms at end of file),
    # retry using a temporary seekable file on disk.
    if process.returncode != 0 or not converted_pcm or len(converted_pcm) % 2:
        logger.info("ffmpeg_pipe_empty_or_failed attempting_seekable_file return_code=%s raw_pcm_bytes=%d",
                    process.returncode, len(converted_pcm or b""))
        import os
        import tempfile
        temp_input_path = None
        try:
            def _write_temp() -> str:
                with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tf:
                    tf.write(audio)
                    tf.flush()
                    return tf.name

            temp_input_path = await asyncio.to_thread(_write_temp)
            file_proc = await asyncio.create_subprocess_exec(
                settings.stt_ffmpeg_path,
                "-y", "-hide_banner", "-loglevel", "error", "-i", temp_input_path,
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            converted_pcm_file, stderr_file = await asyncio.wait_for(
                file_proc.communicate(), timeout=settings.stt_timeout_seconds
            )
            if file_proc.returncode == 0 and converted_pcm_file and len(converted_pcm_file) % 2 == 0:
                process = file_proc
                converted_pcm = converted_pcm_file
                _stderr = stderr_file
        except Exception as exc:
            logger.warning("ffmpeg_seekable_file_attempt_failed error=%s", exc)
        finally:
            if temp_input_path and os.path.exists(temp_input_path):
                try:
                    os.remove(temp_input_path)
                except OSError:
                    pass
    stderr_text = (_stderr or b"").decode("utf-8", errors="replace")[:2048]
    logger.info("ffmpeg_completed return_code=%s raw_pcm_bytes=%d stderr=%r",
                process.returncode, len(converted_pcm), stderr_text)
    if process.returncode != 0 or not converted_pcm or len(converted_pcm) % 2:
        logger.error("ffmpeg_output_invalid return_code=%s raw_pcm_bytes=%d",
                     process.returncode, len(converted_pcm))
        raise STTError("audio_conversion_failed", "Audio could not be converted for transcription",
                       retryable=False)
    # FFmpeg cannot seek on stdout to finalize RIFF/data sizes. Writing a WAV
    # header directly to that pipe can therefore advertise an invalid frame
    # count; wrap the raw PCM in a seekable in-memory WAV instead.
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as converted_wav:
        converted_wav.setnchannels(1)
        converted_wav.setsampwidth(2)
        converted_wav.setframerate(16000)
        converted_wav.writeframes(converted_pcm)
    converted_audio = wav_buffer.getvalue()
    logger.info("audio_wav_built_in_memory sample_rate=16000 channels=1 sample_width=2 "
                "raw_pcm_bytes=%d wav_bytes=%d wav_data_bytes=%d",
                len(converted_pcm), len(converted_audio), len(converted_pcm))
    try:
        return await asyncio.to_thread(create_speech_chunks, converted_audio)
    except STTError as error:
        logger.error("audio_preprocessing_failed stage=converted_pcm_parse code=%s "
                     "raw_pcm_bytes=%d wav_bytes=%d", error.code, len(converted_pcm),
                     len(converted_audio))
        raise
