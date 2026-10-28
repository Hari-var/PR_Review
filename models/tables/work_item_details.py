from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base
from .mixins import TimestampMixin


class WorkItem_Details(TimestampMixin, Base):
    __tablename__ = "work_item_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ado_work_item_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)  # ADO id (org-unique)
    project: Mapped[Optional[str]] = mapped_column(String(255))
    url: Mapped[Optional[str]] = mapped_column(String(1024))

    work_item_type: Mapped[Optional[str]] = mapped_column(String(64))   # Bug / Task / User Story ...
    title: Mapped[Optional[str]] = mapped_column(String(512))
    state: Mapped[Optional[str]] = mapped_column(String(64))
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    priority: Mapped[Optional[int]] = mapped_column(Integer)
    severity: Mapped[Optional[str]] = mapped_column(String(64))
    assigned_to_name: Mapped[Optional[str]] = mapped_column(String(255))
    assigned_to_email: Mapped[Optional[str]] = mapped_column(String(255))
    created_by_name: Mapped[Optional[str]] = mapped_column(String(255))
    created_by_email: Mapped[Optional[str]] = mapped_column(String(255))
    ado_created_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ado_changed_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    tags: Mapped[Optional[str]] = mapped_column(String(1024))
    area_path: Mapped[Optional[str]] = mapped_column(String(512))
    iteration_path: Mapped[Optional[str]] = mapped_column(String(512))

    # rich-text fields (markdown for LLMs, html kept for fidelity)
    description_md: Mapped[Optional[str]] = mapped_column(Text)
    description_html: Mapped[Optional[str]] = mapped_column(Text)
    acceptance_criteria_md: Mapped[Optional[str]] = mapped_column(Text)
    acceptance_criteria_html: Mapped[Optional[str]] = mapped_column(Text)
    repro_steps_md: Mapped[Optional[str]] = mapped_column(Text)
    repro_steps_html: Mapped[Optional[str]] = mapped_column(Text)
    system_info_md: Mapped[Optional[str]] = mapped_column(Text)

    # relationships
    pull_requests: Mapped[list["PR_Details"]] = relationship(
        secondary="pr_work_items", back_populates="work_items")
    comments: Mapped[list["WorkItem_Comment"]] = relationship(
        back_populates="work_item", cascade="all, delete-orphan")
    links: Mapped[list["WorkItem_Link"]] = relationship(
        back_populates="work_item", cascade="all, delete-orphan")
    attachments: Mapped[list["WorkItem_Attachment"]] = relationship(
        back_populates="work_item", cascade="all, delete-orphan")
