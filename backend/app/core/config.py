from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Personal Conversation Memory Assistant"
    app_version: str = "1.0.0"
    database_url: str

    auth_issuer_url: str | None = None
    auth_audience: str | None = None
    auth_jwks_url: str | None = None
    audio_storage_dir: str = "./private_audio"
    audio_encryption_key: str | None = None
    stt_provider: str = "local"
    stt_api_key: str | None = None
    stt_api_base_url: str = "https://api.openai.com/v1"
    stt_ffmpeg_path: str = "ffmpeg"
    stt_model: str = "whisper-1"
    local_stt_model: str = "small"
    local_stt_device: str = "cpu"
    local_stt_compute_type: str = "int8"
    stt_timeout_seconds: float = 90.0
    stt_worker_poll_seconds: float = 2.0
    stt_max_attempts: int = 3
    stt_retry_base_seconds: int = 10
    stt_job_lease_seconds: int = 180
    stt_min_audio_duration_ms: int = 1000
    stt_max_chunk_duration_seconds: int = 30
    stt_vad_rms_threshold: int = 350
    stt_vad_silence_ms: int = 500
    stt_vad_padding_ms: int = 200
    stt_confidence_floor: float = 0.367879
    stt_supported_languages: str = ""
    diarization_provider: str = "http_json"
    diarization_api_key: str | None = None
    diarization_api_base_url: str | None = None
    diarization_model: str = ""
    diarization_timeout_seconds: float = 120.0
    diarization_confidence_floor: float = 0.6
    diarization_max_attempts: int = 3
    local_diarization_model: str = "pyannote/speaker-diarization-3.1"
    local_diarization_device: str = "cpu"
    huggingface_token: str | None = None
    llm_provider: str = "mock"
    llm_api_key: str | None = None
    llm_api_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
