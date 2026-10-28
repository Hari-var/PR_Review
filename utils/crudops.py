"""CRUD operations, one class per table. Sync SQLAlchemy 2.0 Session.

Usage:
    with SessionLocal() as db:
        pr = PRDetailsCRUD(db).upsert(PRDetailsFullCreate(...))
        PRDetailsCRUD(db).get_detail(pr.id)

Every method commits on success and rolls back (then re-raises) on failure.
Methods return None / False when a row is not found, so the API layer decides
whether that is a 404.
"""
from __future__ import annotations

from typing import Any, Generic, Optional, Sequence, TypeVar

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from models.schemas import (
    AttachmentDocumentCreate, AttachmentDocumentUpdate,
    PRChangedFileCreate, PRChangedFileUpdate,
    PRCommentCreate, PRCommentThreadCreate, PRCommentThreadUpdate, PRCommentUpdate,
    PRCommitCreate, PRCommitUpdate,
    PRDetailsCreate, PRDetailsFullCreate, PRDetailsUpdate,
    PRReviewerCreate, PRReviewerUpdate,
    PRWorkItemLinkCreate,
    WorkItemAttachmentCreate, WorkItemAttachmentUpdate,
    WorkItemCommentCreate, WorkItemCommentUpdate,
    WorkItemDetailsCreate, WorkItemDetailsFullCreate, WorkItemDetailsUpdate,
    WorkItemLinkCreate, WorkItemLinkUpdate,
)
from models.tables import (
    Attachment_Document, PR_ChangedFile, PR_Comment, PR_CommentThread, PR_Commit,
    PR_Details, PR_Reviewer, WorkItem_Attachment, WorkItem_Comment, WorkItem_Details,
    WorkItem_Link, pr_work_items,
)

ModelT = TypeVar("ModelT")
CreateT = TypeVar("CreateT", bound=BaseModel)
UpdateT = TypeVar("UpdateT", bound=BaseModel)


# ============================================================================ base
class BaseCRUD(Generic[ModelT, CreateT, UpdateT]):
    model: type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def _commit(self) -> None:
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def create(self, data: CreateT) -> ModelT:
        obj = self.model(**data.model_dump())
        self.db.add(obj)
        self._commit()
        self.db.refresh(obj)
        return obj

    def get(self, id: int) -> Optional[ModelT]:
        return self.db.get(self.model, id)

    def get_multi(self, skip: int = 0, limit: int = 100) -> Sequence[ModelT]:
        stmt = select(self.model).order_by(self.model.id).offset(skip).limit(limit)  # type: ignore[attr-defined]
        return self.db.scalars(stmt).all()

    def update(self, id: int, data: UpdateT) -> Optional[ModelT]:
        obj = self.get(id)
        if obj is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        self._commit()
        self.db.refresh(obj)
        return obj

    def delete(self, id: int) -> bool:
        obj = self.get(id)
        if obj is None:
            return False
        self.db.delete(obj)
        self._commit()
        return True

    # helper for "all rows with FK == value"
    def _by_fk(self, column: Any, value: int) -> Sequence[ModelT]:
        stmt = select(self.model).where(column == value).order_by(self.model.id)  # type: ignore[attr-defined]
        return self.db.scalars(stmt).all()


# ================================================================ PR_Details
class PRDetailsCRUD(BaseCRUD[PR_Details, PRDetailsCreate, PRDetailsUpdate]):
    model = PR_Details

    def get_by_ado(self, repository_id: str, pull_request_id: int) -> Optional[PR_Details]:
        stmt = select(PR_Details).where(
            PR_Details.repository_id == repository_id,
            PR_Details.pull_request_id == pull_request_id)
        return self.db.scalars(stmt).first()

    def get_detail(self, id: int) -> Optional[PR_Details]:
        """PR with reviewers, commits, files, threads+comments and work items loaded."""
        stmt = (select(PR_Details).where(PR_Details.id == id).options(
            selectinload(PR_Details.reviewers),
            selectinload(PR_Details.commits),
            selectinload(PR_Details.changed_files),
            selectinload(PR_Details.comment_threads).selectinload(PR_CommentThread.comments),
            selectinload(PR_Details.work_items)))
        return self.db.scalars(stmt).first()

    def search(self, project: Optional[str] = None, status: Optional[str] = None,
               skip: int = 0, limit: int = 100) -> Sequence[PR_Details]:
        stmt = select(PR_Details).order_by(PR_Details.id.desc())
        if project:
            stmt = stmt.where(PR_Details.project == project)
        if status:
            stmt = stmt.where(PR_Details.status == status)
        return self.db.scalars(stmt.offset(skip).limit(limit)).all()

    def upsert(self, data: PRDetailsFullCreate) -> PR_Details:
        """Insert or update by (repository_id, pull_request_id); child rows are replaced."""
        children = {"reviewers", "commits", "changed_files", "comment_threads", "work_item_ado_ids"}
        payload = data.model_dump(exclude=children)
        obj = self.get_by_ado(data.repository_id, data.pull_request_id)
        if obj is None:
            obj = PR_Details(**payload)
            self.db.add(obj)
        else:
            for k, v in payload.items():
                setattr(obj, k, v)

        obj.reviewers = [PR_Reviewer(**r.model_dump()) for r in data.reviewers]
        obj.commits = [PR_Commit(**c.model_dump()) for c in data.commits]
        obj.changed_files = [PR_ChangedFile(**f.model_dump()) for f in data.changed_files]
        obj.comment_threads = [
            PR_CommentThread(**t.model_dump(exclude={"comments"}),
                             comments=[PR_Comment(**c.model_dump()) for c in t.comments])
            for t in data.comment_threads]
        if data.work_item_ado_ids:
            obj.work_items = list(self.db.scalars(select(WorkItem_Details).where(
                WorkItem_Details.ado_work_item_id.in_(data.work_item_ado_ids))).all())
        self._commit()
        self.db.refresh(obj)
        return obj


# ============================================================== PR_Reviewer
class PRReviewerCRUD(BaseCRUD[PR_Reviewer, PRReviewerCreate, PRReviewerUpdate]):
    model = PR_Reviewer

    def get_by_pr(self, pr_id: int) -> Sequence[PR_Reviewer]:
        return self._by_fk(PR_Reviewer.pr_id, pr_id)


# =============================================================== PR_Commit
class PRCommitCRUD(BaseCRUD[PR_Commit, PRCommitCreate, PRCommitUpdate]):
    model = PR_Commit

    def get_by_pr(self, pr_id: int) -> Sequence[PR_Commit]:
        return self._by_fk(PR_Commit.pr_id, pr_id)

    def get_by_commit_id(self, pr_id: int, commit_id: str) -> Optional[PR_Commit]:
        return self.db.scalars(select(PR_Commit).where(
            PR_Commit.pr_id == pr_id, PR_Commit.commit_id == commit_id)).first()


# ========================================================== PR_ChangedFile
class PRChangedFileCRUD(BaseCRUD[PR_ChangedFile, PRChangedFileCreate, PRChangedFileUpdate]):
    model = PR_ChangedFile

    def get_by_pr(self, pr_id: int) -> Sequence[PR_ChangedFile]:
        return self._by_fk(PR_ChangedFile.pr_id, pr_id)


# ========================================================= PR_CommentThread
class PRCommentThreadCRUD(BaseCRUD[PR_CommentThread, PRCommentThreadCreate, PRCommentThreadUpdate]):
    model = PR_CommentThread

    def get_by_pr(self, pr_id: int) -> Sequence[PR_CommentThread]:
        stmt = (select(PR_CommentThread).where(PR_CommentThread.pr_id == pr_id)
                .options(selectinload(PR_CommentThread.comments)).order_by(PR_CommentThread.id))
        return self.db.scalars(stmt).all()


# ============================================================== PR_Comment
class PRCommentCRUD(BaseCRUD[PR_Comment, PRCommentCreate, PRCommentUpdate]):
    model = PR_Comment

    def get_by_thread(self, thread_id: int) -> Sequence[PR_Comment]:
        return self._by_fk(PR_Comment.thread_id, thread_id)


# ========================================================= WorkItem_Details
class WorkItemDetailsCRUD(BaseCRUD[WorkItem_Details, WorkItemDetailsCreate, WorkItemDetailsUpdate]):
    model = WorkItem_Details

    def get_by_ado_id(self, ado_work_item_id: int) -> Optional[WorkItem_Details]:
        return self.db.scalars(select(WorkItem_Details).where(
            WorkItem_Details.ado_work_item_id == ado_work_item_id)).first()

    def get_detail(self, id: int) -> Optional[WorkItem_Details]:
        stmt = (select(WorkItem_Details).where(WorkItem_Details.id == id).options(
            selectinload(WorkItem_Details.comments),
            selectinload(WorkItem_Details.links),
            selectinload(WorkItem_Details.attachments).selectinload(WorkItem_Attachment.document)))
        return self.db.scalars(stmt).first()

    def get_by_pr(self, pr_id: int) -> Sequence[WorkItem_Details]:
        stmt = (select(WorkItem_Details)
                .join(pr_work_items, pr_work_items.c.work_item_id == WorkItem_Details.id)
                .where(pr_work_items.c.pr_id == pr_id).order_by(WorkItem_Details.id))
        return self.db.scalars(stmt).all()

    def search(self, work_item_type: Optional[str] = None, state: Optional[str] = None,
               skip: int = 0, limit: int = 100) -> Sequence[WorkItem_Details]:
        stmt = select(WorkItem_Details).order_by(WorkItem_Details.id.desc())
        if work_item_type:
            stmt = stmt.where(WorkItem_Details.work_item_type == work_item_type)
        if state:
            stmt = stmt.where(WorkItem_Details.state == state)
        return self.db.scalars(stmt.offset(skip).limit(limit)).all()

    def upsert(self, data: WorkItemDetailsFullCreate) -> WorkItem_Details:
        """Insert or update by ADO work item id; comments, links, attachments(+docs) are replaced."""
        children = {"comments", "links", "attachments"}
        payload = data.model_dump(exclude=children)
        obj = self.get_by_ado_id(data.ado_work_item_id)
        if obj is None:
            obj = WorkItem_Details(**payload)
            self.db.add(obj)
        else:
            for k, v in payload.items():
                setattr(obj, k, v)

        obj.comments = [WorkItem_Comment(**c.model_dump()) for c in data.comments]
        obj.links = [WorkItem_Link(**l.model_dump()) for l in data.links]
        atts = []
        for a in data.attachments:
            att = WorkItem_Attachment(**a.model_dump(exclude={"document"}))
            if a.document is not None:
                att.document = Attachment_Document(**a.document.model_dump())
            atts.append(att)
        obj.attachments = atts
        self._commit()
        self.db.refresh(obj)
        return obj


# ========================================================= WorkItem_Comment
class WorkItemCommentCRUD(BaseCRUD[WorkItem_Comment, WorkItemCommentCreate, WorkItemCommentUpdate]):
    model = WorkItem_Comment

    def get_by_work_item(self, work_item_id: int) -> Sequence[WorkItem_Comment]:
        return self._by_fk(WorkItem_Comment.work_item_id, work_item_id)


# ============================================================ WorkItem_Link
class WorkItemLinkCRUD(BaseCRUD[WorkItem_Link, WorkItemLinkCreate, WorkItemLinkUpdate]):
    model = WorkItem_Link

    def get_by_work_item(self, work_item_id: int) -> Sequence[WorkItem_Link]:
        return self._by_fk(WorkItem_Link.work_item_id, work_item_id)


# ====================================================== WorkItem_Attachment
class WorkItemAttachmentCRUD(
        BaseCRUD[WorkItem_Attachment, WorkItemAttachmentCreate, WorkItemAttachmentUpdate]):
    model = WorkItem_Attachment

    def get_by_work_item(self, work_item_id: int) -> Sequence[WorkItem_Attachment]:
        stmt = (select(WorkItem_Attachment).where(WorkItem_Attachment.work_item_id == work_item_id)
                .options(selectinload(WorkItem_Attachment.document)).order_by(WorkItem_Attachment.id))
        return self.db.scalars(stmt).all()


# ====================================================== Attachment_Document
class AttachmentDocumentCRUD(
        BaseCRUD[Attachment_Document, AttachmentDocumentCreate, AttachmentDocumentUpdate]):
    model = Attachment_Document

    def get_by_attachment(self, attachment_id: int) -> Optional[Attachment_Document]:
        return self.db.scalars(select(Attachment_Document).where(
            Attachment_Document.attachment_id == attachment_id)).first()

    def upsert_for_attachment(self, data: AttachmentDocumentCreate) -> Attachment_Document:
        """One document per attachment: update if it exists, else create."""
        existing = self.get_by_attachment(data.attachment_id)
        if existing is None:
            return self.create(data)
        return self.update(existing.id, AttachmentDocumentUpdate(**data.model_dump()))  # type: ignore[return-value]


# ====================================== PR <-> WorkItem association (no id column)
class PRWorkItemLinkCRUD:
    """Association table pr_work_items; composite key (pr_id, work_item_id)."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, data: PRWorkItemLinkCreate) -> bool:
        """Link a PR to a work item. Returns False if the link already exists."""
        if self.exists(data.pr_id, data.work_item_id):
            return False
        try:
            self.db.execute(pr_work_items.insert().values(**data.model_dump()))
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return True

    def exists(self, pr_id: int, work_item_id: int) -> bool:
        stmt = select(pr_work_items).where(
            pr_work_items.c.pr_id == pr_id, pr_work_items.c.work_item_id == work_item_id)
        return self.db.execute(stmt).first() is not None

    def get_by_pr(self, pr_id: int) -> Sequence[Any]:
        return self.db.execute(select(pr_work_items).where(pr_work_items.c.pr_id == pr_id)).all()

    def get_by_work_item(self, work_item_id: int) -> Sequence[Any]:
        return self.db.execute(
            select(pr_work_items).where(pr_work_items.c.work_item_id == work_item_id)).all()

    def delete(self, pr_id: int, work_item_id: int) -> bool:
        try:
            res = self.db.execute(delete(pr_work_items).where(
                pr_work_items.c.pr_id == pr_id, pr_work_items.c.work_item_id == work_item_id))
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return res.rowcount > 0
