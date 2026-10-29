from dotenv import load_dotenv
load_dotenv()
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    org_url: str
    pat: str
    webhook_secret: str
    max_attachment_mb: int = 25


def get_settings() -> Settings:
    org = os.environ.get("ADO_ORG_URL", "").rstrip("/")
    pat = os.environ.get("ADO_PAT", "")
    if not org or not pat:
        raise RuntimeError("ADO_ORG_URL and ADO_PAT must be set")
    return Settings(
        org_url=org,
        pat=pat,
        webhook_secret=os.environ.get("WEBHOOK_SECRET", ""),
        max_attachment_mb=int(os.environ.get("MAX_ATTACHMENT_MB", "25")),
    )

class DataBase_config:
    cloud_db = os.environ.get("DB_conn_str", "")

class Content_generator_model_config:
    AI_content_version = os.environ.get("AI_content_version","")
    AI_content_endpoint = os.environ.get("AI_content_endpoint","")
    AI_content_key = os.environ.get("AI_content_key","")
    AI_content_model = os.environ.get("AI_content_model","")