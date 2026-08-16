from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers.endpoints import api_router
from alembic.config import Config as AlembicConfig
from alembic import command
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Auto-running database migrations on startup...")
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        ini_path = os.path.join(base_dir, "alembic.ini")
        cfg = AlembicConfig(ini_path)
        cfg.set_main_option("script_location", os.path.join(base_dir, "src", "api", "migrations"))
        command.upgrade(cfg, "head")
        logger.info("Database migrations completed successfully.")
    except Exception as e:
        logger.error(f"Failed to auto-run database migrations: {e}", exc_info=True)
    yield

app = FastAPI(
    title="AI-Assisted Credit Underwriting Platform API",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(api_router, prefix="/api")
