from fastapi import APIRouter

from .pr_routes import router as pr_router
from .work_item_routes import router as work_item_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(pr_router)
api_router.include_router(work_item_router)

__all__ = ["api_router"]
