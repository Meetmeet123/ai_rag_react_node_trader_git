"""
S3-compatible artifact store for model checkpoints.

Supports local MinIO as well as AWS S3. When ``ENABLE_S3_ARTIFACTS`` is True
and an endpoint is configured, checkpoint directories are zipped and uploaded
to the configured bucket. The returned URI is stored in the model registry.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from loguru import logger

from config import settings


class ArtifactStore:
    """Upload and download model checkpoints to/from S3-compatible storage."""

    def __init__(self) -> None:
        self.enabled = settings.ENABLE_S3_ARTIFACTS and settings.S3_ENDPOINT_URL
        self.bucket = settings.S3_BUCKET
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self._client = None

    def _get_client(self):
        """Lazy-import and construct boto3 S3 client."""
        if self._client is not None:
            return self._client
        import boto3
        from botocore.config import Config

        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
            config=Config(signature_version="s3v4"),
        )
        return self._client

    def upload_checkpoint(
        self,
        checkpoint_path: str,
        version_id: int,
    ) -> Optional[str]:
        """Zip ``checkpoint_path`` and upload it under ``version_{version_id}.zip``.

        Returns:
            The S3 URI if successful, otherwise ``None``.
        """
        if not self.enabled:
            return None

        path = Path(checkpoint_path)
        if not path.exists():
            logger.warning("Checkpoint path does not exist: {}", checkpoint_path)
            return None

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                archive_base = Path(tmpdir) / f"version_{version_id}"
                archive_path = shutil.make_archive(str(archive_base), "zip", str(path))
                key = f"version_{version_id}.zip"
                self._get_client().upload_file(archive_path, self.bucket, key)
                uri = f"s3://{self.bucket}/{key}"
                logger.info("Uploaded checkpoint to {}", uri)
                return uri
        except Exception as exc:
            logger.warning("Failed to upload checkpoint to S3: {}", exc)
            return None

    def download_checkpoint(
        self,
        version_id: int,
        destination_dir: str,
    ) -> Optional[str]:
        """Download and extract the checkpoint archive for ``version_id``.

        Returns:
            Path to the extracted checkpoint directory, or ``None`` on failure.
        """
        if not self.enabled:
            return None

        key = f"version_{version_id}.zip"
        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)
        archive_path = dest / f"version_{version_id}.zip"

        try:
            self._get_client().download_file(self.bucket, key, str(archive_path))
            extracted = dest / f"version_{version_id}"
            shutil.unpack_archive(str(archive_path), str(extracted))
            return str(extracted)
        except Exception as exc:
            logger.warning("Failed to download checkpoint from S3: {}", exc)
            return None
