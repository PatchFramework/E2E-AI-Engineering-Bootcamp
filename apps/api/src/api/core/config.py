import os
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
    
    # LangSmith / LangChain Tracing Configuration
    LANGSMITH_API_KEY: Optional[str] = None
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGSMITH_TRACING: Optional[str] = "true"
    LANGCHAIN_TRACING_V2: Optional[str] = "true"
    LANGSMITH_PROJECT: Optional[str] = "e2e-ai-eng"
    LANGCHAIN_PROJECT: Optional[str] = "e2e-ai-eng"
    LANGSMITH_ENDPOINT: Optional[str] = "https://api.smith.langchain.com"
    LANGCHAIN_ENDPOINT: Optional[str] = "https://api.smith.langchain.com"
    
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
    def construct_urls_and_env(self) -> "Config":
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        if not self.S3_ENDPOINT_URL:
            self.S3_ENDPOINT_URL = f"http://{self.MINIO_HOST}:{self.MINIO_PORT}"
        if not self.AIRFLOW_URL:
            self.AIRFLOW_URL = f"http://{self.AIRFLOW_HOST}:{self.AIRFLOW_PORT}"

        # Propagate LangSmith / LangChain environment variables
        effective_ls_key = self.LANGSMITH_API_KEY or self.LANGCHAIN_API_KEY or os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
        if effective_ls_key:
            os.environ["LANGCHAIN_API_KEY"] = effective_ls_key
            os.environ["LANGSMITH_API_KEY"] = effective_ls_key
        
        effective_tracing = self.LANGSMITH_TRACING or self.LANGCHAIN_TRACING_V2 or os.environ.get("LANGSMITH_TRACING") or os.environ.get("LANGCHAIN_TRACING_V2") or "true"
        os.environ["LANGCHAIN_TRACING_V2"] = effective_tracing
        os.environ["LANGSMITH_TRACING"] = effective_tracing

        effective_project = self.LANGSMITH_PROJECT or self.LANGCHAIN_PROJECT or os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT") or "e2e-ai-eng"
        os.environ["LANGCHAIN_PROJECT"] = effective_project
        os.environ["LANGSMITH_PROJECT"] = effective_project

        effective_endpoint = self.LANGSMITH_ENDPOINT or self.LANGCHAIN_ENDPOINT or os.environ.get("LANGSMITH_ENDPOINT") or os.environ.get("LANGCHAIN_ENDPOINT") or "https://api.smith.langchain.com"
        os.environ["LANGCHAIN_ENDPOINT"] = effective_endpoint
        os.environ["LANGSMITH_ENDPOINT"] = effective_endpoint

        if self.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY


        return self


config = Config()