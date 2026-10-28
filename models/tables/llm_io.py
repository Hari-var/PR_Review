from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, ForeignKey
from typing import Optional, Literal

from database.database import Base

class LLM_IO_monitor(Base):
    __tablename__ = "llm_io_monitor"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pr_details_id: Mapped[int] = mapped_column(Integer, ForeignKey("pr_details.id"))
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)

    pr: Mapped["PR_Details"] = relationship(back_populates="llm_response")
    class Config:
        from_attributes = True
