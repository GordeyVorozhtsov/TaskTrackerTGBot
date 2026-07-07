import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import TelegramUser
from app.core.application import Application
from app.infra.logger import log_action
from app.repositories.board_repository import BoardRepository
from app.repositories.comment_repository import CommentRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas import AddMemberRequest, BoardCreate, BoardUpdate
from app.services.access import ensure_board_member, ensure_board_owner

logger = logging.getLogger("app.services.board_service")


class BoardService:
    def __init__(self, session: AsyncSession, application: Application) -> None:
        self._session = session
        self._application = application
        self._boards = BoardRepository(session)
        self._comments = CommentRepository(session)
        self._tasks = TaskRepository(session)
        self._users = UserRepository(session)

    async def list_boards(self, current_user: TelegramUser):
        await self._users.upsert_from_telegram(current_user)
        boards = await self._boards.list_for_user(current_user.id)
        logger.debug("Listed boards | user_id=%s count=%s", current_user.id, len(boards))
        return boards

    async def create_board(self, current_user: TelegramUser, data: BoardCreate):
        user = await self._users.upsert_from_telegram(current_user)
        board = await self._boards.create(data.title, user.id)
        await self._boards.add_member(board.id, user.id)
        log_action(logger, "board.create", user_id=user.id, board_id=board.id, title=data.title)
        return board

    async def update_board(self, current_user: TelegramUser, board_id: int, data: BoardUpdate):
        board = await ensure_board_owner(self._boards, board_id, current_user.id)
        updated = await self._boards.update_title(board, data.title)
        log_action(
            logger,
            "board.update",
            user_id=current_user.id,
            board_id=board_id,
            title=data.title,
        )
        return updated

    async def delete_board(self, current_user: TelegramUser, board_id: int) -> None:
        board = await ensure_board_owner(self._boards, board_id, current_user.id)
        comment_paths = await self._comments.list_image_paths_for_board(board_id)
        task_paths = await self._tasks.list_description_image_paths_for_board(board_id)
        image_paths = comment_paths + task_paths
        await self._boards.delete(board)
        self._application.storage.delete_uploads(image_paths)
        log_action(
            logger,
            "board.delete",
            user_id=current_user.id,
            board_id=board_id,
            uploads_removed=len(image_paths),
        )

    async def get_board_detail(self, current_user: TelegramUser, board_id: int):
        await ensure_board_member(self._boards, board_id, current_user.id)
        board = await self._boards.get_with_details(board_id)
        if board is None:
            logger.warning("Board not found | board_id=%s user_id=%s", board_id, current_user.id)
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Board not found")
        logger.debug(
            "Board detail | board_id=%s user_id=%s tasks=%s members=%s",
            board_id,
            current_user.id,
            len(board.tasks),
            len(board.members),
        )
        return board

    async def add_member(self, current_user: TelegramUser, board_id: int, data: AddMemberRequest):
        await ensure_board_member(self._boards, board_id, current_user.id)

        if data.user_id is None and not data.username:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide username or user_id")

        if data.user_id is not None:
            user = await self._users.get_by_id(data.user_id)
        else:
            user = await self._users.get_by_username(data.username)  # type: ignore[arg-type]

        if user is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "User not found. They must open the mini app at least once.",
            )

        if await self._boards.is_member(board_id, user.id):
            raise HTTPException(status.HTTP_409_CONFLICT, "User is already a member")

        await self._boards.add_member(board_id, user.id)
        member = await self._boards.get_member(board_id, user.id)
        if member is None:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to add member")

        log_action(
            logger,
            "board.member.add",
            user_id=current_user.id,
            board_id=board_id,
            member_user_id=user.id,
        )
        return member

    async def list_members(self, current_user: TelegramUser, board_id: int):
        await ensure_board_member(self._boards, board_id, current_user.id)
        return await self._boards.list_members(board_id)

    async def remove_member(
        self, current_user: TelegramUser, board_id: int, member_id: int
    ) -> None:
        board = await ensure_board_owner(self._boards, board_id, current_user.id)

        member = await self._boards.get_member_by_id(member_id)
        if member is None or member.board_id != board_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

        if member.user_id == board.owner_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove board owner")

        await self._boards.remove_member(member)
        log_action(
            logger,
            "board.member.remove",
            user_id=current_user.id,
            board_id=board_id,
            member_id=member_id,
            member_user_id=member.user_id,
        )
