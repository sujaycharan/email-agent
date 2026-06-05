from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    gemini_api_key: str
    google_client_id: str
    google_client_secret: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str
    app_url: str = "http://localhost:8000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
