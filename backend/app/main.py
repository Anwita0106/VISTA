"""FastAPI entry point: routers, security headers, CORS, health check, SPA hosting."""
import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .config import settings
from .database import SessionLocal, engine
from .routers import accommodation, admin, auth, communication, community, complaints, delivery, profile, service_requests, sos, visitors
from .services import run_escalation

log = logging.getLogger("vista")


async def escalation_loop() -> None:
    while True:
        await asyncio.sleep(settings.escalation_check_seconds)
        try:
            with SessionLocal() as db:
                done = run_escalation(db)
                if done:
                    log.info("Escalated %d complaint(s)", len(done))
        except Exception:  # pragma: no cover - keep the loop alive
            log.exception("Escalation check failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.database_url.startswith("sqlite"):
        # Local SQLite demo: create the tables and load the demo data on first start,
        # so a fresh copy works even if `python -m app.seed` was not run.
        from .seed import create_schema, seed

        create_schema()
        with SessionLocal() as db:
            seed(db)
    task = asyncio.create_task(escalation_loop()) if settings.escalation_check_seconds > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="VISTA API", version="1.0.0", lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=(self)"
    if not request.url.path.startswith("/api/docs"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        )
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - start) * 1000:.1f}"
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    errors = []
    for e in exc.errors():
        field = ".".join(str(p) for p in e.get("loc", []) if p not in ("body", "query", "path"))
        msg = e.get("msg", "Invalid value").removeprefix("Value error, ")
        errors.append({"field": field, "message": msg})
    first = errors[0] if errors else {"field": "", "message": "Invalid input"}
    detail = f"{first['field']}: {first['message']}" if first["field"] else first["message"]
    return JSONResponse(status_code=422, content={"detail": detail, "errors": errors})


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):  # pragma: no cover
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. Please try again."})


for r in (auth, profile, accommodation, complaints, visitors, service_requests, sos, communication, community,
          delivery, admin):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return JSONResponse(status_code=200 if db_ok else 503,
                        content={"status": "ok" if db_ok else "degraded", "database": db_ok, "version": app.version})


# ---- serve the built React app (single-service deployment) ----
dist = settings.frontend_dist
if dist.is_dir() and (dist / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")
