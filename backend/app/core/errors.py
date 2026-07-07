from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


def format_validation_error(exc: RequestValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ()) if part != "body"]
        field = " → ".join(loc) if loc else "запрос"
        msg = err.get("msg", "некорректное значение")
        parts.append(f"{field}: {msg}")
    return "; ".join(parts) if parts else "Некорректные данные запроса"


def user_facing_error(exc: Exception, *, debug: bool) -> str:
    if debug:
        return str(exc) or exc.__class__.__name__

    if isinstance(exc, IntegrityError):
        return "Запись уже существует или нарушены ограничения базы данных."

    if isinstance(exc, SQLAlchemyError):
        return "Ошибка базы данных. Попробуйте позже."

    return "Не удалось выполнить операцию. Попробуйте позже."
