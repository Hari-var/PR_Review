from fastapi import APIRouter #type: ignore
from utils.llm import get_azure_response

router = APIRouter()

@router.get("/test")
async def test_llm(prompt: str):
    return get_azure_response(prompt)