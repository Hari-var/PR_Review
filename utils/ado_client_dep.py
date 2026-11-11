"""Thin async client for the Azure DevOps REST APIs used by the extractor."""
import base64
from urllib.parse import quote

import httpx

API = "7.1"


class AdoClient:
    def __init__(self, org_url: str, pat: str):
        self.org = org_url.rstrip("/")
        token = base64.b64encode(f":{pat}".encode()).decode()
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Basic {token}"},
            timeout=30,
            follow_redirects=True,
        )

    async def close(self):
        await self._http.aclose()

    async def _json(self, url: str, **params):
        params.setdefault("api-version", API)
        r = await self._http.get(url, params=params)
        r.raise_for_status()
        return r.json()

    # ---- Pull request -------------------------------------------------
    def _pr_base(self, project: str, repo_id: str, pr_id: int) -> str:
        return (f"{self.org}/{quote(project)}/_apis/git/repositories/"
                f"{repo_id}/pullRequests/{pr_id}")

    async def pull_request(self, project, repo_id, pr_id):
        return await self._json(self._pr_base(project, repo_id, pr_id))

    async def pr_commits(self, project, repo_id, pr_id):
        d = await self._json(self._pr_base(project, repo_id, pr_id) + "/commits")
        return d.get("value", [])

    async def pr_threads(self, project, repo_id, pr_id):
        d = await self._json(self._pr_base(project, repo_id, pr_id) + "/threads")
        return d.get("value", [])

    async def pr_changed_files(self, project, repo_id, pr_id):
        base = self._pr_base(project, repo_id, pr_id)
        its = (await self._json(base + "/iterations")).get("value", [])
        if not its:
            return []
        last = its[-1]["id"]
        d = await self._json(f"{base}/iterations/{last}/changes", **{"$top": 2000})
        return d.get("changeEntries", [])

    async def pr_work_item_refs(self, project, repo_id, pr_id):
        d = await self._json(self._pr_base(project, repo_id, pr_id) + "/workitems")
        return d.get("value", [])

    # ---- Work items ---------------------------------------------------
    async def work_item(self, project, wi_id):
        url = f"{self.org}/{quote(project)}/_apis/wit/workitems/{wi_id}"
        return await self._json(url, **{"$expand": "all"})

    async def work_item_comments(self, project, wi_id):
        url = f"{self.org}/{quote(project)}/_apis/wit/workItems/{wi_id}/comments"
        d = await self._json(url, **{"api-version": "7.1-preview.4"})
        return d.get("comments", [])

    async def download(self, url: str, max_bytes: int) -> bytes:
        async with self._http.stream("GET", url, params={"download": "true"}) as r:
            r.raise_for_status()
            buf = bytearray()
            async for chunk in r.aiter_bytes():
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    raise ValueError(f"attachment exceeds {max_bytes // (1024 * 1024)} MB limit")
            return bytes(buf)
