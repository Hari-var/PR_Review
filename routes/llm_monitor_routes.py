"""Endpoints for the LLM_IO_monitor table (prompt/response audit log)."""
from fastapi import Depends
from sqlalchemy.orm import Session

from utils.crudops import LLMIOMonitorCRUD
from models.schemas import LLMIOMonitorCreate, LLMIOMonitorResponse, LLMIOMonitorUpdate

from .crud_factory import build_crud_router
from .deps import get_db, or_404

# POST ""  GET ""(?pr_details_id=)  GET/PATCH/DELETE "/{item_id}"
router = build_crud_router(
    prefix="/llm-io-monitor", tag="LLM IO monitor", label="llm_io_monitor",
    crud_cls=LLMIOMonitorCRUD, create_schema=LLMIOMonitorCreate,
    update_schema=LLMIOMonitorUpdate, response_schema=LLMIOMonitorResponse,
    list_by=("pr_details_id", "get_by_pr"))


@router.get("/by-pr/{pr_id}/latest", response_model=LLMIOMonitorResponse)
def latest_for_pr(pr_id: int, db: Session = Depends(get_db)):
    """Most recent prompt/response recorded for a PR (database id)."""
    rows = LLMIOMonitorCRUD(db).get_by_pr(pr_id)
    return or_404(rows[-1] if rows else None, "LLM record")