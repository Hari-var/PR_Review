"""Map the extractor's JSON (aggregator.extract_pr output) onto the schemas and save it with crudops.

    with SessionLocal() as db:
        summary = persist_extraction(db, result, repository_id)

Order matters: work items are upserted first so the PR upsert can link them.
Each upsert is its own transaction and is idempotent, so a retry after a partial
failure simply completes the job.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from .crudops import PRDetailsCRUD, WorkItemDetailsCRUD
from models.schemas import (
    AttachmentDocumentBase, PRChangedFileBase, PRCommentBase, PRCommentThreadNested,
    PRCommitBase, PRDetailsFullCreate, PRReviewerBase, WorkItemAttachmentNested,
    WorkItemCommentBase, WorkItemDetailsFullCreate, WorkItemLinkBase,
)


# ------------------------------------------------------------------- helpers
def _dt(value: Any) -> Optional[datetime]:
    """ADO ISO string -> naive UTC datetime (ADO sends 7 fractional digits; Python takes 6)."""
    if not value:
        return None
    if isinstance(value, datetime):
        d = value
    else:
        s = re.sub(r"(\.\d{6})\d+", r"\1", str(value).strip())
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo:
        d = d.astimezone(timezone.utc).replace(tzinfo=None)
    return d


def _person(v: Any) -> tuple[Optional[str], Optional[str]]:
    if isinstance(v, dict):
        return v.get("name"), v.get("email")
    return (str(v), None) if v else (None, None)


def _int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _s(v: Any) -> Optional[str]:
    return None if v is None else str(v)


# ------------------------------------------------------------------- mappers
def to_work_item(wi: dict, project: Optional[str] = None) -> WorkItemDetailsFullCreate:
    assigned_name, assigned_email = _person(wi.get("assigned_to"))
    created_name, created_email = _person(wi.get("created_by"))

    attachments = []
    for a in wi.get("attachments", []):
        doc = a.get("document")
        attachments.append(WorkItemAttachmentNested(
            name=a.get("name") or "unnamed",
            url=a.get("url"),
            comment=a.get("comment"),
            skipped_reason=a.get("skipped"),
            error=a.get("error"),
            document=AttachmentDocumentBase(
                filename=doc.get("filename"), markdown=doc.get("markdown"),
                blocks=doc.get("blocks"), comments=doc.get("comments"),
                footnotes=doc.get("footnotes"), headers_footers=doc.get("headers_footers"),
                stats=doc.get("stats"), warnings=doc.get("warnings")) if doc else None,
        ))

    return WorkItemDetailsFullCreate(
        ado_work_item_id=int(wi["id"]),
        project=project,
        url=wi.get("url"),
        work_item_type=wi.get("type"),
        title=wi.get("title"),
        state=wi.get("state"),
        reason=wi.get("reason"),
        priority=_int(wi.get("priority")),
        severity=_s(wi.get("severity")),
        assigned_to_name=assigned_name, assigned_to_email=assigned_email,
        created_by_name=created_name, created_by_email=created_email,
        ado_created_date=_dt(wi.get("created_date")),
        ado_changed_date=_dt(wi.get("changed_date")),
        tags=wi.get("tags"),
        area_path=wi.get("area_path"),
        iteration_path=wi.get("iteration_path"),
        description_md=wi.get("description"),
        description_html=wi.get("description_html"),
        acceptance_criteria_md=wi.get("acceptance_criteria"),
        acceptance_criteria_html=wi.get("acceptance_criteria_html"),
        repro_steps_md=wi.get("repro_steps"),
        repro_steps_html=wi.get("repro_steps_html"),
        system_info_md=wi.get("system_info"),
        comments=[WorkItemCommentBase(
            ado_comment_id=_int(c.get("id")), author=c.get("author"),
            text_markdown=c.get("text_markdown"), commented_at=_dt(c.get("created")))
            for c in wi.get("comments", [])],
        links=[WorkItemLinkBase(rel=l.get("rel"), url=l.get("url"), name=l.get("name"))
               for l in wi.get("related_links", [])],
        attachments=attachments,
    )


def to_pull_request(result: dict, repository_id: str, work_item_ado_ids: list[int],
                    store_raw: bool = False) -> PRDetailsFullCreate:
    p = result["pull_request"]
    created_name, created_email = _person(p.get("created_by"))
    meta = result.get("meta", {})

    return PRDetailsFullCreate(
        pull_request_id=int(p["id"]),
        repository_id=repository_id,
        repository_name=p.get("repository"),
        project=p.get("project") or "",
        web_url=p.get("web_url"),
        title=p.get("title") or "(no title)",
        description=p.get("description_markdown"),
        status=p.get("status"),
        is_draft=p.get("is_draft"),
        merge_status=p.get("merge_status"),
        source_branch=p.get("source_branch"),
        target_branch=p.get("target_branch"),
        created_by_name=created_name, created_by_email=created_email,
        creation_date=_dt(p.get("creation_date")),
        labels=[l for l in (p.get("labels") or []) if l],
        extracted_at=_dt(meta.get("extracted_at")),
        warnings=result.get("warnings"),
        raw_payload=result if store_raw else None,
        reviewers=[PRReviewerBase(name=r.get("name"), vote=_int(r.get("vote")),
                                  is_required=r.get("required"))
                   for r in p.get("reviewers", [])],
        commits=[PRCommitBase(commit_id=c["id"], message=c.get("message"),
                              author=c.get("author"), committed_at=_dt(c.get("date")))
                 for c in p.get("commits", []) if c.get("id")],
        changed_files=[PRChangedFileBase(path=f["path"], change_type=_s(f.get("change_type")))
                       for f in p.get("changed_files", []) if f.get("path")],
        comment_threads=[PRCommentThreadNested(
            ado_thread_id=_int(t.get("id")), status=_s(t.get("status")), file_path=t.get("file"),
            comments=[PRCommentBase(author=c.get("author"), text=c.get("text"),
                                    published_at=_dt(c.get("published"))) for c in t.get("comments", [])])
            for t in p.get("comment_threads", [])],
        work_item_ado_ids=work_item_ado_ids,
    )


# ------------------------------------------------------------------- entry point
def persist_extraction(db: Session, result: dict, repository_id: str,
                       store_raw: bool = False) -> dict:
    """Save one extraction. Returns {"pr_id": <db id>, "work_item_ids": [<db ids>]}."""
    wi_crud = WorkItemDetailsCRUD(db)
    project = result.get("pull_request", {}).get("project")
    saved_wis = [wi_crud.upsert(to_work_item(wi, project)) for wi in result.get("work_items", [])]

    pr = PRDetailsCRUD(db).upsert(to_pull_request(
        result, repository_id, [w.ado_work_item_id for w in saved_wis], store_raw))
    return {"pr_id": pr.id, "work_item_ids": [w.id for w in saved_wis]}
