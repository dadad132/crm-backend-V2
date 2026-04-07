from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.api.deps import get_current_user_id, get_db
from app.models.project import Project
from app.models.user import User
from app.models.task import Task, TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"]) 


@router.post("/", response_model=TaskRead, status_code=201)
async def create_task(
    data: TaskCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Ensure project belongs to user's workspace
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    result = await db.execute(select(Project).where(Project.id == data.project_id, Project.workspace_id == user.workspace_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = Task(
        title=data.title,
        description=data.description,
        status=data.status or Task.status.default,
        priority=data.priority or Task.priority.default,
        due_date=data.due_date,
        project_id=data.project_id,
        creator_id=user_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    # Auto-assign task to creator if they're not an admin
    if not user.is_admin:
        from app.models.assignment import Assignment
        assignment = Assignment(task_id=task.id, assignee_id=user_id, assigner_id=user_id)
        db.add(assignment)
        await db.commit()
    
    return task


@router.get("/", response_model=list[TaskRead])
async def list_tasks(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    project_id: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    due_before: Optional[date] = Query(None),
    sort: Optional[str] = Query("-created_at"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    # Convert empty strings to None for integer filters
    project_id_int = int(project_id) if project_id and project_id.strip() else None
    assignee_id_int = int(assignee_id) if assignee_id and assignee_id.strip() else None
    
    # Limit tasks to projects in the user's workspace
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    stmt = select(Task).join(Project, Task.project_id == Project.id).where(Project.workspace_id == user.workspace_id)
    if project_id_int:
        stmt = stmt.where(Task.project_id == project_id_int)
    if assignee_id_int:
        from app.models.assignment import Assignment
        stmt = stmt.join(Assignment, Assignment.task_id == Task.id).where(Assignment.assignee_id == assignee_id_int)
    if status:
        stmt = stmt.where(col(Task.status) == status)
    if priority:
        stmt = stmt.where(col(Task.priority) == priority)
    if due_before:
        stmt = stmt.where(col(Task.due_date) <= due_before)
    if sort:
        order = desc if sort.startswith("-") else asc
        field = sort.lstrip("-")
        if field == "created_at":
            stmt = stmt.order_by(order(Task.created_at))
        elif field == "due_date":
            stmt = stmt.order_by(order(Task.due_date))
        else:
            stmt = stmt.order_by(order(Task.id))
    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: int, user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    stmt = (
        select(Task)
        .join(Project, Task.project_id == Project.id)
        .where(Task.id == task_id, Project.workspace_id == user.workspace_id)
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int,
    data: TaskUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    stmt = (
        select(Task)
        .join(Project, Task.project_id == Project.id)
        .where(Task.id == task_id, Project.workspace_id == user.workspace_id)
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check permission: Admin OR assigned to this task
    if not user.is_admin:
        from app.models.assignment import Assignment
        assignment = (await db.execute(
            select(Assignment).where(
                Assignment.task_id == task_id,
                Assignment.assignee_id == user_id
            )
        )).scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=403, detail="You can only edit tasks assigned to you")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: int, user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Only admins can delete tasks
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can delete tasks")
    
    stmt = (
        select(Task)
        .join(Project, Task.project_id == Project.id)
        .where(Task.id == task_id, Project.workspace_id == user.workspace_id)
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Delete attachment files from disk before cascade removes DB records
    from pathlib import Path
    from app.models.task_extensions import TaskAttachment
    from app.models.comment import Comment
    from app.models.comment_attachment import CommentAttachment
    
    task_attachments = (await db.execute(
        select(TaskAttachment).where(TaskAttachment.task_id == task_id)
    )).scalars().all()
    for att in task_attachments:
        try:
            p = Path(att.file_path)
            if p.exists():
                p.unlink()
        except Exception:
            pass
    
    task_comments = (await db.execute(
        select(Comment).where(Comment.task_id == task_id)
    )).scalars().all()
    comment_ids = [c.id for c in task_comments]
    if comment_ids:
        comment_attachments = (await db.execute(
            select(CommentAttachment).where(CommentAttachment.comment_id.in_(comment_ids))
        )).scalars().all()
        for att in comment_attachments:
            try:
                p = Path(att.file_path)
                if p.exists():
                    p.unlink()
            except Exception:
                pass
    
    await db.delete(task)
    await db.commit()
    return None
