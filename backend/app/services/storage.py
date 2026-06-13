from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageProvider:
    async def upload_file(
        self,
        *,
        bucket: str,
        prefix: str,
        file: UploadFile,
    ) -> str:
        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parents[2] / ".local_storage"

    async def upload_file(
        self,
        *,
        bucket: str,
        prefix: str,
        file: UploadFile,
    ) -> str:
        suffix = Path(file.filename or "upload.bin").suffix
        object_name = f"{prefix.strip('/')}/{uuid4().hex}{suffix}"
        target = self.base_dir / bucket / object_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(await file.read())
        return f"local://{bucket}/{object_name}"


class SupabaseStorageProvider(StorageProvider):
    def __init__(self) -> None:
        from supabase import create_client

        self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

    async def upload_file(
        self,
        *,
        bucket: str,
        prefix: str,
        file: UploadFile,
    ) -> str:
        suffix = Path(file.filename or "upload.bin").suffix
        object_name = f"{prefix.strip('/')}/{uuid4().hex}{suffix}"
        data = await file.read()
        self.client.storage.from_(bucket).upload(
            object_name,
            data,
            file_options={"content-type": file.content_type or "application/octet-stream"},
        )
        public = self.client.storage.from_(bucket).get_public_url(object_name)
        return str(public)


def get_storage_provider() -> StorageProvider:
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
        try:
            return SupabaseStorageProvider()
        except Exception as exc:
            logger.warning("Supabase Storage unavailable; using local fallback: %s", exc)
    return LocalStorageProvider()
