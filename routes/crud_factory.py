"""Router factory for the simple tables: standard CRUD + optional filter-by-parent.

NOTE: deliberately no `from __future__ import annotations` here - FastAPI needs the
real schema classes in the inner function annotations.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from .deps import conflict_as_409, get_db, or_404


def build_crud_router(*, prefix: str, tag: str, label: str, crud_cls,
                      create_schema, update_schema, response_schema,
                      list_by: Optional[tuple[str, str]] = None) -> APIRouter:
    """
    list_by=("pr_id", "get_by_pr") adds an optional ?pr_id= filter to the list endpoint,
    answered by crud_cls.get_by_pr(pr_id). Without it, the list endpoint is plain pagination.
    """
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.post("", response_model=response_schema, status_code=201, name=f"create_{label}")
    def create(payload: create_schema, db: Session = Depends(get_db)):
        with conflict_as_409():
            return crud_cls(db).create(payload)

    if list_by:
        param, method = list_by

        @router.get("", response_model=list[response_schema], name=f"list_{label}")
        def list_items(
            parent_id: Optional[int] = Query(None, alias=param, description=f"Filter by {param}"),
            skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
            db: Session = Depends(get_db),
        ):
            crud = crud_cls(db)
            if parent_id is not None:
                return list(getattr(crud, method)(parent_id))
            return list(crud.get_multi(skip, limit))
    else:
        @router.get("", response_model=list[response_schema], name=f"list_{label}")
        def list_items(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
                       db: Session = Depends(get_db)):
            return list(crud_cls(db).get_multi(skip, limit))

    @router.get("/{item_id}", response_model=response_schema, name=f"get_{label}")
    def get_item(item_id: int, db: Session = Depends(get_db)):
        return or_404(crud_cls(db).get(item_id), label)

    @router.patch("/{item_id}", response_model=response_schema, name=f"update_{label}")
    def update_item(item_id: int, payload: update_schema, db: Session = Depends(get_db)):
        with conflict_as_409():
            return or_404(crud_cls(db).update(item_id, payload), label)

    @router.delete("/{item_id}", status_code=204, name=f"delete_{label}")
    def delete_item(item_id: int, db: Session = Depends(get_db)):
        or_404(crud_cls(db).delete(item_id) or None, label)
        return Response(status_code=204)

    return router
