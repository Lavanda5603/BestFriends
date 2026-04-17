import io
import uuid
from pathlib import Path
from datetime import timedelta
from minio import Minio
from minio.error import S3Error
from loguru import logger
from app.core.config import settings


class StorageService:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            logger.error(f"MinIO: {e}")
            raise

    def upload_file(self, data: bytes, filename: str, mime_type: str, prefix: str = "") -> str:
        ext = Path(filename).suffix
        name = f"{prefix}/{uuid.uuid4()}{ext}".lstrip("/")
        self.client.put_object(self.bucket, name, io.BytesIO(data), length=len(data), content_type=mime_type)
        return name

    def download_file(self, storage_path: str) -> bytes:
        r = self.client.get_object(self.bucket, storage_path)
        try:
            return r.read()
        finally:
            r.close()
            r.release_conn()

    def get_presigned_url(self, storage_path: str, expires_seconds: int = 3600) -> str:
        return self.client.presigned_get_object(self.bucket, storage_path, expires=timedelta(seconds=expires_seconds))

    def delete_file(self, storage_path: str):
        try:
            self.client.remove_object(self.bucket, storage_path)
        except S3Error as e:
            logger.warning(f"Delete failed {storage_path}: {e}")


storage_service = StorageService()
