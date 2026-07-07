import logging
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import TelegramUser
from app.core.application import Application
from app.infra.logger import log_action
from app.infra.upload_signing import UploadSigning
from app.models.task import Task, TaskStatus
from app.repositories.board_repository import BoardRepository
from app.repositories.comment_repository import CommentRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas import CommentOut, TaskCreate, TaskOut, TaskUpdate, UserOut
from app.services.access import ensure_board_member, get_task_for_member

logger = logging.getLogger("app.services.task_service")


def _normalize_description(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def task_to_out(task: Task, upload_signing: UploadSigning) -> TaskOut:
    image_url = None
    if task.description_image_path:
        image_url = upload_signing.build_url(task.description_image_path)
    return TaskOut(
        id=task.id,
        board_id=task.board_id,
        title=task.title,
        description=task.description,
        description_image_url=image_url,
        status=TaskStatus(task.status),
        deadline=task.deadline,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


class TaskService:
    def __init__(self, session: AsyncSession, application: Application) -> None:
        self._session = session
        self._application = application
        self._tasks = TaskRepository(session)
        self._boards = BoardRepository(session)
        self._comments = CommentRepository(session)
        self._users = UserRepository(session)

    def _comment_to_out(self, comment) -> CommentOut:
        image_url = None
        if comment.image_path:
            image_url = self._application.upload_signing.build_url(comment.image_path)
        return CommentOut(
            id=comment.id,
            task_id=comment.task_id,
            user_id=comment.user_id,
            user=UserOut.model_validate(comment.user),
            text=comment.text,
            image_url=image_url,
            created_at=comment.created_at,
            edited_at=comment.edited_at,
        )

    async def create_task(
        self,
        current_user: TelegramUser,
        board_id: int,
        data: TaskCreate,
        description_image: UploadFile | None = None,
    ) -> TaskOut:
        await self._users.upsert_from_telegram(current_user)
        await ensure_board_member(self._boards, board_id, current_user.id)

        image_path = None
        if description_image is not None:
            image_path = await self._application.storage.save_comment_image(description_image)

        task = await self._tasks.create(
            board_id=board_id,
            title=data.title,
            description=_normalize_description(data.description),
            description_image_path=image_path,
            created_by=current_user.id,
            status=data.status,
            deadline=data.deadline,
        )
        log_action(
            logger,
            "task.create",
            user_id=current_user.id,
            board_id=board_id,
            task_id=task.id,
            status=data.status.value,
            title=data.title,
            has_description_image=bool(image_path),
        )
        return task_to_out(task, self._application.upload_signing)

    async def get_task(self, current_user: TelegramUser, task_id: int) -> TaskOut:
        task = await get_task_for_member(self._session, task_id, current_user.id)
        return task_to_out(task, self._application.upload_signing)

    async def update_task(
        self,
        current_user: TelegramUser,
        task_id: int,
        data: TaskUpdate,
        description_image: UploadFile | None = None,
        remove_description_image: bool = False,
    ) -> TaskOut:
        task = await get_task_for_member(self._session, task_id, current_user.id)

        update_fields = data.model_dump(exclude_unset=True)
        if "description" in update_fields:
            update_fields["description"] = _normalize_description(update_fields["description"])

        old_image_path = task.description_image_path
        if remove_description_image:
            update_fields["description_image_path"] = None
        elif description_image is not None:
            update_fields["description_image_path"] = await self._application.storage.save_comment_image(
                description_image
            )

        updated = await self._tasks.update(task, **update_fields)

        new_image_path = updated.description_image_path
        if old_image_path and old_image_path != new_image_path:
            self._application.storage.delete_upload(old_image_path)

        log_action(
            logger,
            "task.update",
            user_id=current_user.id,
            task_id=task_id,
            board_id=task.board_id,
            fields=",".join(update_fields.keys()),
        )
        return task_to_out(updated, self._application.upload_signing)

    async def delete_task(self, current_user: TelegramUser, task_id: int) -> None:
        task = await get_task_for_member(self._session, task_id, current_user.id)
        image_paths = await self._comments.list_image_paths_for_task(task_id)
        if task.description_image_path:
            image_paths.append(task.description_image_path)
        await self._tasks.delete(task)
        self._application.storage.delete_uploads(image_paths)
        log_action(
            logger,
            "task.delete",
            user_id=current_user.id,
            task_id=task_id,
            board_id=task.board_id,
            uploads_removed=len(image_paths),
        )

    async def list_comments(self, current_user: TelegramUser, task_id: int):
        await get_task_for_member(self._session, task_id, current_user.id)
        comments = await self._comments.list_for_task(task_id)
        return [self._comment_to_out(c) for c in comments]

    async def add_comment(
        self,
        current_user: TelegramUser,
        task_id: int,
        text: str,
        image: UploadFile | None = None,
    ):
        await self._users.upsert_from_telegram(current_user)
        await get_task_for_member(self._session, task_id, current_user.id)

        normalized_text = text.strip()
        if not normalized_text and image is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Comment text or image is required")

        image_path = None
        if image is not None:
            image_path = await self._application.storage.save_comment_image(image)

        comment = await self._comments.create(
            task_id,
            current_user.id,
            normalized_text,
            image_path=image_path,
        )
        log_action(
            logger,
            "comment.create",
            user_id=current_user.id,
            task_id=task_id,
            comment_id=comment.id,
            has_image=bool(image_path),
            text_len=len(normalized_text),
        )
        return self._comment_to_out(comment)

    async def update_comment(
        self,
        current_user: TelegramUser,
        task_id: int,
        comment_id: int,
        text: str,
        image: UploadFile | None = None,
        remove_image: bool = False,
    ):
        await get_task_for_member(self._session, task_id, current_user.id)
        comment = await self._comments.get_by_id(comment_id)
        if comment is None or comment.task_id != task_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")

        if comment.user_id != current_user.id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only comment author can edit this comment",
            )

        normalized_text = text.strip()
        old_image_path = comment.image_path
        image_path = old_image_path

        if remove_image:
            image_path = None
        elif image is not None:
            image_path = await self._application.storage.save_comment_image(image)

        if not normalized_text and image_path is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Comment text or image is required")

        updated = await self._comments.update(
            comment,
            text=normalized_text,
            image_path=image_path,
            edited_at=datetime.now(timezone.utc),
        )

        if old_image_path and old_image_path != image_path:
            self._application.storage.delete_upload(old_image_path)

        log_action(
            logger,
            "comment.update",
            user_id=current_user.id,
            task_id=task_id,
            comment_id=comment_id,
            has_image=bool(image_path),
            text_len=len(normalized_text),
        )
        return self._comment_to_out(updated)

    async def delete_comment(
        self, current_user: TelegramUser, task_id: int, comment_id: int
    ) -> None:
        await get_task_for_member(self._session, task_id, current_user.id)
        comment = await self._comments.get_by_id(comment_id)
        if comment is None or comment.task_id != task_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")

        if comment.user_id != current_user.id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only comment author can delete this comment",
            )

        image_path = comment.image_path
        await self._comments.delete(comment)
        self._application.storage.delete_upload(image_path)
        log_action(
            logger,
            "comment.delete",
            user_id=current_user.id,
            task_id=task_id,
            comment_id=comment_id,
            had_image=bool(image_path),
        )
