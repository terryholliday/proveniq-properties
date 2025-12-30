"""
Runtime Environment Validation Module

This module validates all required environment variables at application startup.
If validation fails, the application will refuse to start (hard fail).

This prevents runtime errors from missing or misconfigured environment variables.
"""

import os
import sys
from typing import Optional

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProductionSettings(BaseSettings):
    """
    Strict validation schema for production environment variables.
    
    All required fields MUST be present and valid, or the application will not start.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",  # Fail on unknown environment variables in production
    )
    
    # ========================================================================
    # CRITICAL: Database Configuration
    # ========================================================================
    database_url: str  # REQUIRED: PostgreSQL connection string
    
    # ========================================================================
    # CRITICAL: Firebase Authentication
    # ========================================================================
    firebase_project_id: str  # REQUIRED: Firebase project ID
    google_application_credentials: Optional[str] = None  # Path to service account JSON
    
    # ========================================================================
    # CRITICAL: Storage Provider
    # ========================================================================
    storage_provider: str  # REQUIRED: "gcs" or "s3"
    
    # GCS Configuration (required if storage_provider=gcs)
    gcs_bucket_name: Optional[str] = None
    gcs_project_id: Optional[str] = None
    
    # S3 Configuration (required if storage_provider=s3)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = None
    s3_bucket_name: Optional[str] = None
    
    # ========================================================================
    # Application Configuration
    # ========================================================================
    app_name: str = "PROVENIQ Properties"
    debug: bool = False
    api_v1_prefix: str = "/v1"
    
    # ========================================================================
    # CRITICAL: CORS Configuration
    # ========================================================================
    allowed_origins: str  # REQUIRED: Comma-separated list of allowed origins
    
    # ========================================================================
    # Optional: External Integrations
    # ========================================================================
    claimsiq_enabled: bool = False
    claimsiq_base_url: Optional[str] = None
    claimsiq_api_key: Optional[str] = None
    
    mason_enabled: bool = True
    
    # ========================================================================
    # Optional: Upload Configuration
    # ========================================================================
    presign_ttl_seconds: int = 300
    max_upload_size_mb: int = 50


def validate_environment() -> ProductionSettings:
    """
    Validate all required environment variables at startup.
    
    This function MUST be called before the FastAPI app starts.
    If validation fails, the application will exit with code 1.
    
    Returns:
        ProductionSettings: Validated settings object
        
    Raises:
        SystemExit: If validation fails (exit code 1)
    """
    
    try:
        settings = ProductionSettings()
        
        # ====================================================================
        # Additional Production-Specific Validation
        # ====================================================================
        
        # 1. CORS: Ensure wildcard is not used in production
        if not settings.debug:
            origins = [o.strip() for o in settings.allowed_origins.split(",")]
            if "*" in origins:
                print(
                    "❌ FATAL: Wildcard CORS origin (*) detected in production mode.",
                    file=sys.stderr
                )
                print(
                    "   Set ALLOWED_ORIGINS to specific domains (comma-separated).",
                    file=sys.stderr
                )
                sys.exit(1)
        
        # 2. Storage Provider: Validate provider-specific configuration
        if settings.storage_provider == "gcs":
            if not settings.gcs_bucket_name or not settings.gcs_project_id:
                print(
                    "❌ FATAL: GCS_BUCKET_NAME and GCS_PROJECT_ID required when STORAGE_PROVIDER=gcs",
                    file=sys.stderr
                )
                sys.exit(1)
        elif settings.storage_provider == "s3":
            if not settings.s3_bucket_name or not settings.aws_access_key_id or not settings.aws_secret_access_key:
                print(
                    "❌ FATAL: S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY required when STORAGE_PROVIDER=s3",
                    file=sys.stderr
                )
                sys.exit(1)
        else:
            print(
                f"❌ FATAL: Invalid STORAGE_PROVIDER '{settings.storage_provider}'. Must be 'gcs' or 's3'.",
                file=sys.stderr
            )
            sys.exit(1)
        
        # 3. Firebase: Validate credentials path exists (if provided)
        if settings.google_application_credentials:
            if not os.path.exists(settings.google_application_credentials):
                print(
                    f"❌ FATAL: Firebase credentials file not found: {settings.google_application_credentials}",
                    file=sys.stderr
                )
                sys.exit(1)
        
        # 4. Database URL: Basic format validation
        if not settings.database_url.startswith("postgresql"):
            print(
                "❌ FATAL: DATABASE_URL must be a PostgreSQL connection string (postgresql:// or postgresql+asyncpg://)",
                file=sys.stderr
            )
            sys.exit(1)
        
        # ====================================================================
        # Success: Log validated configuration
        # ====================================================================
        print("✅ Environment validation passed")
        print(f"   App: {settings.app_name}")
        print(f"   Debug: {settings.debug}")
        print(f"   Storage: {settings.storage_provider}")
        print(f"   CORS Origins: {settings.allowed_origins}")
        
        return settings
        
    except ValidationError as e:
        print("❌ FATAL: Environment validation failed", file=sys.stderr)
        print("\nMissing or invalid environment variables:", file=sys.stderr)
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            print(f"   • {field}: {msg}", file=sys.stderr)
        
        print("\nThe application cannot start with invalid configuration.", file=sys.stderr)
        print("Please check your .env file or environment variables.", file=sys.stderr)
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ FATAL: Unexpected error during environment validation: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Allow running this module directly to test validation
    validate_environment()
    print("\n✅ All environment variables are valid!")
