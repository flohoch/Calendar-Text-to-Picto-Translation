import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.api import router as api_router
from app.routers.evaluation import router as evaluation_router
from app.services import index_service, nlp_service, synset_service
from app.services.database import close_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Init __init__.py files
import app.models
import app.routers
import app.services


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Starting Pictogram Translator backend ===")
    nlp_service.init()
    synset_service.init()
    index_service.build_indices()
    logger.info("=== Backend ready ===")
    yield
    close_db()
    logger.info("=== Backend shut down ===")


app = FastAPI(
    title="Pictogram Translator",
    description="Hybrid pipeline for ARASAAC pictogram translation of calendar events",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:4200"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(evaluation_router)
