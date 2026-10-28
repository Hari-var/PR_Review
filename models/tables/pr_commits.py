from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base
from .mixins import TimestampMixin


class PR_Commit(TimestampMixin, Base):
    __tablename__ = "pr_commits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pr_id: Mapped[int] = mapped_column(ForeignKey("pr_details.id", ondelete="CASCADE"), index=True)
    commit_id: Mapped[str] = mapped_column(String(64))
    message: Mapped[Optional[str]] = mapped_column(Text)
    author: Mapped[Optional[str]] = mapped_column(String(255))
    committed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    pr: Mapped["PR_Details"] = relationship(back_populates="commits")
