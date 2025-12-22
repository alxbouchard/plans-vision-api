"""File storage for uploaded images."""

from __future__ import annotations

import os
import aiofiles
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from PIL import Image
import io

from src.config import get_settings


class FileStorageError(Exception):
    """File storage operation error."""
    pass


class FileStorage:
    """Manages file storage for uploaded plan images."""

    ALLOWED_MIME_TYPES = {"image/png"}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

    def __init__(self, base_dir: Optional[str] = None):
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.upload_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_project_dir(self, project_id: UUID) -> Path:
        """Get the directory for a project's files."""
        project_dir = self.base_dir / str(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    async def save_image(
        self,
        project_id: UUID,
        content: bytes,
        content_type: str,
    ) -> str:
        """
        Save an uploaded image.

        Args:
            project_id: The project ID
            content: Raw image bytes
            content_type: MIME type of the image

        Returns:
            Relative path to the saved file

        Raises:
            FileStorageError: If validation fails
        """
        # Validate MIME type
        if content_type not in self.ALLOWED_MIME_TYPES:
            raise FileStorageError(
                f"Invalid file type: {content_type}. Only PNG images are allowed."
            )

        # Validate file size
        if len(content) > self.MAX_FILE_SIZE:
            raise FileStorageError(
                f"File too large: {len(content)} bytes. Maximum is {self.MAX_FILE_SIZE} bytes."
            )

        # Validate it's actually a valid PNG
        try:
            img = Image.open(io.BytesIO(content))
            if img.format != "PNG":
                raise FileStorageError(
                    f"File is not a valid PNG image. Detected format: {img.format}"
                )
        except Exception as e:
            if isinstance(e, FileStorageError):
                raise
            raise FileStorageError(f"Invalid image file: {e}")

        # Generate unique filename
        file_id = uuid4()
        filename = f"{file_id}.png"
        project_dir = self._get_project_dir(project_id)
        file_path = project_dir / filename

        # Save the file
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # Return relative path
        return str(file_path.relative_to(self.base_dir))

    async def get_image_path(self, relative_path: str) -> Path:
        """Get the absolute path to a stored image."""
        abs_path = self.base_dir / relative_path
        if not abs_path.exists():
            raise FileStorageError(f"Image not found: {relative_path}")
        return abs_path

    async def read_image_bytes(self, relative_path: str) -> bytes:
        """Read an image file and return its bytes."""
        abs_path = await self.get_image_path(relative_path)
        async with aiofiles.open(abs_path, "rb") as f:
            return await f.read()

    async def delete_project_files(self, project_id: UUID) -> None:
        """Delete all files for a project."""
        import shutil
        project_dir = self.base_dir / str(project_id)
        if project_dir.exists():
            shutil.rmtree(project_dir)
