from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import admin, attachments, auth, conversations, knowledge, public, settings as settings_api, turtles
from .config import PROJECT_DIR, get_settings
from .database import Base, SessionLocal, engine, get_db
from .services.rag import seed_knowledge_metadata


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    if get_db not in _app.dependency_overrides:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_knowledge_metadata(db, settings.knowledge_path)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in settings.allowed_origins:
            return JSONResponse(status_code=403, content={"detail": "不允許的請求來源。"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self' http://localhost:8000 http://127.0.0.1:8000"
    )
    return response


api_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(public.router, prefix=api_prefix)
if settings.enable_turtle_module:
    app.include_router(turtles.router, prefix=api_prefix)
app.include_router(attachments.router, prefix=api_prefix)
app.include_router(conversations.router, prefix=api_prefix)
app.include_router(knowledge.router, prefix=api_prefix)
app.include_router(settings_api.router, prefix=api_prefix)
app.include_router(admin.router, prefix=api_prefix)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "provider": settings.ai_provider,
        "model": settings.ai_model,
        "configured": bool(settings.ai_api_key),
    }


frontend_dist = PROJECT_DIR / "frontend" / "dist"
if (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    index = frontend_dist / "index.html"
    if index.exists():
        requested = (frontend_dist / full_path).resolve()
        if frontend_dist.resolve() in requested.parents and requested.is_file():
            return FileResponse(requested)
        return FileResponse(index)
    return JSONResponse(
        status_code=200,
        content={
            "message": f"{settings.app_name} API 已啟動；前端尚未建置。",
            "docs": "/api/docs",
        },
    )
