from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base
from .mixins import TimestampMixin


class WorkItem_Attachment(TimestampMixin, Base):
    __tablename__ = "work_item_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_item_id: Mapped[int] = mapped_column(
        ForeignKey("work_item_details.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(512))
    url: Mapped[Optional[str]] = mapped_column(String(1024))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    skipped_reason: Mapped[Optional[str]] = mapped_column(String(255))   # e.g. "not a .docx"
    error: Mapped[Optional[str]] = mapped_column(Text)                   # conversion/download error

    work_item: Mapped["WorkItem_Details"] = relationship(back_populates="attachments")
    document: Mapped[Optional["Attachment_Document"]] = relationship(
        back_populates="attachment", cascade="all, delete-orphan", uselist=False)
