import asyncio
import hmac
import inspect
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from utils.ado_client import AdoClient
from utils.ado_comments import post_pr_comment                      # NEW
from utils.aggregator import extract_pr
from utils.config import get_settings
from utils.persistence import persist_extraction
from utils.prompt_builder import build_review_prompt                # NEW
from database.database import db_manager
from utils.crudops import LLMIOMonitorCRUD, PRDetailsCRUD, WorkItemDetailsCRUD   # CHANGED
from .deps import get_db
from models.schemas import (                                         # CHANGED
    LLMIOMonitorCreate, PRDetailsDetailResponse, WorkItemDetailsDetailResponse)
from utils.llm import get_azure_response

log = logging.getLogger("ado-pr-extractor")
router = APIRouter()

ERROR_PREFIX = "[ERROR] "
COMMENT_STATUS = "closed"   # "closed" never blocks merge policies; use "active" to make it prominent


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


# ------------------------------------------------------------------ NEW: LLM review
def _already_reviewed(pr_db_id: int) -> bool:
    with db_manager.get_session() as db:
        return any(not r.response.startswith(ERROR_PREFIX)
                   for r in LLMIOMonitorCRUD(db).get_by_pr(pr_db_id))


def _store_llm_io(pr_db_id: int, prompt: str, response: str) -> None:
    with db_manager.get_session() as db:
        LLMIOMonitorCRUD(db).create(
            LLMIOMonitorCreate(pr_details_id=pr_db_id, prompt=prompt, response=response))


async def _call_llm(prompt: str) -> str:
    # ASSUMPTION: get_azure_response(prompt) -> str (sync or async).
    # If your function takes more arguments or returns an object, adapt ONLY this function.
    if inspect.iscoroutinefunction(get_azure_response):
        out = await get_azure_response(prompt)
    else:
        out = await asyncio.to_thread(get_azure_response, prompt)
    text = out if isinstance(out, str) else str(out)
    if not text.strip():
        raise ValueError("LLM returned an empty response")
    return text


async def _review_and_comment(result: dict, project: str, repo_id: str, pr_id: int,
                              force: bool = False) -> dict:
    pr_db_id = (result.get("persistence") or {}).get("pr_id")
    if not pr_db_id:
        return {"status": "skipped", "reason": "PR was not saved, so the LLM record cannot be linked"}
    if not force and await asyncio.to_thread(_already_reviewed, pr_db_id):
        return {"status": "skipped", "reason": "already reviewed (use force to re-run)"}

    prompt = build_review_prompt(result)
    try:
        report = await _call_llm(prompt)
    except Exception as e:  # noqa: BLE001
        log.exception("LLM call failed for PR %s", pr_id)
        await asyncio.to_thread(_store_llm_io, pr_db_id, prompt, f"{ERROR_PREFIX}{e}")
        return {"status": "failed", "stage": "llm", "error": str(e)}

    await asyncio.to_thread(_store_llm_io, pr_db_id, prompt, report)   # keep the report even if posting fails
    try:
        cfg = get_settings()
        thread_id = await post_pr_comment(cfg.org_url, cfg.pat, project, repo_id, pr_id,
                                          report, status=COMMENT_STATUS)
    except Exception as e:  # noqa: BLE001
        log.exception("posting PR comment failed for PR %s", pr_id)
        return {"status": "failed", "stage": "comment", "error": str(e), "llm_record_saved": True}
    return {"status": "completed", "comment_thread_id": thread_id}


async def _process_pr(project: str, repo_id: str, pr_id: int, force: bool = False) -> dict:
    result = await _extract_and_store(project, repo_id, pr_id)
    result["review"] = await _review_and_comment(result, project, repo_id, pr_id, force)
    return result


async def _process_pr_background(project: str, repo_id: str, pr_id: int) -> None:
    try:
        outcome = await _process_pr(project, repo_id, pr_id)
        log.info("PR %s processed: persistence=%s review=%s", pr_id,
                 outcome.get("persistence"), outcome.get("review"))
    except Exception:  # noqa: BLE001
        log.exception("background processing of PR %s failed", pr_id)


# ------------------------------------------------------------------------ endpoints
@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/webhook/pr-created", status_code=202)
async def pr_created(request: Request, background_tasks: BackgroundTasks,
                     x_webhook_secret: str | None = Header(default=None)):
    """Acknowledge immediately (ADO times out quickly); extract, save, review and comment in the background."""
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
async def manual_extract(project: str, repo_id: str, pr_id: int, force: bool = False,
                         x_webhook_secret: str | None = Header(default=None)):
    """Synchronous run for testing: extract, save, review, comment, and return everything.
    Skips the LLM step if the PR was already reviewed, unless ?force=true."""
    _verify(get_settings().webhook_secret, x_webhook_secret)
    return await _process_pr(project, repo_id, pr_id, force)