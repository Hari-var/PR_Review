from database.database import db_manager
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("/health")
async def health():
    return db_manager.health_check()
