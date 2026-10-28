"""Pull request aggregate: PR_Details (custom routes) + reviewers, commits, files, threads, comments."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from utils.crudops import (
    PRChangedFileCRUD, PRCommentCRUD, PRCommentThreadCRUD, PRCommitCRUD,
    PRDetailsCRUD, PRReviewerCRUD, PRWorkItemLinkCRUD, WorkItemDetailsCRUD,
)
from models.schemas import (
    PRChangedFileCreate, PRChangedFileResponse, PRChangedFileUpdate,
    PRCommentCreate, PRCommentResponse, PRCommentThreadCreate, PRCommentThreadResponse,
    PRCommentThreadUpdate, PRCommentUpdate, PRCommitCreate, PRCommitResponse, PRCommitUpdate,
    PRDetailsCreate, PRDetailsDetailResponse, PRDetailsFullCreate, PRDetailsResponse,
    PRDetailsUpdate, PRReviewerCreate, PRReviewerResponse, PRReviewerUpdate,
    PRWorkItemLinkCreate, PRWorkItemLinkResponse, WorkItemDetailsResponse,
)
from .crud_factory import build_crud_router
from .deps import conflict_as_409, get_db, or_404

router = APIRouter()

# ------------------------------------------------------------------ PR_Details
pr = APIRouter(prefix="/pull-requests", tags=["Pull requests"])


@pr.post("", response_model=PRDetailsResponse, status_code=201)
def create_pr(payload: PRDetailsCreate, db: Session = Depends(get_db)):
    with conflict_as_409():
        return PRDetailsCRUD(db).create(payload)


@pr.post("/upsert", response_model=PRDetailsDetailResponse)
def upsert_pr(payload: PRDetailsFullCreate, db: Session = Depends(get_db)):
    """Insert/update a PR with reviewers, commits, files, threads and linked work items
    (matched on repository_id + pull_request_id). Upsert the work items first."""
    crud = PRDetailsCRUD(db)
    with conflict_as_409():
        saved = crud.upsert(payload)
    return crud.get_detail(saved.id)


@pr.get("", response_model=list[PRDetailsResponse])
def search_prs(project: Optional[str] = None, status: Optional[str] = None,
               skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
               db: Session = Depends(get_db)):
    return list(PRDetailsCRUD(db).search(project, status, skip, limit))


@pr.get("/by-ado/{repository_id}/{pull_request_id}", response_model=PRDetailsDetailResponse)
def get_pr_by_ado(repository_id: str, pull_request_id: int, db: Session = Depends(get_db)):
    crud = PRDetailsCRUD(db)
    found = or_404(crud.get_by_ado(repository_id, pull_request_id), "Pull request")
    return crud.get_detail(found.id)


@pr.get("/{pr_id}", response_model=PRDetailsResponse)
def get_pr(pr_id: int, db: Session = Depends(get_db)):
    return or_404(PRDetailsCRUD(db).get(pr_id), "Pull request")


@pr.get("/{pr_id}/detail", response_model=PRDetailsDetailResponse)
def get_pr_detail(pr_id: int, db: Session = Depends(get_db)):
    return or_404(PRDetailsCRUD(db).get_detail(pr_id), "Pull request")


@pr.patch("/{pr_id}", response_model=PRDetailsResponse)
def update_pr(pr_id: int, payload: PRDetailsUpdate, db: Session = Depends(get_db)):
    with conflict_as_409():
        return or_404(PRDetailsCRUD(db).update(pr_id, payload), "Pull request")


@pr.delete("/{pr_id}", status_code=204)
def delete_pr(pr_id: int, db: Session = Depends(get_db)):
    """Also deletes its reviewers, commits, files and comments. Work items are kept."""
    or_404(PRDetailsCRUD(db).delete(pr_id) or None, "Pull request")
    return Response(status_code=204)


# ----- PR <-> work item links
@pr.get("/{pr_id}/work-items", response_model=list[WorkItemDetailsResponse])
def list_pr_work_items(pr_id: int, db: Session = Depends(get_db)):
    or_404(PRDetailsCRUD(db).get(pr_id), "Pull request")
    return list(WorkItemDetailsCRUD(db).get_by_pr(pr_id))


@pr.post("/{pr_id}/work-items/{work_item_id}", response_model=PRWorkItemLinkResponse,
         status_code=201)
def link_work_item(pr_id: int, work_item_id: int, db: Session = Depends(get_db)):
    with conflict_as_409():
        created = PRWorkItemLinkCRUD(db).create(
            PRWorkItemLinkCreate(pr_id=pr_id, work_item_id=work_item_id))
    if not created:
        raise HTTPException(status_code=409, detail="Link already exists")
    return PRWorkItemLinkResponse(pr_id=pr_id, work_item_id=work_item_id)


@pr.delete("/{pr_id}/work-items/{work_item_id}", status_code=204)
def unlink_work_item(pr_id: int, work_item_id: int, db: Session = Depends(get_db)):
    or_404(PRWorkItemLinkCRUD(db).delete(pr_id, work_item_id) or None, "Link")
    return Response(status_code=204)


router.include_router(pr)

# ----------------------------------------------------------- simple child tables
for cfg in (
    dict(prefix="/pr-reviewers", tag="PR reviewers", label="pr_reviewer", crud_cls=PRReviewerCRUD,
         create_schema=PRReviewerCreate, update_schema=PRReviewerUpdate,
         response_schema=PRReviewerResponse, list_by=("pr_id", "get_by_pr")),
    dict(prefix="/pr-commits", tag="PR commits", label="pr_commit", crud_cls=PRCommitCRUD,
         create_schema=PRCommitCreate, update_schema=PRCommitUpdate,
         response_schema=PRCommitResponse, list_by=("pr_id", "get_by_pr")),
    dict(prefix="/pr-changed-files", tag="PR changed files", label="pr_changed_file",
         crud_cls=PRChangedFileCRUD, create_schema=PRChangedFileCreate,
         update_schema=PRChangedFileUpdate, response_schema=PRChangedFileResponse,
         list_by=("pr_id", "get_by_pr")),
    dict(prefix="/pr-comment-threads", tag="PR comment threads", label="pr_comment_thread",
         crud_cls=PRCommentThreadCRUD, create_schema=PRCommentThreadCreate,
         update_schema=PRCommentThreadUpdate, response_schema=PRCommentThreadResponse,
         list_by=("pr_id", "get_by_pr")),
    dict(prefix="/pr-comments", tag="PR comments", label="pr_comment", crud_cls=PRCommentCRUD,
         create_schema=PRCommentCreate, update_schema=PRCommentUpdate,
         response_schema=PRCommentResponse, list_by=("thread_id", "get_by_thread")),
):
    router.include_router(build_crud_router(**cfg))
