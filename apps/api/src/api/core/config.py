from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

def find_env_file() -> str:
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / ".env").exists():
            return str(current / ".env")
        if current.parent == current:
            break
        current = current.parent
    return ".env"


class Config(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/underwriting_db"
    
    # S3 / MinIO Configuration
    MINIO_HOST: str = "localhost"
    MINIO_PORT: str = "9000"
    S3_ENDPOINT_URL: Optional[str] = None
    S3_BUCKET: str = "filings"
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    AWS_REGION: str = "us-east-1"

    # Airflow Configuration
    AIRFLOW_URL: str = "http://airflow-webserver:8080"
    AIRFLOW_USERNAME: str = "admin"
    AIRFLOW_PASSWORD: str = "admin"

    model_config = SettingsConfigDict(env_file=find_env_file(), extra="ignore")

    @model_validator(mode="after")
    def set_s3_endpoint_url(self) -> "Config":
        if not self.S3_ENDPOINT_URL:
            self.S3_ENDPOINT_URL = f"http://{self.MINIO_HOST}:{self.MINIO_PORT}"
        return self

config = Config()