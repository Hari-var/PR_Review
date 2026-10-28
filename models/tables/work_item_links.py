from typing import Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base
from .mixins import TimestampMixin


class WorkItem_Link(TimestampMixin, Base):
    """Related items (parent/child/related/PR/commit links), excluding attachments."""
    __tablename__ = "work_item_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_item_id: Mapped[int] = mapped_column(
        ForeignKey("work_item_details.id", ondelete="CASCADE"), index=True)
    rel: Mapped[Optional[str]] = mapped_column(String(128))
    url: Mapped[Optional[str]] = mapped_column(String(1024))
    name: Mapped[Optional[str]] = mapped_column(String(255))

    work_item: Mapped["WorkItem_Details"] = relationship(back_populates="links")
