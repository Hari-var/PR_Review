"""Bitbucket support: parse the "PR created" webhook (Cloud and Data Center) and post PR comments.

Environment:
  BITBUCKET_TOKEN           Cloud: API token | Data Center: HTTP access token
  BITBUCKET_EMAIL           Cloud only: account email used with the API token
  BITBUCKET_BASE_URL        Data Center only, e.g. https://bitbucket.company.com
  BITBUCKET_WEBHOOK_SECRET  optional; if set, the X-Hub-Signature header is verified
"""
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import httpx

from .constants import SOURCE_BITBUCKET

CLOUD_EVENT = "pullrequest:created"
DC_EVENT = "pr:opened"
MAX_COMMENT_CHARS = 30_000


@dataclass
class BitbucketSettings:
    token: str
    email: str
    base_url: str
    webhook_secret: str


def settings() -> BitbucketSettings:
    return BitbucketSettings(
        token=os.environ.get("BITBUCKET_TOKEN", ""),
        email=os.environ.get("BITBUCKET_EMAIL", ""),
        base_url=os.environ.get("BITBUCKET_BASE_URL", "").rstrip("/"),
        webhook_secret=os.environ.get("BITBUCKET_WEBHOOK_SECRET", ""))


@dataclass
class BitbucketPR:
    flavor: str                       # "cloud" | "datacenter"
    pr_id: int
    title: str
    description: str
    state: str
    source_branch: Optional[str]
    target_branch: Optional[str]
    author_name: Optional[str]
    author_email: Optional[str]
    created_at: Optional[str]
    repository_id: str
    repository_name: str
    project: str                      # Cloud: workspace slug | Data Center: project key
    repo_slug: str
    web_url: Optional[str]
    is_draft: Optional[bool]

    def to_pull_request(self) -> dict:
        """Normalized PR dict (same shape the extractor produces for other code hosts)."""
        return {
            "id": self.pr_id, "source_system": SOURCE_BITBUCKET, "title": self.title,
            "description_markdown": self.description, "status": self.state,
            "is_draft": self.is_draft,
            "created_by": {"name": self.author_name, "email": self.author_email},
            "creation_date": self.created_at, "source_branch": self.source_branch,
            "target_branch": self.target_branch, "merge_status": None,
            "repository": self.repository_name, "project": self.project, "web_url": self.web_url,
            "labels": [], "reviewers": [], "commits": [], "changed_files": [], "comment_threads": [],
        }


# ---------------------------------------------------------------------- parsing
def _parse_cloud(body: dict) -> BitbucketPR:
    pr = body["pullrequest"]
    repo = body.get("repository") or (pr.get("destination") or {}).get("repository") or {}
    full = repo.get("full_name") or ""
    workspace, _, slug = full.partition("/")
    workspace = workspace or (repo.get("workspace") or {}).get("slug") or ""
    slug = slug or repo.get("slug") or repo.get("name") or ""
    author = pr.get("author") or {}
    return BitbucketPR(
        flavor="cloud", pr_id=int(pr["id"]), title=pr.get("title") or "",
        description=pr.get("description") or "", state=(pr.get("state") or "").lower(),
        source_branch=((pr.get("source") or {}).get("branch") or {}).get("name"),
        target_branch=((pr.get("destination") or {}).get("branch") or {}).get("name"),
        author_name=author.get("display_name") or author.get("nickname"), author_email=None,
        created_at=pr.get("created_on"), repository_id=repo.get("uuid") or full or slug,
        repository_name=repo.get("name") or slug, project=workspace, repo_slug=slug,
        web_url=((pr.get("links") or {}).get("html") or {}).get("href"), is_draft=pr.get("draft"))


def _parse_dc(body: dict) -> BitbucketPR:
    pr = body["pullRequest"]
    repo = (pr.get("toRef") or {}).get("repository") or {}
    key = (repo.get("project") or {}).get("key") or ""
    slug = repo.get("slug") or ""
    created = pr.get("createdDate")
    iso = (datetime.fromtimestamp(created / 1000, tz=timezone.utc).isoformat()
           if isinstance(created, (int, float)) else None)
    user = (pr.get("author") or {}).get("user") or {}
    links = (pr.get("links") or {}).get("self") or []
    return BitbucketPR(
        flavor="datacenter", pr_id=int(pr["id"]), title=pr.get("title") or "",
        description=pr.get("description") or "", state=(pr.get("state") or "").lower(),
        source_branch=(pr.get("fromRef") or {}).get("displayId"),
        target_branch=(pr.get("toRef") or {}).get("displayId"),
        author_name=user.get("displayName") or user.get("name"),
        author_email=user.get("emailAddress"), created_at=iso,
        repository_id=str(repo.get("id") or f"{key}/{slug}"),
        repository_name=repo.get("name") or slug, project=key, repo_slug=slug,
        web_url=links[0].get("href") if links else None, is_draft=pr.get("draft"))


def parse_webhook(body: dict, event_key: Optional[str] = None) -> Optional[BitbucketPR]:
    """Return the PR for a "PR created" event (Cloud or Data Center), else None."""
    key = event_key or body.get("eventKey")
    if "pullrequest" in body:
        return _parse_cloud(body) if key in (None, CLOUD_EVENT) else None
    if "pullRequest" in body:
        return _parse_dc(body) if key in (None, DC_EVENT) else None
    return None


def verify_signature(raw_body: bytes, header: Optional[str]) -> bool:
    """True if no secret is configured, or the `X-Hub-Signature: sha256=<hex>` header matches."""
    secret = settings().webhook_secret
    if not secret:
        return True
    if not header or "=" not in header:
        return False
    algo, _, sig = header.partition("=")
    if algo.lower() != "sha256":
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig.strip())


# ---------------------------------------------------------------------- comments
async def post_comment(pr: BitbucketPR, markdown: str) -> str:
    """Add a comment to the PR. Returns the new comment id."""
    s = settings()
    if len(markdown) > MAX_COMMENT_CHARS:
        markdown = markdown[:MAX_COMMENT_CHARS] + "\n\n_[comment truncated]_"
    if not s.token:
        raise RuntimeError("BITBUCKET_TOKEN is not set")
    async with httpx.AsyncClient(timeout=30) as client:
        if pr.flavor == "cloud":
            if not s.email:
                raise RuntimeError("BITBUCKET_EMAIL is required for Bitbucket Cloud")
            url = (f"https://api.bitbucket.org/2.0/repositories/{quote(pr.project)}/"
                   f"{quote(pr.repo_slug)}/pullrequests/{pr.pr_id}/comments")
            r = await client.post(url, json={"content": {"raw": markdown}},
                                  auth=httpx.BasicAuth(s.email, s.token))
        else:
            if not s.base_url:
                raise RuntimeError("BITBUCKET_BASE_URL is required for Bitbucket Data Center")
            url = (f"{s.base_url}/rest/api/1.0/projects/{quote(pr.project)}/repos/"
                   f"{quote(pr.repo_slug)}/pull-requests/{pr.pr_id}/comments")
            r = await client.post(url, json={"text": markdown},
                                  headers={"Authorization": f"Bearer {s.token}"})
    if r.status_code >= 400:
        raise RuntimeError(f"Bitbucket {r.status_code} posting PR comment: {r.text[:300]}")
    return str(r.json().get("id"))
