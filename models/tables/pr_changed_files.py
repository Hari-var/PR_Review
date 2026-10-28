from typing import Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base
from .mixins import TimestampMixin


class PR_ChangedFile(TimestampMixin, Base):
    __tablename__ = "pr_changed_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pr_id: Mapped[int] = mapped_column(ForeignKey("pr_details.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(1024))
    change_type: Mapped[Optional[str]] = mapped_column(String(64))  # add / edit / delete / rename

    pr: Mapped["PR_Details"] = relationship(back_populates="changed_files")
