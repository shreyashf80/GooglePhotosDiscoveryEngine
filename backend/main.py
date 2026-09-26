import os
import logging
import time
from contextvars import ContextVar
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Security, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastembed import TextEmbedding
from sqlalchemy import event

from backend.db import engine, _async_url
from backend.api import routes

logger = logging.getLogger(__name__)

query_count: ContextVar[int] = ContextVar("query_count", default=0)

if engine:
    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        query_count.set(query_count.get() + 1)

# Global model instance
embedding_model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global embedding_model
    logger.info("Loading BGE-small embedding model...")
    embedding_model = TextEmbedding("BAAI/bge-small-en-v1.5")
    logger.info("Model loaded.")
    yield
    if engine:
        await engine.dispose()

app = FastAPI(
    title="Recall Gap API",
    version="1.0.0",
    lifespan=lifespan
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    query_count.set(0)
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.warning(f"MEASURE: Route {request.url.path} took {process_time:.4f}s and ran {query_count.get()} SQL queries")
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-SQL-Queries"] = str(query_count.get())
    return response

ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="X-API-Key")
BACKEND_API_KEY = os.environ.get("BACKEND_API_KEY", "dev_key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != BACKEND_API_KEY:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key

app.include_router(routes.router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])

@app.get("/health")
async def health_check():
    db_ok = False
    try:
        if engine:
            async with engine.begin() as conn:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
    
    return {
        "status": "ok",
        "db_ok": db_ok,
        "model_loaded": embedding_model is not None,
        "is_using_async_db": bool(_async_url)
    }
