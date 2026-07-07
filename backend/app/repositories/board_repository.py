from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infra.database import flush_and_refresh
from app.models.board import Board, BoardMember


class BoardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: int) -> list[Board]:
        result = await self._session.execute(
            select(Board)
            .join(BoardMember, BoardMember.board_id == Board.id)
            .where(BoardMember.user_id == user_id)
            .order_by(Board.created_at.desc())
        )
        return list(result.scalars().unique().all())

    async def get_by_id(self, board_id: int) -> Board | None:
        return await self._session.get(Board, board_id)

    async def get_with_details(self, board_id: int) -> Board | None:
        result = await self._session.execute(
            select(Board)
            .where(Board.id == board_id)
            .options(
                selectinload(Board.members).selectinload(BoardMember.user),
                selectinload(Board.tasks),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, title: str, owner_id: int) -> Board:
        board = Board(title=title, owner_id=owner_id)
        self._session.add(board)
        await flush_and_refresh(self._session, board)
        return board

    async def update_title(self, board: Board, title: str) -> Board:
        board.title = title
        await flush_and_refresh(self._session, board)
        return board

    async def delete(self, board: Board) -> None:
        await self._session.delete(board)

    async def is_member(self, board_id: int, user_id: int) -> bool:
        result = await self._session.execute(
            select(BoardMember.id).where(
                BoardMember.board_id == board_id,
                BoardMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def add_member(self, board_id: int, user_id: int) -> BoardMember:
        member = BoardMember(board_id=board_id, user_id=user_id)
        self._session.add(member)
        await self._session.flush()
        return member

    async def get_member(self, board_id: int, user_id: int) -> BoardMember | None:
        result = await self._session.execute(
            select(BoardMember)
            .where(BoardMember.board_id == board_id, BoardMember.user_id == user_id)
            .options(selectinload(BoardMember.user))
        )
        return result.scalar_one_or_none()

    async def get_member_by_id(self, member_id: int) -> BoardMember | None:
        result = await self._session.execute(
            select(BoardMember)
            .where(BoardMember.id == member_id)
            .options(selectinload(BoardMember.user))
        )
        return result.scalar_one_or_none()

    async def list_members(self, board_id: int) -> list[BoardMember]:
        result = await self._session.execute(
            select(BoardMember)
            .where(BoardMember.board_id == board_id)
            .options(selectinload(BoardMember.user))
            .order_by(BoardMember.added_at)
        )
        return list(result.scalars().all())

    async def remove_member(self, member: BoardMember) -> None:
        await self._session.delete(member)
