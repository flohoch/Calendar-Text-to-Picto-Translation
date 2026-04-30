import logging
import os

from pymongo import MongoClient
from pymongo.database import Database

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("SPRING_DATA_MONGODB_URI", "mongodb://localhost:27017/pictograms")

_client: MongoClient | None = None
_db: Database | None = None


def get_db() -> Database:
    global _client, _db
    if _db is None:
        logger.info("Connecting to MongoDB at %s", MONGO_URI)
        _client = MongoClient(MONGO_URI)
        _db = _client.get_default_database()
        logger.info("Connected to database '%s'", _db.name)
    return _db


def close_db() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
