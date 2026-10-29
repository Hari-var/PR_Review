"""Post a comment thread on an Azure DevOps pull request.

PAT scope required: Code (Read & write). The comment appears as the PAT owner.
"""
import base64
from urllib.parse import quote

import httpx

MAX_COMMENT_CHARS = 140_000   # ADO limit is 150,000
VALID_STATUS = {"active", "fixed", "wontFix", "closed", "byDesign", "pending"}


async def post_pr_comment(org_url: str, pat: str, project: str, repo_id: str, pr_id: int,
                          markdown: str, status: str = "closed") -> int:
    """Create a new thread with one markdown comment. Returns the thread id.

    status="closed" keeps the comment visible but never blocks branch policies that
    require all comments to be resolved. Use "active" if you want reviewers to notice it more.
    """
    if status not in VALID_STATUS:
        raise ValueError(f"status must be one of {sorted(VALID_STATUS)}")
    if len(markdown) > MAX_COMMENT_CHARS:
        markdown = markdown[:MAX_COMMENT_CHARS] + "\n\n_[comment truncated]_"

    url = (f"{org_url.rstrip('/')}/{quote(project)}/_apis/git/repositories/"
           f"{repo_id}/pullRequests/{pr_id}/threads")
    token = base64.b64encode(f":{pat}".encode()).decode()
    body = {"comments": [{"parentCommentId": 0, "content": markdown, "commentType": "text"}],
            "status": status}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, params={"api-version": "7.1"}, json=body,
                              headers={"Authorization": f"Basic {token}"})
    if r.status_code >= 400:
        raise RuntimeError(f"ADO {r.status_code} posting PR comment: {r.text[:300]}")
    return r.json()["id"]