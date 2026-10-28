from routes.databade_routes import router as db_router
from routes.PR_review_route import router as pr_review_route
from fastapi import APIRouter

router = APIRouter()
router.include_router(db_router, prefix="/db", tags=["Database"])
router.include_router(pr_review_route, prefix="/pr", tags=["PR Review"])