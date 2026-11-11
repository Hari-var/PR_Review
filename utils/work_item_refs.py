"""Find work-item references in a PR title/description.

RECOMMENDED FORMAT - put these lines anywhere in the PR description (ideal for a PR template):

    Work-Items: 1234, 1235
    Work-Item-Project: Fabrikam          <- optional; saves a project lookup

Also accepted: Azure Boards' own `AB#1234` anywhere in the title or description.
Rules: ids are plain numbers (comma, space or semicolon separated); an optional `AB#` prefix is
allowed inside the Work-Items line; the line may sit in a list item or quote (`- Work-Items: 12`).
"""
import re
from dataclasses import dataclass, field
from typing import Optional

MAX_ITEMS = 10

_LABEL = re.compile(r"(?im)^[ \t>*_-]*work[ _-]?items?[ \t]*:[ \t]*(.*)$")
_PROJECT = re.compile(r"(?im)^[ \t>*_-]*work[ _-]?item[ _-]?project[ \t]*:[ \t]*(.+?)[ \t]*$")
_ITEM = re.compile(r"^(?:AB#)?(\d{1,9})$", re.I)
_TOKEN = re.compile(r"(?<![\w#])AB#(\d{1,9})\b", re.I)


@dataclass
class WorkItemRefs:
    ids: list[str] = field(default_factory=list)
    project: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


def parse_work_item_refs(*texts: Optional[str]) -> WorkItemRefs:
    out = WorkItemRefs()
    for text in texts:
        text = text or ""
        for m in _LABEL.finditer(text):
            for part in re.split(r"[,\s;]+", m.group(1).strip()):
                if not part:
                    continue
                item = _ITEM.match(part)
                if item:
                    if item.group(1) not in out.ids:
                        out.ids.append(item.group(1))
                else:
                    out.warnings.append(f"Ignored unrecognised work item reference {part!r}")
        for m in _TOKEN.finditer(text):
            if m.group(1) not in out.ids:
                out.ids.append(m.group(1))
        pm = _PROJECT.search(text)
        if pm and not out.project:
            out.project = pm.group(1).strip().strip("`*_") or None
    if len(out.ids) > MAX_ITEMS:
        out.warnings.append(f"{len(out.ids)} work items referenced; only the first {MAX_ITEMS} are used.")
        out.ids = out.ids[:MAX_ITEMS]
    return out
