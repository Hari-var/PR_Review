from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base
from .mixins import TimestampMixin


class PR_Reviewer(TimestampMixin, Base):
    __tablename__ = "pr_reviewers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pr_id: Mapped[int] = mapped_column(ForeignKey("pr_details.id", ondelete="CASCADE"), index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    vote: Mapped[Optional[int]] = mapped_column(Integer)  # 10 approved, 5 w/ suggestions, 0 none, -5 waiting, -10 rejected
    is_required: Mapped[Optional[bool]] = mapped_column(Boolean)

    pr: Mapped["PR_Details"] = relationship(back_populates="reviewers")
