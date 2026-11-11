import datetime as dt
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from utils.ado_client import AdoClient
from utils.aggregator import fetch_work_items
from utils.bitbucket import BitbucketPR, parse_webhook, post_comment, verify_signature
from utils.config import get_settings
from utils.pr_review import persist, process
from utils.work_item_refs import parse_work_item_refs

log = logging.getLogger("bitbucket-webhook")
router = APIRouter(prefix="/webhook/bitbucket", tags=["Bitbucket"])

# True: when a PR has no work-item reference, post a short comment explaining the format.
NOTIFY_MISSING_REFERENCE = False
MISSING_REFERENCE_NOTE = (
    "**Automated review skipped:** no work item reference found. Add a line such as "
    "`Work-Items: 1234` to the PR description and re-run.")


async def _process_bitbucket(pr: BitbucketPR, force: bool = False) -> dict:
    refs = parse_work_item_refs(pr.title, pr.description)
    warnings = list(refs.warnings)
    items: list[dict] = []
    if refs.ids:
        cfg = get_settings()                       # work items still live in Azure DevOps
        ado = AdoClient(cfg.org_url, cfg.pat)
        try:
            items = await fetch_work_items(ado, cfg, refs.ids, refs.project, warnings)
        finally:
            await ado.close()
    else:
        warnings.append("No work item reference found in the PR title or description.")

    result = {
        "meta": {"extracted_at": dt.datetime.now(dt.timezone.utc).isoformat(), "schema_version": "1.0",
                 "note": "Bitbucket PR data comes from the webhook payload; work items from Azure DevOps."},
        "pull_request": pr.to_pull_request(), "work_items": items, "warnings": warnings}

    async def post(markdown: str):
        return await post_comment(pr, markdown)

    if not items:                                  # nothing to review: save the PR, skip the LLM
        await persist(result, pr.repository_id)
        result["review"] = {"status": "skipped", "reason": "no work item data to review"}
        if NOTIFY_MISSING_REFERENCE and not refs.ids:
            try:
                await post(MISSING_REFERENCE_NOTE)
            except Exception as e:  # noqa: BLE001
                log.warning("could not post missing-reference note: %s", e)
        return result
    return await process(result, pr.repository_id, post, force)


async def _background(pr: BitbucketPR) -> None:
    try:
        outcome = await _process_bitbucket(pr)
        log.info("Bitbucket PR %s processed: persistence=%s review=%s", pr.pr_id,
                 outcome.get("persistence"), outcome.get("review"))
    except Exception:  # noqa: BLE001
        log.exception("background processing of Bitbucket PR %s failed", pr.pr_id)


@router.post("/pr-created", status_code=202)
async def pr_created(request: Request, background_tasks: BackgroundTasks,
                     x_event_key: str | None = Header(default=None),
                     x_hub_signature: str | None = Header(default=None)):
    """Bitbucket webhook (Cloud: pullrequest:created | Data Center: pr:opened)."""
    raw = await request.body()
    if not verify_signature(raw, x_hub_signature):
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    try:
        body = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="body is not valid JSON")
    pr = parse_webhook(body, x_event_key)
    if pr is None:
        return JSONResponse({"ignored": f"not a pull-request-created event (event key: {x_event_key!r})"})
    background_tasks.add_task(_background, pr)
    return {"accepted": True, "pull_request_id": pr.pr_id, "flavor": pr.flavor}


@router.post("/test")
async def test_run(request: Request, force: bool = False,
                   x_event_key: str | None = Header(default=None)):
    """Synchronous run for testing: POST a Bitbucket webhook payload, get the full outcome back."""
    pr = parse_webhook(await request.json(), x_event_key)
    if pr is None:
        raise HTTPException(status_code=422, detail="payload is not a pull-request-created event")
    return await _process_bitbucket(pr, force)
