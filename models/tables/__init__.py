# Import every model so relationships (string-referenced) resolve and
# Base.metadata knows all tables before create_all()/migrations.
from .pr_details import PR_Details
from .pr_reviewers import PR_Reviewer
from .pr_commits import PR_Commit
from .pr_changed_files import PR_ChangedFile
from .pr_comments import PR_CommentThread, PR_Comment
from .work_item_details import WorkItem_Details
from .work_item_comments import WorkItem_Comment
from .work_item_links import WorkItem_Link
from .work_item_attachments import WorkItem_Attachment
from .attachment_documents import Attachment_Document
from .pr_work_item_link import pr_work_items
from .llm_io import LLM_IO_monitor

__all__ = [
    "PR_Details", "PR_Reviewer", "PR_Commit", "PR_ChangedFile", "PR_CommentThread", "PR_Comment",
    "WorkItem_Details", "WorkItem_Comment", "WorkItem_Link", "WorkItem_Attachment",
    "Attachment_Document", "pr_work_items", "LLM_IO_monitor"
]
