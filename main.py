import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.database import init_db
from app.redis_client import init_redis
from app.storage import get_s3_client
from app.routers.admin import router as admin_router
from app.routers.auth import limiter as auth_limiter, router as auth_router
from app.routers.images import router as images_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Grabpic")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = auth_limiter
app.add_middleware(SlowAPIMiddleware)

app.include_router(admin_router, prefix="/admin")
app.include_router(auth_router, prefix="/auth")
app.include_router(images_router, prefix="/images")

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Starting Grabpic backend")
    await init_db()
    await init_redis()
    await asyncio.to_thread(get_s3_client)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})


@app.get("/")
async def serve_frontend():
    return FileResponse("frontend/index.html")

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "grabpic"}
