"""
EducAgent — Multi-Agent AI Student Assistant
FastAPI entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup: ensure RAG index is ready if PDFs exist
    from rag.indexer import build_index_if_needed
    try:
        build_index_if_needed()
    except Exception as e:
        print(f"[!] Warning: Could not build index on startup: {e}")

    # Initialize Redis connection
    from api.redis_client import redis_client
    try:
        await redis_client.connect()
    except Exception as e:
        print(f"[!] Warning: Redis not available: {e}")

    print("[+] EducAgent backend is ready.")
    yield

    # Shutdown: cleanup
    from api.generation import generation_manager
    await generation_manager.cleanup()

    from api.redis_client import redis_client as rc
    await rc.close()

    print("[*] EducAgent shutting down.")


app = FastAPI(
    title="EducAgent",
    description="Multi-Agent AI Student Assistant API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    
    status_code = 500
    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        
    return JSONResponse(
        status_code=status_code,
        content={"detail": str(getattr(exc, "detail", str(exc)))},
        headers={"Access-Control-Allow-Origin": "*"}
    )


@app.get("/")
async def root():
    return {
        "name": "EducAgent",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }
