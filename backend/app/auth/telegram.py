import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException, status

from app.core.config import Settings


@dataclass(frozen=True)
class TelegramUser:
    id: int
    username: str | None
    first_name: str
    last_name: str | None


class TelegramAuth:
    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger

    def _validate_init_data(
        self, init_data: str, bot_token: str, max_age_seconds: int = 86400
    ) -> dict:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing hash in init data")

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid init data signature")

        auth_date = int(parsed.get("auth_date", "0"))
        if time.time() - auth_date > max_age_seconds:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Init data expired")

        return parsed

    def parse_user(self, init_data: str) -> TelegramUser:
        if not self.settings.bot_token:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "BOT_TOKEN is not configured",
            )

        parsed = self._validate_init_data(init_data, self.settings.bot_token)
        user_raw = parsed.get("user")
        if not user_raw:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User data missing in init data")

        user = json.loads(user_raw)
        return TelegramUser(
            id=int(user["id"]),
            username=user.get("username"),
            first_name=user.get("first_name", "User"),
            last_name=user.get("last_name"),
        )

    async def get_current_user(
        self,
        x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
        x_dev_user_id: int | None = Header(default=None, alias="X-Dev-User-Id"),
    ) -> TelegramUser:
        if x_telegram_init_data:
            return self.parse_user(x_telegram_init_data)

        if self.settings.debug and x_dev_user_id:
            self.logger.debug("Dev auth | user_id=%s", x_dev_user_id)
            return TelegramUser(
                id=x_dev_user_id,
                username="devuser",
                first_name="Dev",
                last_name="User",
            )

        self.logger.warning("Authentication required | path auth failed")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
