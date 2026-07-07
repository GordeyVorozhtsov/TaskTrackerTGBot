import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.board_repository import BoardRepository
from app.repositories.task_repository import TaskRepository

logger = logging.getLogger("app.services.access")


async def ensure_board_member(
    boards: BoardRepository, board_id: int, user_id: int
) -> None:
    if not await boards.is_member(board_id, user_id):
        logger.warning("Access denied | board_id=%s user_id=%s", board_id, user_id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a board member")


async def ensure_board_owner(
    boards: BoardRepository, board_id: int, user_id: int
):
    board = await boards.get_by_id(board_id)
    if board is None:
        logger.warning("Board not found | board_id=%s user_id=%s", board_id, user_id)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Board not found")
    if board.owner_id != user_id:
        logger.warning(
            "Board owner required | board_id=%s user_id=%s owner_id=%s",
            board_id,
            user_id,
            board.owner_id,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only board owner can perform this action")
    return board


async def get_task_for_member(
    session: AsyncSession, task_id: int, user_id: int
) -> Task:
    tasks = TaskRepository(session)
    boards = BoardRepository(session)

    task = await tasks.get_by_id(task_id)
    if task is None:
        logger.warning("Task not found | task_id=%s user_id=%s", task_id, user_id)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")

    await ensure_board_member(boards, task.board_id, user_id)
    return task
