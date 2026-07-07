from starlette.responses import Response
from starlette.staticfiles import StaticFiles


class NoCacheStaticFiles(StaticFiles):
    """Serve static assets without aggressive caching (important for Telegram WebView)."""

    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200 and not path.startswith("api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response
