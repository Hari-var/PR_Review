from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base
from .mixins import TimestampMixin


class PR_Details(TimestampMixin, Base):
    __tablename__ = "pr_details"
    __table_args__ = (UniqueConstraint("repository_id", "pull_request_id", name="uq_pr_repo_prid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ADO identity
    pull_request_id: Mapped[int] = mapped_column(Integer, index=True)       # ADO PR number
    repository_id: Mapped[str] = mapped_column(String(64), index=True)      # repo GUID
    repository_name: Mapped[Optional[str]] = mapped_column(String(255))
    project: Mapped[str] = mapped_column(String(255))
    web_url: Mapped[Optional[str]] = mapped_column(String(1024))

    # core fields
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[Optional[str]] = mapped_column(String(32))               # active/completed/abandoned
    is_draft: Mapped[Optional[bool]] = mapped_column(Boolean)
    merge_status: Mapped[Optional[str]] = mapped_column(String(32))
    source_branch: Mapped[Optional[str]] = mapped_column(String(512))
    target_branch: Mapped[Optional[str]] = mapped_column(String(512))
    created_by_name: Mapped[Optional[str]] = mapped_column(String(255))
    created_by_email: Mapped[Optional[str]] = mapped_column(String(255))
    creation_date: Mapped[Optional[datetime]] = mapped_column(DateTime)    # ADO-side creation time
    labels: Mapped[Optional[list]] = mapped_column(JSON)

    # extraction bookkeeping
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    warnings: Mapped[Optional[list]] = mapped_column(JSON)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON)               # full aggregated JSON (optional)

    # relationships
    reviewers: Mapped[list["PR_Reviewer"]] = relationship(
        back_populates="pr", cascade="all, delete-orphan")
    commits: Mapped[list["PR_Commit"]] = relationship(
        back_populates="pr", cascade="all, delete-orphan")
    changed_files: Mapped[list["PR_ChangedFile"]] = relationship(
        back_populates="pr", cascade="all, delete-orphan")
    comment_threads: Mapped[list["PR_CommentThread"]] = relationship(
        back_populates="pr", cascade="all, delete-orphan")
    work_items: Mapped[list["WorkItem_Details"]] = relationship(
        secondary="pr_work_items", back_populates="pull_requests")
    llm_response: Mapped[list["LLM_IO_monitor"]] = relationship(
        back_populates="pr", cascade="all, delete-orphan")

