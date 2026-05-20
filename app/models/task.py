from __future__ import annotations

from datetime import datetime, date, time
from typing import Optional

from sqlmodel import Field, SQLModel

from .enums import TaskPriority, TaskStatus


class TaskBase(SQLModel):
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    # Scheduling
    start_date: Optional[date] = None
    start_time: Optional[time] = None
    due_date: Optional[date] = None
    due_time: Optional[time] = None
    # Working days (comma-separated: "0,1,2,3,4" for Mon-Fri, where Mon=0, Sun=6)
    working_days: Optional[str] = Field(default="0,1,2,3,4")
    # Time tracking
    estimated_hours: Optional[float] = None
    time_spent_hours: Optional[float] = None
    # Archive status - when task is marked done and locked
    is_archived: bool = Field(default=False, index=True)
    archived_at: Optional[datetime] = None
    # Tags for flexible categorization
    tags: Optional[str] = None  # Comma-separated tags
    # Customer info (optional - for tasks related to specific customers)
    customer_name: Optional[str] = None
    customer_surname: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_office_number: Optional[str] = None
    # Completion/Billing details (optional, filled when completing task)
    # Billable items
    billable_traveling: Optional[str] = None
    billable_labour_onsite: Optional[str] = None
    billable_remote_labour: Optional[str] = None
    billable_equipment_used: Optional[str] = None
    # Non-billable items
    non_billable_traveling: Optional[str] = None
    non_billable_labour_onsite: Optional[str] = None
    non_billable_remote_labour: Optional[str] = None
    non_billable_equipment_used: Optional[str] = None
    # Completion notes
    completion_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Task(TaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    creator_id: int = Field(foreign_key="user.id", index=True)
    # Subtask support - parent task relationship
    parent_task_id: Optional[int] = Field(default=None, foreign_key="task.id", index=True)


class TaskCreate(SQLModel):
    title: str
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    start_date: Optional[date] = None
    start_time: Optional[time] = None
    due_date: Optional[date] = None
    due_time: Optional[time] = None
    project_id: int
    customer_name: Optional[str] = None
    customer_surname: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None


class TaskRead(TaskBase):
    id: int
    project_id: int


class TaskUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    start_date: Optional[date] = None
    start_time: Optional[time] = None
    due_date: Optional[date] = None
    due_time: Optional[time] = None
    customer_name: Optional[str] = None
    customer_surname: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
