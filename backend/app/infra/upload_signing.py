import hashlib
import hmac
import re
import time
from urllib.parse import urlencode

from fastapi import HTTPException, status

from app.core.config import Settings

_FILENAME_RE = re.compile(r"^[a-f0-9]{32}\.jpg$")


class UploadSigning:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _signing_key(self) -> bytes:
        material = self.settings.bot_token or self.settings.app_name
        return hashlib.sha256(f"upload-sign:{material}".encode()).digest()

    def _compute_signature(self, filename: str, expires: int) -> str:
        message = f"{filename}:{expires}".encode()
        return hmac.new(self._signing_key(), message, hashlib.sha256).hexdigest()

    def build_url(self, filename: str) -> str:
        expires = int(time.time()) + self.settings.upload_sign_ttl_seconds
        sig = self._compute_signature(filename, expires)
        query = urlencode({"e": expires, "sig": sig})
        return f"/api/uploads/{filename}?{query}"

    def verify(self, filename: str, expires: int, signature: str) -> None:
        if not _FILENAME_RE.fullmatch(filename):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")

        if time.time() > expires:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Upload URL expired")

        expected = self._compute_signature(filename, expires)
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid upload URL")
