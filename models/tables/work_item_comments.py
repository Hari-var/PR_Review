from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base
from .mixins import TimestampMixin


class WorkItem_Comment(TimestampMixin, Base):
    __tablename__ = "work_item_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_item_id: Mapped[int] = mapped_column(
        ForeignKey("work_item_details.id", ondelete="CASCADE"), index=True)
    ado_comment_id: Mapped[Optional[int]] = mapped_column(Integer)
    author: Mapped[Optional[str]] = mapped_column(String(255))
    text_markdown: Mapped[Optional[str]] = mapped_column(Text)
    commented_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    work_item: Mapped["WorkItem_Details"] = relationship(back_populates="comments")
