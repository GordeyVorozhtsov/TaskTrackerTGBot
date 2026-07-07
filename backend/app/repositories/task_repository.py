from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import flush_and_refresh
from app.models.task import Task, TaskStatus


def _status_value(status: TaskStatus | str) -> str:
    return status.value if isinstance(status, TaskStatus) else str(status)


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, task_id: int) -> Task | None:
        return await self._session.get(Task, task_id)

    async def list_description_image_paths_for_board(self, board_id: int) -> list[str]:
        result = await self._session.execute(
            select(Task.description_image_path).where(
                Task.board_id == board_id,
                Task.description_image_path.is_not(None),
            )
        )
        return list(result.scalars().all())

    async def create(
        self,
        board_id: int,
        title: str,
        created_by: int,
        status: TaskStatus = TaskStatus.NEW,
        description: str | None = None,
        description_image_path: str | None = None,
        deadline=None,
    ) -> Task:
        task = Task(
            board_id=board_id,
            title=title,
            description=description,
            description_image_path=description_image_path,
            created_by=created_by,
            status=_status_value(status),
            deadline=deadline,
        )
        self._session.add(task)
        await flush_and_refresh(self._session, task)
        return task

    async def update(self, task: Task, **fields) -> Task:
        if fields.get("status") is not None:
            fields["status"] = _status_value(fields["status"])
        for key, value in fields.items():
            if value is not None or key in ("deadline", "description", "description_image_path"):
                setattr(task, key, value)
        await flush_and_refresh(self._session, task)
        return task

    async def delete(self, task: Task) -> None:
        await self._session.delete(task)
