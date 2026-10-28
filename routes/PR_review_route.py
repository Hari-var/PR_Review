import hmac
import logging

from fastapi import Header, HTTPException, Request,APIRouter
from fastapi.responses import JSONResponse

from utils.ado_client import AdoClient
from utils.aggregator import extract_pr
from utils.config import get_settings

log = logging.getLogger("ado-pr-extractor")
router = APIRouter()
_cache: dict[tuple[str, int], dict] = {}  # idempotency + retrieval (in-memory)


def _verify(secret_expected: str, provided: str | None):
    if secret_expected and not (provided and hmac.compare_digest(secret_expected, provided)):
        raise HTTPException(status_code=401, detail="invalid webhook secret")


async def _run(project: str, repo_id: str, pr_id: int, force: bool = False) -> dict:
    key = (repo_id, pr_id)
    if key in _cache and not force:
        return _cache[key]
    cfg = get_settings()
    ado = AdoClient(cfg.org_url, cfg.pat)
    try:
        result = await extract_pr(ado, cfg, project, repo_id, pr_id)
    finally:
        await ado.close()
    _cache[key] = result
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
        result = await _run(project, repo["id"], int(res["pullRequestId"]))
    except Exception as e:  # noqa: BLE001
        log.exception("extraction failed")
        raise HTTPException(status_code=502, detail=f"extraction failed: {e}")
    return result


@router.get("/results/{repo_id}/{pr_id}")
async def get_result(repo_id: str, pr_id: int, x_webhook_secret: str | None = Header(default=None)):
    _verify(get_settings().webhook_secret, x_webhook_secret)
    if (repo_id, pr_id) not in _cache:
        raise HTTPException(404, "no cached result")
    return _cache[(repo_id, pr_id)]


@router.post("/extract/{project}/{repo_id}/{pr_id}")
async def manual_extract(project: str, repo_id: str, pr_id: int,
                         x_webhook_secret: str | None = Header(default=None)):
    """Manual trigger for testing without the service hook."""
    _verify(get_settings().webhook_secret, x_webhook_secret)
    return await _run(project, repo_id, pr_id, force=True)
