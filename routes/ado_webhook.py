import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from utils.ado_client import AdoClient
from utils.ado_comments import post_pr_comment
from utils.aggregator import extract_pr
from utils.config import get_settings
from utils.constants import SOURCE_ADO
from utils.crudops import PRDetailsCRUD, WorkItemDetailsCRUD
from utils.pr_review import process
from models.schemas import PRDetailsDetailResponse, WorkItemDetailsDetailResponse
from .deps import get_db

log = logging.getLogger("ado-pr-extractor")
router = APIRouter()

COMMENT_STATUS = "closed"   # "closed" never blocks merge policies; use "active" to make it prominent


def _verify(secret_expected: str, provided: str | None):
    if secret_expected and not (provided and hmac.compare_digest(secret_expected, provided)):
        raise HTTPException(status_code=401, detail="invalid webhook secret")


async def _process_pr(project: str, repo_id: str, pr_id: int, force: bool = False) -> dict:
    cfg = get_settings()
    ado = AdoClient(cfg.org_url, cfg.pat)
    try:
        result = await extract_pr(ado, cfg, project, repo_id, pr_id)
    finally:
        await ado.close()

    async def post(markdown: str):
        return await post_pr_comment(cfg.org_url, cfg.pat, project, repo_id, pr_id,
                                     markdown, status=COMMENT_STATUS)

    return await process(result, repo_id, post, force)


async def _process_pr_background(project: str, repo_id: str, pr_id: int) -> None:
    try:
        outcome = await _process_pr(project, repo_id, pr_id)
        log.info("PR %s processed: persistence=%s review=%s", pr_id,
                 outcome.get("persistence"), outcome.get("review"))
    except Exception:  # noqa: BLE001
        log.exception("background processing of PR %s failed", pr_id)


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/webhook/pr-created", status_code=202)
async def pr_created(request: Request, background_tasks: BackgroundTasks,
                     x_webhook_secret: str | None = Header(default=None)):
    """Azure DevOps service hook. Acknowledge immediately; the rest runs in the background."""
    _verify(get_settings().webhook_secret, x_webhook_secret)
    body = await request.json()
    if body.get("eventType") != "git.pullrequest.created":
        return JSONResponse({"ignored": f"unsupported eventType {body.get('eventType')!r}"})
    res = body["resource"]
    repo = res["repository"]
    project = repo.get("project", {}).get("name")
    pr_id = int(res["pullRequestId"])
    background_tasks.add_task(_process_pr_background, project, repo["id"], pr_id)
    return {"accepted": True, "pull_request_id": pr_id}


@router.get("/results/{source_system}/{repo_id}/{pr_id}")
def get_result(source_system: str, repo_id: str, pr_id: int,
               x_webhook_secret: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Stored result for any source system (azure_devops, bitbucket), read from the database."""
    _verify(get_settings().webhook_secret, x_webhook_secret)
    crud = PRDetailsCRUD(db)
    found = crud.get_by_source(source_system, repo_id, pr_id)
    if found is None:
        raise HTTPException(404, "no stored result")
    pr = crud.get_detail(found.id)
    wi_crud = WorkItemDetailsCRUD(db)
    return {
        "pull_request": PRDetailsDetailResponse.model_validate(pr),
        "work_items": [WorkItemDetailsDetailResponse.model_validate(wi_crud.get_detail(w.id))
                       for w in pr.work_items],
    }


@router.post("/extract/{project}/{repo_id}/{pr_id}")
async def manual_extract(project: str, repo_id: str, pr_id: int, force: bool = False,
                         x_webhook_secret: str | None = Header(default=None)):
    """Synchronous run for testing (Azure DevOps PR). ?force=true re-runs an already reviewed PR."""
    _verify(get_settings().webhook_secret, x_webhook_secret)
    return await _process_pr(project, repo_id, pr_id, force)
