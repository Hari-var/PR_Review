"""Work item aggregate: WorkItem_Details (custom routes) + comments, links, attachments, documents."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from utils.crudops import (
    AttachmentDocumentCRUD, WorkItemAttachmentCRUD, WorkItemCommentCRUD,
    WorkItemDetailsCRUD, WorkItemLinkCRUD,
)
from models.schemas import (
    AttachmentDocumentCreate, AttachmentDocumentResponse, AttachmentDocumentUpdate,
    PRDetailsResponse, WorkItemAttachmentCreate, WorkItemAttachmentResponse,
    WorkItemAttachmentUpdate, WorkItemCommentCreate, WorkItemCommentResponse,
    WorkItemCommentUpdate, WorkItemDetailsCreate, WorkItemDetailsDetailResponse,
    WorkItemDetailsFullCreate, WorkItemDetailsResponse, WorkItemDetailsUpdate,
    WorkItemLinkCreate, WorkItemLinkResponse, WorkItemLinkUpdate,
)
from .crud_factory import build_crud_router
from .deps import conflict_as_409, get_db, or_404

router = APIRouter()

# ------------------------------------------------------------- WorkItem_Details
wi = APIRouter(prefix="/work-items", tags=["Work items"])


@wi.post("", response_model=WorkItemDetailsResponse, status_code=201)
def create_work_item(payload: WorkItemDetailsCreate, db: Session = Depends(get_db)):
    with conflict_as_409():
        return WorkItemDetailsCRUD(db).create(payload)


@wi.post("/upsert", response_model=WorkItemDetailsDetailResponse)
def upsert_work_item(payload: WorkItemDetailsFullCreate, db: Session = Depends(get_db)):
    """Insert/update a work item with comments, links, attachments and converted documents
    (matched on ado_work_item_id)."""
    crud = WorkItemDetailsCRUD(db)
    with conflict_as_409():
        saved = crud.upsert(payload)
    return crud.get_detail(saved.id)


@wi.get("", response_model=list[WorkItemDetailsResponse])
def search_work_items(work_item_type: Optional[str] = None, state: Optional[str] = None,
                      skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
                      db: Session = Depends(get_db)):
    return list(WorkItemDetailsCRUD(db).search(work_item_type, state, skip, limit))


@wi.get("/by-ado/{ado_work_item_id}", response_model=WorkItemDetailsDetailResponse)
def get_work_item_by_ado(ado_work_item_id: int, db: Session = Depends(get_db)):
    crud = WorkItemDetailsCRUD(db)
    found = or_404(crud.get_by_ado_id(ado_work_item_id), "Work item")
    return crud.get_detail(found.id)


@wi.get("/{work_item_id}", response_model=WorkItemDetailsResponse)
def get_work_item(work_item_id: int, db: Session = Depends(get_db)):
    return or_404(WorkItemDetailsCRUD(db).get(work_item_id), "Work item")


@wi.get("/{work_item_id}/detail", response_model=WorkItemDetailsDetailResponse)
def get_work_item_detail(work_item_id: int, db: Session = Depends(get_db)):
    return or_404(WorkItemDetailsCRUD(db).get_detail(work_item_id), "Work item")


@wi.get("/{work_item_id}/pull-requests", response_model=list[PRDetailsResponse])
def list_work_item_prs(work_item_id: int, db: Session = Depends(get_db)):
    item = or_404(WorkItemDetailsCRUD(db).get(work_item_id), "Work item")
    return list(item.pull_requests)


@wi.patch("/{work_item_id}", response_model=WorkItemDetailsResponse)
def update_work_item(work_item_id: int, payload: WorkItemDetailsUpdate,
                     db: Session = Depends(get_db)):
    with conflict_as_409():
        return or_404(WorkItemDetailsCRUD(db).update(work_item_id, payload), "Work item")


@wi.delete("/{work_item_id}", status_code=204)
def delete_work_item(work_item_id: int, db: Session = Depends(get_db)):
    """Also deletes its comments, links, attachments and documents."""
    or_404(WorkItemDetailsCRUD(db).delete(work_item_id) or None, "Work item")
    return Response(status_code=204)


router.include_router(wi)

# ----------------------------------------------------------- simple child tables
for cfg in (
    dict(prefix="/work-item-comments", tag="Work item comments", label="work_item_comment",
         crud_cls=WorkItemCommentCRUD, create_schema=WorkItemCommentCreate,
         update_schema=WorkItemCommentUpdate, response_schema=WorkItemCommentResponse,
         list_by=("work_item_id", "get_by_work_item")),
    dict(prefix="/work-item-links", tag="Work item links", label="work_item_link",
         crud_cls=WorkItemLinkCRUD, create_schema=WorkItemLinkCreate,
         update_schema=WorkItemLinkUpdate, response_schema=WorkItemLinkResponse,
         list_by=("work_item_id", "get_by_work_item")),
    dict(prefix="/work-item-attachments", tag="Work item attachments", label="work_item_attachment",
         crud_cls=WorkItemAttachmentCRUD, create_schema=WorkItemAttachmentCreate,
         update_schema=WorkItemAttachmentUpdate, response_schema=WorkItemAttachmentResponse,
         list_by=("work_item_id", "get_by_work_item")),
):
    router.include_router(build_crud_router(**cfg))

# ---- attachment documents: one per attachment, so extra by-attachment routes
docs = build_crud_router(
    prefix="/attachment-documents", tag="Attachment documents", label="attachment_document",
    crud_cls=AttachmentDocumentCRUD, create_schema=AttachmentDocumentCreate,
    update_schema=AttachmentDocumentUpdate, response_schema=AttachmentDocumentResponse)


@docs.get("/by-attachment/{attachment_id}", response_model=AttachmentDocumentResponse)
def get_document_by_attachment(attachment_id: int, db: Session = Depends(get_db)):
    return or_404(AttachmentDocumentCRUD(db).get_by_attachment(attachment_id), "Document")


@docs.put("/by-attachment", response_model=AttachmentDocumentResponse)
def upsert_document(payload: AttachmentDocumentCreate, db: Session = Depends(get_db)):
    """Create the document for an attachment, or replace it if one exists."""
    with conflict_as_409():
        return AttachmentDocumentCRUD(db).upsert_for_attachment(payload)


router.include_router(docs)
