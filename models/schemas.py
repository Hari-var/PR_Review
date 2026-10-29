"""Pydantic v2 request/response models for the PR + work-item tables.

Naming per table:  XBase (shared fields) -> XCreate (+ FK) / XUpdate (all optional) / XResponse (+ id, timestamps)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, create_model


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampedResponse(ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


def _partial(name: str, base: type[BaseModel]) -> type[BaseModel]:
    """Build an all-optional copy of `base` for PATCH-style updates."""
    fields = {n: (Optional[f.annotation], None) for n, f in base.model_fields.items()}
    return create_model(name, **fields)  # type: ignore[call-overload]

# ======================================================== LLM_IO_monitor
class LLMIOMonitorBase(BaseModel):
    prompt: str
    response: str


class LLMIOMonitorCreate(LLMIOMonitorBase):
    pr_details_id: int


LLMIOMonitorUpdate = _partial("LLMIOMonitorUpdate", LLMIOMonitorCreate)


class LLMIOMonitorResponse(ORMModel, LLMIOMonitorBase):
    # your model has no TimestampMixin, so no created_at/updated_at here
    id: int
    pr_details_id: int
# =============================================================== PR_Details
class PRDetailsBase(BaseModel):
    pull_request_id: int
    repository_id: str
    repository_name: Optional[str] = None
    project: str
    web_url: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: Optional[str] = None
    is_draft: Optional[bool] = None
    merge_status: Optional[str] = None
    source_branch: Optional[str] = None
    target_branch: Optional[str] = None
    created_by_name: Optional[str] = None
    created_by_email: Optional[str] = None
    creation_date: Optional[datetime] = None
    labels: Optional[list[str]] = None
    extracted_at: Optional[datetime] = None
    warnings: Optional[list[str]] = None
    raw_payload: Optional[dict[str, Any]] = None


class PRDetailsCreate(PRDetailsBase):
    pass


PRDetailsUpdate = _partial("PRDetailsUpdate", PRDetailsBase)


class PRDetailsResponse(TimestampedResponse, PRDetailsBase):
    pass


# ============================================================== PR_Reviewer
class PRReviewerBase(BaseModel):
    name: Optional[str] = None
    vote: Optional[int] = None
    is_required: Optional[bool] = None


class PRReviewerCreate(PRReviewerBase):
    pr_id: int


PRReviewerUpdate = _partial("PRReviewerUpdate", PRReviewerCreate)


class PRReviewerResponse(TimestampedResponse, PRReviewerBase):
    pr_id: int


# =============================================================== PR_Commit
class PRCommitBase(BaseModel):
    commit_id: str
    message: Optional[str] = None
    author: Optional[str] = None
    committed_at: Optional[datetime] = None


class PRCommitCreate(PRCommitBase):
    pr_id: int


PRCommitUpdate = _partial("PRCommitUpdate", PRCommitCreate)


class PRCommitResponse(TimestampedResponse, PRCommitBase):
    pr_id: int


# ========================================================== PR_ChangedFile
class PRChangedFileBase(BaseModel):
    path: str
    change_type: Optional[str] = None


class PRChangedFileCreate(PRChangedFileBase):
    pr_id: int


PRChangedFileUpdate = _partial("PRChangedFileUpdate", PRChangedFileCreate)


class PRChangedFileResponse(TimestampedResponse, PRChangedFileBase):
    pr_id: int


# ===================================================== PR_CommentThread / PR_Comment
class PRCommentBase(BaseModel):
    author: Optional[str] = None
    text: Optional[str] = None
    published_at: Optional[datetime] = None


class PRCommentCreate(PRCommentBase):
    thread_id: int


PRCommentUpdate = _partial("PRCommentUpdate", PRCommentCreate)


class PRCommentResponse(TimestampedResponse, PRCommentBase):
    thread_id: int


class PRCommentThreadBase(BaseModel):
    ado_thread_id: Optional[int] = None
    status: Optional[str] = None
    file_path: Optional[str] = None


class PRCommentThreadCreate(PRCommentThreadBase):
    pr_id: int


PRCommentThreadUpdate = _partial("PRCommentThreadUpdate", PRCommentThreadCreate)


class PRCommentThreadResponse(TimestampedResponse, PRCommentThreadBase):
    pr_id: int


class PRCommentThreadDetailResponse(PRCommentThreadResponse):
    comments: list[PRCommentResponse] = Field(default_factory=list)


# ======================================================= Attachment_Document
class AttachmentDocumentBase(BaseModel):
    filename: Optional[str] = None
    markdown: Optional[str] = None
    blocks: Optional[list[dict[str, Any]]] = None
    comments: Optional[list[dict[str, Any]]] = None
    footnotes: Optional[list[dict[str, Any]]] = None
    headers_footers: Optional[list[dict[str, Any]]] = None
    stats: Optional[dict[str, Any]] = None
    warnings: Optional[list[str]] = None


class AttachmentDocumentCreate(AttachmentDocumentBase):
    attachment_id: int


AttachmentDocumentUpdate = _partial("AttachmentDocumentUpdate", AttachmentDocumentCreate)


class AttachmentDocumentResponse(TimestampedResponse, AttachmentDocumentBase):
    attachment_id: int


# ====================================================== WorkItem_Attachment
class WorkItemAttachmentBase(BaseModel):
    name: str
    url: Optional[str] = None
    comment: Optional[str] = None
    skipped_reason: Optional[str] = None
    error: Optional[str] = None


class WorkItemAttachmentCreate(WorkItemAttachmentBase):
    work_item_id: int


WorkItemAttachmentUpdate = _partial("WorkItemAttachmentUpdate", WorkItemAttachmentCreate)


class WorkItemAttachmentResponse(TimestampedResponse, WorkItemAttachmentBase):
    work_item_id: int


class WorkItemAttachmentDetailResponse(WorkItemAttachmentResponse):
    document: Optional[AttachmentDocumentResponse] = None


# ========================================================= WorkItem_Comment
class WorkItemCommentBase(BaseModel):
    ado_comment_id: Optional[int] = None
    author: Optional[str] = None
    text_markdown: Optional[str] = None
    commented_at: Optional[datetime] = None


class WorkItemCommentCreate(WorkItemCommentBase):
    work_item_id: int


WorkItemCommentUpdate = _partial("WorkItemCommentUpdate", WorkItemCommentCreate)


class WorkItemCommentResponse(TimestampedResponse, WorkItemCommentBase):
    work_item_id: int


# ============================================================ WorkItem_Link
class WorkItemLinkBase(BaseModel):
    rel: Optional[str] = None
    url: Optional[str] = None
    name: Optional[str] = None


class WorkItemLinkCreate(WorkItemLinkBase):
    work_item_id: int


WorkItemLinkUpdate = _partial("WorkItemLinkUpdate", WorkItemLinkCreate)


class WorkItemLinkResponse(TimestampedResponse, WorkItemLinkBase):
    work_item_id: int


# ======================================================== WorkItem_Details
class WorkItemDetailsBase(BaseModel):
    ado_work_item_id: int
    project: Optional[str] = None
    url: Optional[str] = None
    work_item_type: Optional[str] = None
    title: Optional[str] = None
    state: Optional[str] = None
    reason: Optional[str] = None
    priority: Optional[int] = None
    severity: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_to_email: Optional[str] = None
    created_by_name: Optional[str] = None
    created_by_email: Optional[str] = None
    ado_created_date: Optional[datetime] = None
    ado_changed_date: Optional[datetime] = None
    tags: Optional[str] = None
    area_path: Optional[str] = None
    iteration_path: Optional[str] = None
    description_md: Optional[str] = None
    description_html: Optional[str] = None
    acceptance_criteria_md: Optional[str] = None
    acceptance_criteria_html: Optional[str] = None
    repro_steps_md: Optional[str] = None
    repro_steps_html: Optional[str] = None
    system_info_md: Optional[str] = None


class WorkItemDetailsCreate(WorkItemDetailsBase):
    pass


WorkItemDetailsUpdate = _partial("WorkItemDetailsUpdate", WorkItemDetailsBase)


class WorkItemDetailsResponse(TimestampedResponse, WorkItemDetailsBase):
    pass


class WorkItemDetailsDetailResponse(WorkItemDetailsResponse):
    comments: list[WorkItemCommentResponse] = Field(default_factory=list)
    links: list[WorkItemLinkResponse] = Field(default_factory=list)
    attachments: list[WorkItemAttachmentDetailResponse] = Field(default_factory=list)


# ================================================== PR <-> WorkItem link table
class PRWorkItemLinkCreate(BaseModel):
    pr_id: int
    work_item_id: int


class PRWorkItemLinkResponse(ORMModel):
    pr_id: int
    work_item_id: int


# ======================================= Nested payloads for upsert (full extraction)
class WorkItemAttachmentNested(WorkItemAttachmentBase):
    document: Optional[AttachmentDocumentBase] = None


class WorkItemDetailsFullCreate(WorkItemDetailsBase):
    comments: list[WorkItemCommentBase] = Field(default_factory=list)
    links: list[WorkItemLinkBase] = Field(default_factory=list)
    attachments: list[WorkItemAttachmentNested] = Field(default_factory=list)


class PRCommentThreadNested(PRCommentThreadBase):
    comments: list[PRCommentBase] = Field(default_factory=list)


class PRDetailsFullCreate(PRDetailsBase):
    reviewers: list[PRReviewerBase] = Field(default_factory=list)
    commits: list[PRCommitBase] = Field(default_factory=list)
    changed_files: list[PRChangedFileBase] = Field(default_factory=list)
    comment_threads: list[PRCommentThreadNested] = Field(default_factory=list)
    # ADO work item ids to link (items must already exist; upsert them first)
    work_item_ado_ids: list[int] = Field(default_factory=list)


class PRDetailsDetailResponse(PRDetailsResponse):
    reviewers: list[PRReviewerResponse] = Field(default_factory=list)
    commits: list[PRCommitResponse] = Field(default_factory=list)
    changed_files: list[PRChangedFileResponse] = Field(default_factory=list)
    comment_threads: list[PRCommentThreadDetailResponse] = Field(default_factory=list)
    work_items: list[WorkItemDetailsResponse] = Field(default_factory=list)
    llm_response: list[LLMIOMonitorResponse] = Field(default_factory=list)