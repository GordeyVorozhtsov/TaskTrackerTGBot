from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False, comment="Telegram user id"
    )
    username: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(255), server_default="User")
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    board_memberships: Mapped[list["BoardMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    owned_boards: Mapped[list["Board"]] = relationship(back_populates="owner")
    created_tasks: Mapped[list["Task"]] = relationship(back_populates="creator")
    comments: Mapped[list["TaskComment"]] = relationship(back_populates="user")
