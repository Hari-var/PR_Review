"""Source-neutral pipeline: save the extraction, ask the LLM for a review, post the report.

Used by every webhook (Azure DevOps, Bitbucket, ...). A webhook only has to build the
normalized `result` dict and give us a `post_comment(markdown)` coroutine for its code host.
"""
import asyncio
import inspect
import logging
from typing import Any, Awaitable, Callable

from database.database import db_manager
from models.schemas import LLMIOMonitorCreate
from .crudops import LLMIOMonitorCRUD
from .llm import get_azure_response
from .persistence import persist_extraction
from .prompt_builder import build_review_prompt

log = logging.getLogger("pr-review")
ERROR_PREFIX = "[ERROR] "
PostComment = Callable[[str], Awaitable[Any]]


# ------------------------------------------------------------------ persistence
def _persist_sync(result: dict, repo_id: str) -> dict:
    with db_manager.get_session() as db:          # own session, used inside the worker thread
        return persist_extraction(db, result, repo_id)


async def persist(result: dict, repo_id: str) -> dict:
    """Save the extraction; records the outcome in result["persistence"]."""
    try:
        saved = await asyncio.to_thread(_persist_sync, result, repo_id)
        result["persistence"] = {"saved": True, **saved}
    except Exception as e:  # noqa: BLE001
        log.exception("persisting PR failed")
        result["persistence"] = {"saved": False, "error": str(e)}
    return result


# -------------------------------------------------------------------------- LLM
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


async def review_and_comment(result: dict, post_comment: PostComment, force: bool = False) -> dict:
    pr_db_id = (result.get("persistence") or {}).get("pr_id")
    if not pr_db_id:
        return {"status": "skipped", "reason": "PR was not saved, so the LLM record cannot be linked"}
    if not force and await asyncio.to_thread(_already_reviewed, pr_db_id):
        return {"status": "skipped", "reason": "already reviewed (use force to re-run)"}

    prompt = build_review_prompt(result)
    try:
        report = await _call_llm(prompt)
    except Exception as e:  # noqa: BLE001
        log.exception("LLM call failed")
        await asyncio.to_thread(_store_llm_io, pr_db_id, prompt, f"{ERROR_PREFIX}{e}")
        return {"status": "failed", "stage": "llm", "error": str(e)}

    await asyncio.to_thread(_store_llm_io, pr_db_id, prompt, report)  # keep the report even if posting fails
    try:
        comment_id = await post_comment(report)
    except Exception as e:  # noqa: BLE001
        log.exception("posting PR comment failed")
        return {"status": "failed", "stage": "comment", "error": str(e), "llm_record_saved": True}
    return {"status": "completed", "comment_id": comment_id}


async def process(result: dict, repo_id: str, post_comment: PostComment, force: bool = False) -> dict:
    """persist -> review -> comment. Adds "persistence" and "review" to `result` and returns it."""
    await persist(result, repo_id)
    result["review"] = await review_and_comment(result, post_comment, force)
    return result
