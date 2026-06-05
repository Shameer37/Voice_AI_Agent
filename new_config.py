import os

from pydantic_settings import BaseSettings
from utils import get_server_domain
from dotenv import load_dotenv
load_dotenv()


class Settings(BaseSettings):
    """Application settings"""
    
    # Local Agent Configuration
    local_agent_websocket_url: str = os.getenv("LOCAL_AGENT_WEBSOCKET_URL")
    local_agent_sample_rate: str = str(os.getenv("LOCAL_AGENT_SAMPLE_RATE"))
    
    # Server Configuration - dynamically get ngrok URL
    @property
    def server_domain(self) -> str:
        return get_server_domain()
    
    server_host: str = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port: int = int(os.getenv("SERVER_PORT", "8000"))
    
    # Teler Configuration
    teler_api_key: str = os.getenv("TELER_API_KEY")
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL")

    openai_api_key: str = os.getenv("OPENAI_API_KEY")
    # TTS model + voice defaults (override via env)
    #openai_realtime_model: str = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-transcribe")
    openai_tts_model: str = os.getenv("OPENAI_TTS_MODEL")
    openai_tts_voice: str = os.getenv("OPENAI_TTS_VOICE")
    # preferred output format (pcm/wav/mp3). We'll request PCM and resample to 8k when needed.
    openai_tts_response_format: str = os.getenv("OPENAI_TTS_RESPONSE_FORMAT")
    openai_stt_sr: str = os.getenv("OPENAI_STT_SR") 

    FREJUN_GREETING_FRAME_MS : str = os.getenv("FREJUN_GREETING_FRAME_MS")
    GREETING_FADE_MS : str = os.getenv("GREETING_FADE_MS")

        # -------------------------
    # SMTP / Email
    # -------------------------
    smtp_host: str = os.getenv("SMTP_HOST")
    smtp_port: int = int(os.getenv("SMTP_PORT"))
    smtp_sender: str = os.getenv("SMTP_SENDER")
    support_team_email: str = os.getenv("SUPPORT_TEAM_EMAIL")



    # Extra fields from .env
    env: str = os.getenv("ENV", "local")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY")
    db_host: str = os.getenv("DB_HOST")
    db_port: int = int(os.getenv("DB_PORT"))
    db_user: str = os.getenv("DB_USER")
    db_password: str = os.getenv("DB_PASSWORD")
    db_name: str = os.getenv("DB_NAME")
    public_domain: str = os.getenv("PUBLIC_DOMAIN")
    from_number: str = os.getenv("FROM_NUMBER")
    to_number: str = os.getenv("TO_NUMBER")
    rag_test_mode: int = int(os.getenv("RAG_TEST_MODE"))

    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()
