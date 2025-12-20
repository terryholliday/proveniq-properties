"""Storage service with provider interface (GCS/S3)."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import uuid

from app.core.config import get_settings, StorageProvider

settings = get_settings()


class StorageProviderInterface(ABC):
    """Abstract interface for storage providers."""

    @abstractmethod
    async def generate_presigned_upload_url(
        self,
        object_path: str,
        mime_type: str,
        max_size_bytes: int,
        ttl_seconds: int,
    ) -> tuple[str, datetime]:
        """Generate a presigned PUT URL for direct upload.
        
        Returns:
            Tuple of (presigned_url, expires_at)
        """
        pass

    @abstractmethod
    async def generate_presigned_download_url(
        self,
        object_path: str,
        ttl_seconds: int,
    ) -> str:
        """Generate a presigned GET URL for download."""
        pass

    @abstractmethod
    async def verify_object_exists(self, object_path: str) -> bool:
        """Verify an object exists in storage."""
        pass

    @abstractmethod
    async def delete_object(self, object_path: str) -> bool:
        """Delete an object from storage."""
        pass


class GCSStorageProvider(StorageProviderInterface):
    """Google Cloud Storage provider."""

    def __init__(self, bucket_name: str, project_id: Optional[str] = None):
        self.bucket_name = bucket_name
        self.project_id = project_id
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from google.cloud import storage
            self._client = storage.Client(project=self.project_id)
        return self._client

    @property
    def bucket(self):
        return self.client.bucket(self.bucket_name)

    async def generate_presigned_upload_url(
        self,
        object_path: str,
        mime_type: str,
        max_size_bytes: int,
        ttl_seconds: int,
    ) -> tuple[str, datetime]:
        blob = self.bucket.blob(object_path)
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=ttl_seconds),
            method="PUT",
            content_type=mime_type,
        )
        
        return url, expires_at

    async def generate_presigned_download_url(
        self,
        object_path: str,
        ttl_seconds: int,
    ) -> str:
        blob = self.bucket.blob(object_path)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=ttl_seconds),
            method="GET",
        )

    async def verify_object_exists(self, object_path: str) -> bool:
        blob = self.bucket.blob(object_path)
        return blob.exists()

    async def delete_object(self, object_path: str) -> bool:
        blob = self.bucket.blob(object_path)
        if blob.exists():
            blob.delete()
            return True
        return False


class S3StorageProvider(StorageProviderInterface):
    """AWS S3 storage provider."""

    def __init__(
        self,
        bucket_name: str,
        region: str,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.region = region
        self._client = None
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client(
                "s3",
                region_name=self.region,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
            )
        return self._client

    async def generate_presigned_upload_url(
        self,
        object_path: str,
        mime_type: str,
        max_size_bytes: int,
        ttl_seconds: int,
    ) -> tuple[str, datetime]:
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": object_path,
                "ContentType": mime_type,
            },
            ExpiresIn=ttl_seconds,
        )
        
        return url, expires_at

    async def generate_presigned_download_url(
        self,
        object_path: str,
        ttl_seconds: int,
    ) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": object_path,
            },
            ExpiresIn=ttl_seconds,
        )

    async def verify_object_exists(self, object_path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_path)
            return True
        except Exception:
            return False

    async def delete_object(self, object_path: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_path)
            return True
        except Exception:
            return False


class StorageService:
    """High-level storage service wrapping provider interface."""

    ALLOWED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "video/mp4",
        "video/quicktime",
        "audio/mpeg",
        "audio/mp4",
        "application/pdf",
    }

    def __init__(self, provider: StorageProviderInterface):
        self.provider = provider

    def generate_object_path(
        self,
        org_id: UUID,
        inspection_id: UUID,
        item_id: UUID,
        file_name: str,
    ) -> str:
        """Generate a unique object path for evidence."""
        file_uuid = uuid.uuid4()
        ext = file_name.split(".")[-1] if "." in file_name else ""
        return f"orgs/{org_id}/inspections/{inspection_id}/items/{item_id}/{file_uuid}.{ext}"

    async def create_presigned_upload(
        self,
        org_id: UUID,
        inspection_id: UUID,
        item_id: UUID,
        file_name: str,
        mime_type: str,
        file_size_bytes: int,
    ) -> tuple[str, str, datetime]:
        """Create presigned upload URL with validation.
        
        Returns:
            Tuple of (upload_url, object_path, expires_at)
        """
        # Validate mime type
        if mime_type not in self.ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported mime type: {mime_type}")

        # Validate file size
        max_size = settings.max_upload_size_mb * 1024 * 1024
        if file_size_bytes > max_size:
            raise ValueError(f"File size exceeds maximum of {settings.max_upload_size_mb}MB")

        object_path = self.generate_object_path(org_id, inspection_id, item_id, file_name)
        
        url, expires_at = await self.provider.generate_presigned_upload_url(
            object_path=object_path,
            mime_type=mime_type,
            max_size_bytes=file_size_bytes,
            ttl_seconds=settings.presign_ttl_seconds,
        )

        return url, object_path, expires_at

    async def verify_upload(self, object_path: str) -> bool:
        """Verify an upload was completed."""
        return await self.provider.verify_object_exists(object_path)

    async def get_download_url(self, object_path: str, ttl_seconds: int = 3600) -> str:
        """Get a presigned download URL."""
        return await self.provider.generate_presigned_download_url(object_path, ttl_seconds)


def get_storage_service() -> StorageService:
    """Factory function to get storage service based on config."""
    if settings.storage_provider == StorageProvider.GCS:
        provider = GCSStorageProvider(
            bucket_name=settings.bucket_name,
            project_id=settings.gcs_project_id,
        )
    else:
        provider = S3StorageProvider(
            bucket_name=settings.bucket_name,
            region=settings.aws_region or "us-east-1",
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
        )
    
    return StorageService(provider)
