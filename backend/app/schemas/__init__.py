from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskStatus


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str | None
    first_name: str
    last_name: str | None = None


class BoardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class BoardUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class BoardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    owner_id: int
    created_at: datetime


class BoardMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    user: UserOut
    added_at: datetime


class AddMemberRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=255)
    user_id: int | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus = TaskStatus.NEW
    deadline: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    deadline: datetime | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    title: str
    description: str | None = None
    description_image_url: str | None = None
    status: TaskStatus
    deadline: datetime | None
    created_by: int
    created_at: datetime
    updated_at: datetime


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    user_id: int
    user: UserOut
    text: str
    image_url: str | None = None
    created_at: datetime
    edited_at: datetime | None = None


class BoardDetailOut(BaseModel):
    board: BoardOut
    members: list[BoardMemberOut]
    tasks: list[TaskOut]
