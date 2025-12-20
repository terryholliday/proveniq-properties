"""Application configuration using Pydantic Settings."""

from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageProvider(str, Enum):
    GCS = "gcs"
    S3 = "s3"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "PROVENIQ Properties"
    debug: bool = False
    api_v1_prefix: str = "/v1"

    # Database
    database_url: str

    # Firebase Auth
    firebase_project_id: str
    google_application_credentials: Optional[str] = None

    # Storage
    storage_provider: StorageProvider = StorageProvider.GCS

    # GCS Config
    gcs_bucket_name: Optional[str] = None
    gcs_project_id: Optional[str] = None

    # S3 Config
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = "us-east-1"
    s3_bucket_name: Optional[str] = None

    # Presigned URLs
    presign_ttl_seconds: int = 300
    max_upload_size_mb: int = 50

    # Mason AI
    mason_enabled: bool = True

    @property
    def bucket_name(self) -> str:
        """Get the appropriate bucket name based on storage provider."""
        if self.storage_provider == StorageProvider.GCS:
            if not self.gcs_bucket_name:
                raise ValueError("GCS_BUCKET_NAME required when STORAGE_PROVIDER=gcs")
            return self.gcs_bucket_name
        else:
            if not self.s3_bucket_name:
                raise ValueError("S3_BUCKET_NAME required when STORAGE_PROVIDER=s3")
            return self.s3_bucket_name


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
