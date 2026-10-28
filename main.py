from dotenv import load_dotenv
load_dotenv()
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import models.tables
from database.database import db_manager, Base
from api import router as api_router
 
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=db_manager.engine)

app.include_router(api_router)
# app.include_router(PR_agent, prefix="/api", tags=["ADO PR Extractor"])

@app.get("/")
def health():
    return {"status": "Backend Running"}