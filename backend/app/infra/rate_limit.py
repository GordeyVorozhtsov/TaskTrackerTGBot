import json
from urllib.parse import parse_qsl

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import Settings


class RateLimiter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.limiter = Limiter(
            key_func=self._rate_limit_key,
            default_limits=[settings.rate_limit_default],
        )

    @staticmethod
    def _rate_limit_key(request: Request) -> str:
        init_data = request.headers.get("X-Telegram-Init-Data")
        if init_data:
            try:
                parsed = dict(parse_qsl(init_data, keep_blank_values=True))
                user_raw = parsed.get("user")
                if user_raw:
                    user = json.loads(user_raw)
                    return f"user:{user['id']}"
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                pass

        dev_id = request.headers.get("X-Dev-User-Id")
        if dev_id:
            return f"dev:{dev_id}"

        return get_remote_address(request)
