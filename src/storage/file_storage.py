"""File storage for uploaded images with tenant isolation."""

from __future__ import annotations

import os
import aiofiles
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from PIL import Image
import io

from src.config import get_settings
from src.logging import get_logger

logger = get_logger(__name__)


class FileStorageError(Exception):
    """File storage operation error."""

    def __init__(self, message: str, error_code: str = "STORAGE_FAILURE"):
        super().__init__(message)
        self.error_code = error_code


class FileStorage:
    """
    Manages file storage for uploaded plan images.

    Storage structure (tenant-isolated):
        {base_dir}/
            {tenant_id}/
                {project_id}/
                    {page_uuid}.png
    """

    ALLOWED_MIME_TYPES = {"image/png"}

    def __init__(self, base_dir: Optional[str] = None, tenant_id: Optional[UUID] = None):
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.upload_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.tenant_id = tenant_id

        # Use settings for limits
        self.max_file_size = settings.max_upload_size_bytes
        self.max_dimension = settings.max_image_dimension

    def _get_tenant_dir(self, tenant_id: Optional[UUID] = None) -> Path:
        """Get the directory for a tenant's files."""
        tid = tenant_id or self.tenant_id
        if tid:
            tenant_dir = self.base_dir / str(tid)
        else:
            # Backwards compatibility: use 'default' tenant
            tenant_dir = self.base_dir / "default"
        tenant_dir.mkdir(parents=True, exist_ok=True)
        return tenant_dir

    def _get_project_dir(self, project_id: UUID, tenant_id: Optional[UUID] = None) -> Path:
        """Get the directory for a project's files."""
        tenant_dir = self._get_tenant_dir(tenant_id)
        project_dir = tenant_dir / str(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    async def save_image(
        self,
        project_id: UUID,
        content: bytes,
        content_type: str,
        tenant_id: Optional[UUID] = None,
    ) -> str:
        """
        Save an uploaded image with validation.

        Args:
            project_id: The project ID
            content: Raw image bytes
            content_type: MIME type of the image
            tenant_id: Optional tenant ID for scoped storage

        Returns:
            Relative path to the saved file

        Raises:
            FileStorageError: If validation fails
        """
        tid = tenant_id or self.tenant_id

        # Validate MIME type
        if content_type not in self.ALLOWED_MIME_TYPES:
            raise FileStorageError(
                f"Invalid file type: {content_type}. Only PNG images are allowed.",
                error_code="INVALID_IMAGE_FORMAT",
            )

        # Validate file size
        if len(content) > self.max_file_size:
            raise FileStorageError(
                f"File too large: {len(content)} bytes. Maximum is {self.max_file_size} bytes.",
                error_code="FILE_TOO_LARGE",
            )

        # Validate it's actually a valid PNG and check dimensions
        try:
            img = Image.open(io.BytesIO(content))
            if img.format != "PNG":
                raise FileStorageError(
                    f"File is not a valid PNG image. Detected format: {img.format}",
                    error_code="INVALID_IMAGE_FORMAT",
                )

            # Check image dimensions
            width, height = img.size
            if width > self.max_dimension or height > self.max_dimension:
                raise FileStorageError(
                    f"Image dimensions too large: {width}x{height}. "
                    f"Maximum dimension is {self.max_dimension}px.",
                    error_code="IMAGE_DIMENSION_EXCEEDED",
                )

            logger.debug(
                "image_validated",
                project_id=str(project_id),
                tenant_id=str(tid) if tid else None,
                width=width,
                height=height,
                size_bytes=len(content),
            )

        except FileStorageError:
            raise
        except Exception as e:
            raise FileStorageError(
                f"Invalid image file: {e}",
                error_code="INVALID_IMAGE_FORMAT",
            )

        # Generate unique filename
        file_id = uuid4()
        filename = f"{file_id}.png"
        project_dir = self._get_project_dir(project_id, tid)
        file_path = project_dir / filename

        # Save the file
        try:
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)
        except Exception as e:
            logger.error(
                "file_save_failed",
                project_id=str(project_id),
                error=str(e),
            )
            raise FileStorageError(
                f"Failed to save file: {e}",
                error_code="STORAGE_FAILURE",
            )

        # Return relative path (includes tenant_id for isolation)
        return str(file_path.relative_to(self.base_dir))

    async def get_image_path(self, relative_path: str) -> Path:
        """Get the absolute path to a stored image."""
        abs_path = self.base_dir / relative_path

        # Security: ensure path doesn't escape base directory
        try:
            abs_path = abs_path.resolve()
            self.base_dir.resolve()
            if not str(abs_path).startswith(str(self.base_dir.resolve())):
                raise FileStorageError(
                    "Invalid file path",
                    error_code="STORAGE_FAILURE",
                )
        except Exception as e:
            if isinstance(e, FileStorageError):
                raise
            raise FileStorageError(
                "Invalid file path",
                error_code="STORAGE_FAILURE",
            )

        if not abs_path.exists():
            raise FileStorageError(
                f"Image not found: {relative_path}",
                error_code="FILE_NOT_FOUND",
            )
        return abs_path

    async def read_image_bytes(self, relative_path: str) -> bytes:
        """Read an image file and return its bytes."""
        abs_path = await self.get_image_path(relative_path)
        async with aiofiles.open(abs_path, "rb") as f:
            return await f.read()

    async def delete_project_files(
        self,
        project_id: UUID,
        tenant_id: Optional[UUID] = None,
    ) -> None:
        """Delete all files for a project."""
        tid = tenant_id or self.tenant_id
        if tid:
            project_dir = self.base_dir / str(tid) / str(project_id)
        else:
            project_dir = self.base_dir / "default" / str(project_id)

        if project_dir.exists():
            shutil.rmtree(project_dir)
            logger.info(
                "project_files_deleted",
                project_id=str(project_id),
                tenant_id=str(tid) if tid else None,
            )

    async def cleanup_old_files(self, max_age_days: int = 30) -> int:
        """
        Clean up files older than max_age_days.

        Returns the number of directories cleaned up.
        """
        cutoff = datetime.now() - timedelta(days=max_age_days)
        cleaned = 0

        for tenant_dir in self.base_dir.iterdir():
            if not tenant_dir.is_dir():
                continue

            for project_dir in tenant_dir.iterdir():
                if not project_dir.is_dir():
                    continue

                # Check modification time of directory
                mtime = datetime.fromtimestamp(project_dir.stat().st_mtime)
                if mtime < cutoff:
                    shutil.rmtree(project_dir)
                    cleaned += 1
                    logger.info(
                        "old_project_cleaned",
                        project_dir=str(project_dir),
                        age_days=(datetime.now() - mtime).days,
                    )

        return cleaned

    def get_storage_stats(self) -> dict:
        """Get storage statistics."""
        total_files = 0
        total_size = 0
        tenant_count = 0

        for tenant_dir in self.base_dir.iterdir():
            if not tenant_dir.is_dir():
                continue
            tenant_count += 1

            for project_dir in tenant_dir.iterdir():
                if not project_dir.is_dir():
                    continue

                for file_path in project_dir.iterdir():
                    if file_path.is_file():
                        total_files += 1
                        total_size += file_path.stat().st_size

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "tenant_count": tenant_count,
        }
