from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import TaskComment
from app.models.task import Task


class CommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _load_with_user(self, comment_id: int) -> TaskComment:
        result = await self._session.execute(
            select(TaskComment)
            .where(TaskComment.id == comment_id)
            .options(selectinload(TaskComment.user))
        )
        comment = result.scalar_one_or_none()
        if comment is None:
            raise RuntimeError(f"Comment {comment_id} not found after save")
        return comment

    async def list_for_task(self, task_id: int) -> list[TaskComment]:
        result = await self._session.execute(
            select(TaskComment)
            .where(TaskComment.task_id == task_id)
            .options(selectinload(TaskComment.user))
            .order_by(TaskComment.created_at)
        )
        return list(result.scalars().all())

    async def create(
        self,
        task_id: int,
        user_id: int,
        text: str,
        image_path: str | None = None,
    ) -> TaskComment:
        comment = TaskComment(
            task_id=task_id,
            user_id=user_id,
            text=text,
            image_path=image_path,
        )
        self._session.add(comment)
        await self._session.flush()
        return await self._load_with_user(comment.id)

    async def get_by_id(self, comment_id: int) -> TaskComment | None:
        return await self._session.get(TaskComment, comment_id)

    async def update(
        self,
        comment: TaskComment,
        *,
        text: str,
        image_path: str | None,
        edited_at,
    ) -> TaskComment:
        comment.text = text
        comment.image_path = image_path
        comment.edited_at = edited_at
        await self._session.flush()
        return await self._load_with_user(comment.id)

    async def delete(self, comment: TaskComment) -> None:
        await self._session.delete(comment)

    async def list_image_paths_for_task(self, task_id: int) -> list[str]:
        result = await self._session.execute(
            select(TaskComment.image_path).where(
                TaskComment.task_id == task_id,
                TaskComment.image_path.is_not(None),
            )
        )
        return list(result.scalars().all())

    async def list_image_paths_for_board(self, board_id: int) -> list[str]:
        result = await self._session.execute(
            select(TaskComment.image_path)
            .join(Task, Task.id == TaskComment.task_id)
            .where(
                Task.board_id == board_id,
                TaskComment.image_path.is_not(None),
            )
        )
        return list(result.scalars().all())
