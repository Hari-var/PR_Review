"""Collect PR + linked work items + work-item .docx attachments into one JSON."""
import asyncio
import datetime as dt
import re

from markdownify import markdownify

from .ado_client import AdoClient
from .config import Settings
from .docx_converter import convert_docx

HTML_FIELDS = {
    "System.Description": "description",
    "Microsoft.VSTS.Common.AcceptanceCriteria": "acceptance_criteria",
    "Microsoft.VSTS.TCM.ReproSteps": "repro_steps",
    "Microsoft.VSTS.TCM.SystemInfo": "system_info",
}
PLAIN_FIELDS = {
    "System.Title": "title",
    "System.WorkItemType": "type",
    "System.State": "state",
    "System.Reason": "reason",
    "Microsoft.VSTS.Common.Priority": "priority",
    "Microsoft.VSTS.Common.Severity": "severity",
    "System.AssignedTo": "assigned_to",
    "System.CreatedBy": "created_by",
    "System.CreatedDate": "created_date",
    "System.ChangedDate": "changed_date",
    "System.Tags": "tags",
    "System.AreaPath": "area_path",
    "System.IterationPath": "iteration_path",
}


def _person(v):
    if isinstance(v, dict):
        return {"name": v.get("displayName"), "email": v.get("uniqueName")}
    return v


def _html_to_md(html: str) -> str:
    md = markdownify(html or "", heading_style="ATX")
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def _clean_comment(c):
    return {"id": c.get("id"), "author": (c.get("createdBy") or {}).get("displayName"),
            "created": c.get("createdDate"), "text_markdown": _html_to_md(c.get("text", ""))}


async def _work_item(ado: AdoClient, cfg: Settings, project: str, wi_id: int, warnings: list):
    raw = await ado.work_item(project, wi_id)
    f = raw.get("fields", {})
    wi = {"id": wi_id, "url": raw.get("_links", {}).get("html", {}).get("href")}
    for k, name in PLAIN_FIELDS.items():
        if k in f:
            wi[name] = _person(f[k])
    for k, name in HTML_FIELDS.items():
        if f.get(k):
            wi[name] = _html_to_md(f[k])
            wi[name + "_html"] = f[k]

    try:
        wi["comments"] = [_clean_comment(c) for c in await ado.work_item_comments(project, wi_id)]
    except Exception as e:  # noqa: BLE001
        wi["comments"] = []
        warnings.append(f"WI {wi_id}: could not fetch comments ({e}).")

    wi["related_links"] = [
        {"rel": r.get("rel"), "url": r.get("url"), "name": (r.get("attributes") or {}).get("name")}
        for r in raw.get("relations", []) if r.get("rel") != "AttachedFile"]

    attachments = [r for r in raw.get("relations", []) if r.get("rel") == "AttachedFile"]
    wi["attachments"] = []
    docx_found = False
    for rel in attachments:
        name = (rel.get("attributes") or {}).get("name", "unnamed")
        entry = {"name": name, "url": rel.get("url"),
                 "comment": (rel.get("attributes") or {}).get("comment")}
        if name.lower().endswith((".docx", ".docm")):
            docx_found = True
            try:
                data = await ado.download(rel["url"], cfg.max_attachment_mb * 1024 * 1024)
                entry["document"] = await asyncio.to_thread(convert_docx, data, name)
            except Exception as e:  # noqa: BLE001
                entry["error"] = str(e)
                warnings.append(f"WI {wi_id}: failed to convert '{name}' ({e}).")
        elif name.lower().endswith(".doc"):
            warnings.append(f"WI {wi_id}: '{name}' is legacy .doc; only .docx is supported.")
        else:
            entry["skipped"] = "not a .docx; metadata only"
        wi["attachments"].append(entry)
    if not docx_found:
        warnings.append(f"WI {wi_id}: no .docx attachment found.")
    return wi


async def extract_pr(ado: AdoClient, cfg: Settings, project: str, repo_id: str, pr_id: int) -> dict:
    warnings: list[str] = []
    pr, commits, threads, files, refs = await asyncio.gather(
        ado.pull_request(project, repo_id, pr_id),
        ado.pr_commits(project, repo_id, pr_id),
        ado.pr_threads(project, repo_id, pr_id),
        ado.pr_changed_files(project, repo_id, pr_id),
        ado.pr_work_item_refs(project, repo_id, pr_id),
    )

    pull_request = {
        "id": pr_id,
        "title": pr.get("title"),
        "description_markdown": pr.get("description") or "",
        "status": pr.get("status"),
        "is_draft": pr.get("isDraft"),
        "created_by": _person(pr.get("createdBy")),
        "creation_date": pr.get("creationDate"),
        "source_branch": pr.get("sourceRefName"),
        "target_branch": pr.get("targetRefName"),
        "merge_status": pr.get("mergeStatus"),
        "repository": (pr.get("repository") or {}).get("name"),
        "project": project,
        "labels": [l.get("name") for l in pr.get("labels", [])],
        "reviewers": [{"name": r.get("displayName"), "vote": r.get("vote"),
                       "required": r.get("isRequired")} for r in pr.get("reviewers", [])],
        "commits": [{"id": c.get("commitId"), "message": c.get("comment"),
                     "author": (c.get("author") or {}).get("name"),
                     "date": (c.get("author") or {}).get("date")} for c in commits],
        "changed_files": [{"path": (e.get("item") or {}).get("path"),
                           "change_type": e.get("changeType")} for e in files],
        "comment_threads": [
            {"id": t.get("id"), "status": t.get("status"),
             "file": (t.get("threadContext") or {}).get("filePath"),
             "comments": [{"author": (c.get("author") or {}).get("displayName"),
                           "text": c.get("content"), "published": c.get("publishedDate")}
                          for c in t.get("comments", []) if c.get("commentType") != "system"]}
            for t in threads if any(c.get("commentType") != "system" for c in t.get("comments", []))],
    }

    work_items = []
    if not refs:
        warnings.append("No work item is linked to this pull request.")
    elif len(refs) > 1:
        warnings.append(f"{len(refs)} work items are linked; all were processed.")
    results = await asyncio.gather(
        *[_work_item(ado, cfg, project, int(r["id"]), warnings) for r in refs],
        return_exceptions=True)
    for r, res in zip(refs, results):
        if isinstance(res, Exception):
            warnings.append(f"WI {r['id']}: failed to fetch ({res}).")
        else:
            work_items.append(res)

    return {
        "meta": {"extracted_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                 "schema_version": "1.0",
                 "note": "Changed files list paths and change types only; diffs are not included."},
        "pull_request": pull_request,
        "work_items": work_items,
        "warnings": warnings,
    }
