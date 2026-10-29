import asyncio
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from utils.ado_client import AdoClient
from utils.aggregator import extract_pr
from utils.config import get_settings
from utils.persistence import persist_extraction
from database.database import db_manager
from utils.crudops import PRDetailsCRUD, WorkItemDetailsCRUD
from .deps import get_db
from models.schemas import PRDetailsDetailResponse, WorkItemDetailsDetailResponse
from utils.llm import get_azure_response

log = logging.getLogger("ado-pr-extractor")
router = APIRouter()


def _verify(secret_expected: str, provided: str | None):
    if secret_expected and not (provided and hmac.compare_digest(secret_expected, provided)):
        raise HTTPException(status_code=401, detail="invalid webhook secret")


async def _extract(project: str, repo_id: str, pr_id: int) -> dict:
    cfg = get_settings()
    ado = AdoClient(cfg.org_url, cfg.pat)
    try:
        return await extract_pr(ado, cfg, project, repo_id, pr_id)
    finally:
        await ado.close()


def _persist_sync(result: dict, repo_id: str) -> dict:
    # own session, created and used inside the worker thread
    with db_manager.get_session() as db:
        return persist_extraction(db, result, repo_id)


async def _extract_and_store(project: str, repo_id: str, pr_id: int) -> dict:
    result = await _extract(project, repo_id, pr_id)
    try:
        # sync DB work runs off the event loop
        saved = await asyncio.to_thread(_persist_sync, result, repo_id)
        result["persistence"] = {"saved": True, **saved}
    except Exception as e:  # noqa: BLE001
        log.exception("persisting PR %s failed", pr_id)
        result["persistence"] = {"saved": False, "error": str(e)}
    return result


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/webhook/pr-created")
async def pr_created(request: Request, x_webhook_secret: str | None = Header(default=None)):
    _verify(get_settings().webhook_secret, x_webhook_secret)
    body = await request.json()
    if body.get("eventType") != "git.pullrequest.created":
        return JSONResponse({"ignored": f"unsupported eventType {body.get('eventType')!r}"})
    res = body["resource"]
    repo = res["repository"]
    project = repo.get("project", {}).get("name")
    try:
        return await _extract_and_store(project, repo["id"], int(res["pullRequestId"]))
    except Exception as e:  # noqa: BLE001  (extraction itself failed)
        log.exception("extraction failed")
        raise HTTPException(status_code=502, detail=f"extraction failed: {e}")


@router.get("/results/{repo_id}/{pr_id}")
def get_result(repo_id: str, pr_id: int, x_webhook_secret: str | None = Header(default=None),
               db: Session = Depends(get_db)):
    """Stored result, read from the database (survives restarts)."""
    _verify(get_settings().webhook_secret, x_webhook_secret)
    crud = PRDetailsCRUD(db)
    found = crud.get_by_ado(repo_id, pr_id)
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
async def manual_extract(project: str, repo_id: str, pr_id: int,
                         x_webhook_secret: str | None = Header(default=None)):
    """Manual trigger for testing without the service hook (re-extracts and re-saves)."""
    _verify(get_settings().webhook_secret, x_webhook_secret)
    return await _extract_and_store(project, repo_id, pr_id)
