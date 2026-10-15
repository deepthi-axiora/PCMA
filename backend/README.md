# PCMA backend

## Transcription worker

Stopping a recording creates a `transcription` row in `ai_processing_jobs` in the same database transaction. Run the worker separately from the FastAPI process so transcription does not hold the stop request open:

```powershell
python -m app.workers.transcription_worker
```

Apply database migrations before starting the API or worker:

```powershell
alembic upgrade head
```

Configure the provider and encryption key in the backend environment. See `.env.example` for the settings. `STT_API_KEY` is required by the default `openai_whisper` adapter; `STT_API_BASE_URL` and `STT_MODEL` can point it at a compatible transcription service/model. The adapter requests timestamped verbose segments. Audio and transcript text are never included in worker logs.

The worker uses a PostgreSQL job table with row locks and expiring leases, allowing multiple worker processes. Failures retry with bounded exponential backoff; permanent failures set the recording and job to `failed`. Owners can inspect `GET /v1/recordings/{recording_id}/transcription-status`, retrieve `GET /v1/recordings/{recording_id}/transcript` (including any preserved partial transcript), and retry with `POST /v1/recordings/{recording_id}/transcription/retry`.

The built-in deterministic VAD accepts uncompressed 16-bit mono or stereo PCM WAV directly. Other containers/encodings require the configured `STT_FFMPEG_PATH` executable (default `ffmpeg`) so they can be converted to 16 kHz mono PCM. The VAD threshold, silence merge, padding, minimum duration, chunk duration, and confidence floor are configurable in `app/core/config.py` through their corresponding environment variables.

## Tests

The test suite uses an isolated in-memory SQLite database and an injected STT provider test double. No provider credentials or network calls are needed for tests:

```powershell
python -m pytest -q -p no:cacheprovider
```
