import logging
import re
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps

from app.core.config import Settings
from app.core.paths import PROJECT_ROOT

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
UPLOAD_FILENAME_RE = re.compile(r"^[a-f0-9]{32}\.jpg$")
LEGACY_UPLOADS_DIR = PROJECT_ROOT / "uploads"
MAX_IMAGE_DIMENSION = 1024
JPEG_QUALITY = 75
READ_CHUNK_SIZE = 64 * 1024

Image.MAX_IMAGE_PIXELS = 12_000_000


class Storage:
    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger

    def uploads_dir(self) -> Path:
        path = self.settings.uploads_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    def upload_search_dirs(self) -> list[Path]:
        primary = self.uploads_dir()
        dirs = [primary]
        if LEGACY_UPLOADS_DIR != primary and LEGACY_UPLOADS_DIR.is_dir():
            dirs.append(LEGACY_UPLOADS_DIR)
        return dirs

    @staticmethod
    def normalize_filename(filename: str | None) -> str | None:
        if not filename:
            return None
        name = Path(filename).name
        if not UPLOAD_FILENAME_RE.fullmatch(name):
            return None
        return name

    def resolve_upload_path(self, filename: str) -> Path | None:
        name = self.normalize_filename(filename)
        if name is None:
            return None
        for directory in self.upload_search_dirs():
            path = directory / name
            if path.is_file():
                return path
        return None

    async def read_upload_with_limit(self, upload: UploadFile, max_size: int) -> bytes:
        chunks: list[bytes] = []
        total = 0

        while True:
            chunk = await upload.read(READ_CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > max_size:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"Image is too large (max {max_size // (1024 * 1024)} MB)",
                )
            chunks.append(chunk)

        return b"".join(chunks)

    def compress_image(self, data: bytes) -> bytes:
        with Image.open(BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                alpha = img.convert("RGBA").split()[-1] if img.mode in ("RGBA", "LA") else None
                rgb = img.convert("RGBA")
                background.paste(rgb, mask=alpha or rgb.split()[-1])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)

            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            return buffer.getvalue()

    async def save_comment_image(self, image: UploadFile) -> str:
        content_type = (image.content_type or "").split(";", 1)[0].strip().lower()
        data = await self.read_upload_with_limit(image, self.settings.max_upload_size)
        if not data:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty image file")

        if content_type not in ALLOWED_IMAGE_TYPES:
            if content_type not in ("application/octet-stream", ""):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported image type")

        try:
            compressed = self.compress_image(data)
        except Exception as exc:
            self.logger.warning("Image compression failed | error=%s", exc)
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid image file") from exc

        filename = f"{uuid4().hex}.jpg"
        path = self.uploads_dir() / filename
        path.write_bytes(compressed)
        self.logger.info("Image saved | filename=%s size=%s", filename, len(compressed))
        return filename

    def delete_upload(self, filename: str | None) -> None:
        name = self.normalize_filename(filename)
        if name is None:
            if filename:
                self.logger.warning("Skipped unsafe upload delete | filename=%s", filename)
            return

        path = self.resolve_upload_path(name)
        if path is None:
            self.logger.warning("Upload file not found for delete | filename=%s", name)
            return

        path.unlink()
        self.logger.info("Upload deleted | filename=%s path=%s", name, path)

    def delete_uploads(self, filenames: Iterable[str | None]) -> None:
        seen: set[str] = set()
        for filename in filenames:
            if not filename or filename in seen:
                continue
            seen.add(filename)
            self.delete_upload(filename)
