import asyncio
import io
import struct
import wave
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.stt_provider import LocalFasterWhisperProvider


def generate_sample_wav(duration_seconds: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Generate a simple 16kHz mono WAV audio sample in memory."""
    frames = int(duration_seconds * sample_rate)
    samples = [int(3000 * (i % 32 - 16) / 16) for i in range(frames)]
    data = struct.pack(f"<{len(samples)}h", *samples)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(data)
    return buffer.getvalue()


async def run_smoke_test():
    print("=== PCMA Local faster-whisper STT Smoke Test ===")
    print("Initializing LocalFasterWhisperProvider(model='small', device='cpu', compute_type='int8')...")
    provider = LocalFasterWhisperProvider(model="small", device="cpu", compute_type="int8")
    
    print("Generating 2.0s audio sample...")
    audio_wav = generate_sample_wav(2.0)
    print(f"Generated WAV audio sample size: {len(audio_wav)} bytes.")

    print("Executing local STT transcription with actual model...")
    transcript = await provider.transcribe(audio_wav, "audio/wav")

    print("\n--- SMOKE TEST RESULT ---")
    print(f"Provider Name : {provider.name}")
    print(f"Model Used    : {transcript.model}")
    print(f"Detected Lang : {transcript.language}")
    print(f"Segment Count : {len(transcript.segments)}")
    for idx, seg in enumerate(transcript.segments):
        print(f"  Segment {idx+1}: [{seg.start_seconds:.2f}s - {seg.end_seconds:.2f}s] text='{seg.text}' confidence={seg.confidence:.4f}")
    print("=== Local STT Smoke Test PASSED Successfully! ===\n")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
