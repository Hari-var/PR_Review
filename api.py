from routes.database_routes import router as db_router
from routes.PR_review_route import router as pr_review_route
from routes.pr_routes import router as pr_router
from routes.work_item_routes import router as work_item_router
from routes.ado_webhook import router as pr_review_route_v2
from routes.llm_route import router as llm_router

from fastapi import APIRouter

router = APIRouter()
router.include_router(db_router, prefix="/db", tags=["Database"])
router.include_router(pr_review_route, prefix="/pr_review", tags=["PR Review"])
router.include_router(pr_review_route_v2, prefix="/pr_review_v2", tags=["PR Review version 2"])
router.include_router(pr_router, prefix="/pr_data", tags=["PR Data"])
router.include_router(work_item_router, prefix="/Workitem_data", tags=["Work-Item Data"])
router.include_router(llm_router, prefix="/llm", tags=["LLM"])