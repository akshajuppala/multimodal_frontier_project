from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    emergency_contact_number: str = ""
    tts_provider: str = "openai"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    weather_api_key: str = ""
    default_location: str = "New York,US"
    frame_sample_rate: int = 2
    observer_window_seconds: int = 5
    user_name: str = "friend"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
