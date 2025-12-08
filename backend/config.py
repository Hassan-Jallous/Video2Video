from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Google APIs
    google_gemini_api_key: str = ""
    google_cloud_project_id: Optional[str] = None

    # Google Drive Storage
    google_drive_folder_id: Optional[str] = None
    google_service_account_file: str = "credentials/google-drive-service-account.json"

    # Video Generation Providers
    kie_ai_api_key: str = ""
    defapi_org_api_key: str = ""

    # Infrastructure
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"

    # Storage Strategy
    storage_mode: str = "local"  # "local" or "google_drive"
    storage_path: str = "../storage"
    temp_path: str = "../tmp"

    # Defaults
    default_provider: str = "kie.ai"
    default_model: str = "veo-3.1-fast"
    default_strategy: str = "segments"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
