from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import create_db_dependency
from app.auth import TelegramUser
from app.core.application import Application
from app.schemas import (
    AddMemberRequest,
    BoardCreate,
    BoardDetailOut,
    BoardMemberOut,
    BoardOut,
    BoardUpdate,
    CommentOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    UserOut,
)
from app.models.task import TaskStatus
from app.services.board_service import BoardService
from app.services.task_service import TaskService, task_to_out


def create_api_router(application: Application) -> APIRouter:
    router = APIRouter(prefix="/api")
    limiter = application.rate_limiter.limiter
    settings = application.settings

    get_db = create_db_dependency(application.db)
    get_current_user = application.auth.get_current_user

    def get_board_service(
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> BoardService:
        return BoardService(db, application)

    def get_task_service(
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> TaskService:
        return TaskService(db, application)

    @router.get("/health")
    @limiter.exempt
    async def health_check(request: Request):
        await application.db.ping()
        return {"status": "ok"}

    @router.get("/uploads/{filename}")
    @limiter.limit(settings.rate_limit_uploads)
    async def get_upload(
        request: Request,
        filename: str,
        e: int,
        sig: str,
    ):
        application.upload_signing.verify(filename, e, sig)
        path = application.storage.resolve_upload_path(filename)
        if path is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        return FileResponse(path, media_type="image/jpeg", filename=filename)

    @router.get("/me", response_model=UserOut)
    async def get_me(user: Annotated[TelegramUser, Depends(get_current_user)]):
        return UserOut(
            id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

    @router.get("/boards", response_model=list[BoardOut])
    async def list_boards(
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[BoardService, Depends(get_board_service)],
    ):
        return await service.list_boards(user)

    @router.post("/boards", response_model=BoardOut, status_code=201)
    async def create_board(
        data: BoardCreate,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[BoardService, Depends(get_board_service)],
    ):
        return await service.create_board(user, data)

    @router.get("/boards/{board_id}", response_model=BoardDetailOut)
    async def get_board(
        board_id: int,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[BoardService, Depends(get_board_service)],
    ):
        board = await service.get_board_detail(user, board_id)
        return BoardDetailOut(
            board=BoardOut.model_validate(board),
            members=[BoardMemberOut.model_validate(m) for m in board.members],
            tasks=[task_to_out(t, application.upload_signing) for t in board.tasks],
        )

    @router.patch("/boards/{board_id}", response_model=BoardOut)
    async def update_board(
        board_id: int,
        data: BoardUpdate,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[BoardService, Depends(get_board_service)],
    ):
        return await service.update_board(user, board_id, data)

    @router.delete("/boards/{board_id}", status_code=204)
    async def delete_board(
        board_id: int,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[BoardService, Depends(get_board_service)],
    ):
        await service.delete_board(user, board_id)

    @router.get("/boards/{board_id}/members", response_model=list[BoardMemberOut])
    async def list_members(
        board_id: int,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[BoardService, Depends(get_board_service)],
    ):
        return await service.list_members(user, board_id)

    @router.post("/boards/{board_id}/members", response_model=BoardMemberOut, status_code=201)
    async def add_member(
        board_id: int,
        data: AddMemberRequest,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[BoardService, Depends(get_board_service)],
    ):
        return await service.add_member(user, board_id, data)

    @router.delete("/boards/{board_id}/members/{member_id}", status_code=204)
    async def remove_member(
        board_id: int,
        member_id: int,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[BoardService, Depends(get_board_service)],
    ):
        await service.remove_member(user, board_id, member_id)

    @router.post("/boards/{board_id}/tasks", response_model=TaskOut, status_code=201)
    async def create_task(
        board_id: int,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[TaskService, Depends(get_task_service)],
        title: str = Form(...),
        status: TaskStatus = Form(...),
        description: str = Form(""),
        deadline: str = Form(""),
        description_image: UploadFile | None = File(None),
    ):
        parsed_deadline = deadline.strip() or None
        data = TaskCreate(
            title=title,
            description=description or None,
            status=status,
            deadline=parsed_deadline,
        )
        upload = (
            description_image
            if description_image is not None and description_image.filename
            else None
        )
        return await service.create_task(user, board_id, data, upload)

    @router.get("/tasks/{task_id}", response_model=TaskOut)
    async def get_task(
        task_id: int,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[TaskService, Depends(get_task_service)],
    ):
        return await service.get_task(user, task_id)

    @router.patch("/tasks/{task_id}", response_model=TaskOut)
    async def update_task(
        task_id: int,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[TaskService, Depends(get_task_service)],
        title: str = Form(...),
        status: TaskStatus = Form(...),
        description: str = Form(""),
        deadline: str = Form(""),
        remove_description_image: bool = Form(False),
        description_image: UploadFile | None = File(None),
    ):
        parsed_deadline = deadline.strip() or None
        data = TaskUpdate(
            title=title,
            description=description or None,
            status=status,
            deadline=parsed_deadline,
        )
        upload = (
            description_image
            if description_image is not None and description_image.filename
            else None
        )
        return await service.update_task(
            user,
            task_id,
            data,
            upload,
            remove_description_image=remove_description_image,
        )

    @router.delete("/tasks/{task_id}", status_code=204)
    async def delete_task(
        task_id: int,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[TaskService, Depends(get_task_service)],
    ):
        await service.delete_task(user, task_id)

    @router.get("/tasks/{task_id}/comments", response_model=list[CommentOut])
    async def list_comments(
        task_id: int,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[TaskService, Depends(get_task_service)],
    ):
        return await service.list_comments(user, task_id)

    @router.post("/tasks/{task_id}/comments", response_model=CommentOut, status_code=201)
    @limiter.limit(settings.rate_limit_comments)
    async def add_comment(
        request: Request,
        task_id: int,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[TaskService, Depends(get_task_service)],
        text: str = Form(""),
        image: UploadFile | None = File(None),
    ):
        upload = image if image is not None and image.filename else None
        return await service.add_comment(user, task_id, text, upload)

    @router.patch("/tasks/{task_id}/comments/{comment_id}", response_model=CommentOut)
    @limiter.limit(settings.rate_limit_comments)
    async def update_comment(
        request: Request,
        task_id: int,
        comment_id: int,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[TaskService, Depends(get_task_service)],
        text: str = Form(""),
        remove_image: bool = Form(False),
        image: UploadFile | None = File(None),
    ):
        upload = image if image is not None and image.filename else None
        return await service.update_comment(
            user, task_id, comment_id, text, upload, remove_image
        )

    @router.delete("/tasks/{task_id}/comments/{comment_id}", status_code=204)
    async def delete_comment(
        task_id: int,
        comment_id: int,
        user: Annotated[TelegramUser, Depends(get_current_user)],
        service: Annotated[TaskService, Depends(get_task_service)],
    ):
        await service.delete_comment(user, task_id, comment_id)

    return router
