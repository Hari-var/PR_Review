from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base
from .mixins import TimestampMixin


class PR_CommentThread(TimestampMixin, Base):
    __tablename__ = "pr_comment_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pr_id: Mapped[int] = mapped_column(ForeignKey("pr_details.id", ondelete="CASCADE"), index=True)
    ado_thread_id: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(String(32))
    file_path: Mapped[Optional[str]] = mapped_column(String(1024))

    pr: Mapped["PR_Details"] = relationship(back_populates="comment_threads")
    comments: Mapped[list["PR_Comment"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan")


class PR_Comment(TimestampMixin, Base):
    __tablename__ = "pr_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("pr_comment_threads.id", ondelete="CASCADE"), index=True)
    author: Mapped[Optional[str]] = mapped_column(String(255))
    text: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    thread: Mapped["PR_CommentThread"] = relationship(back_populates="comments")
