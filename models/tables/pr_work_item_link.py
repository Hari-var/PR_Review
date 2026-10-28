from sqlalchemy import Column, ForeignKey, Integer, Table

from database.database import Base

# Many-to-many: a PR can link several work items; a work item can be linked from several PRs.
pr_work_items = Table(
    "pr_work_items",
    Base.metadata,
    Column("pr_id", Integer, ForeignKey("pr_details.id", ondelete="CASCADE"), primary_key=True),
    Column("work_item_id", Integer, ForeignKey("work_item_details.id", ondelete="CASCADE"), primary_key=True),
)
