from typing import Optional

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base
from .mixins import TimestampMixin


class Attachment_Document(TimestampMixin, Base):
    """Converted .docx content, one-to-one with a work-item attachment."""
    __tablename__ = "attachment_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("work_item_attachments.id", ondelete="CASCADE"), unique=True)
    filename: Mapped[Optional[str]] = mapped_column(String(512))
    markdown: Mapped[Optional[str]] = mapped_column(Text)            # flat, human/LLM-readable
    blocks: Mapped[Optional[list]] = mapped_column(JSON)             # structured blocks (tables, lists, ...)
    comments: Mapped[Optional[list]] = mapped_column(JSON)           # Word comments
    footnotes: Mapped[Optional[list]] = mapped_column(JSON)
    headers_footers: Mapped[Optional[list]] = mapped_column(JSON)
    stats: Mapped[Optional[dict]] = mapped_column(JSON)
    warnings: Mapped[Optional[list]] = mapped_column(JSON)

    attachment: Mapped["WorkItem_Attachment"] = relationship(back_populates="document")
