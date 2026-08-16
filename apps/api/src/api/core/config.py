from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Config(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/underwriting_db"
    
    # S3 / MinIO Configuration
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_BUCKET: str = "filings"
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    AWS_REGION: str = "us-east-1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

config = Config()