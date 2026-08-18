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
    
    # Database Configuration
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "underwriting_db"
    DATABASE_URL: Optional[str] = None
    
    # S3 / MinIO Configuration
    MINIO_HOST: str = "localhost"
    MINIO_PORT: str = "9000"
    S3_ENDPOINT_URL: Optional[str] = None
    S3_BUCKET: str = "filings"
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    AWS_REGION: str = "us-east-1"

    # Airflow Configuration
    AIRFLOW_HOST: str = "localhost"
    AIRFLOW_PORT: str = "8080"
    AIRFLOW_URL: Optional[str] = None
    AIRFLOW_USERNAME: str = "admin"
    AIRFLOW_PASSWORD: str = "admin"

    model_config = SettingsConfigDict(env_file=find_env_file(), extra="ignore")

    @model_validator(mode="after")
    def construct_urls(self) -> "Config":
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        if not self.S3_ENDPOINT_URL:
            self.S3_ENDPOINT_URL = f"http://{self.MINIO_HOST}:{self.MINIO_PORT}"
        if not self.AIRFLOW_URL:
            self.AIRFLOW_URL = f"http://{self.AIRFLOW_HOST}:{self.AIRFLOW_PORT}"
        return self

config = Config()