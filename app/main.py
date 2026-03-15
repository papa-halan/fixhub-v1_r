from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin_router, common_router, contractor_router, jobs_router, resident_router
from app.api.deps import APP_DIR, user_query
from app.core.config import settings
from app.core.database import build_engine, build_session_factory
from app.models import Base, User
from app.services import ensure_demo_data


def create_app(database_url: str | None = None) -> FastAPI:
    engine = build_engine(database_url)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Base.metadata.create_all(bind=engine)
        with session_factory() as session:
            ensure_demo_data(session)
            session.commit()
        yield

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.engine = engine
    app.state.SessionLocal = session_factory
    app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

    @app.middleware("http")
    async def resolve_api_user(request: Request, call_next):
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        user_email = (request.headers.get("X-User-Email") or "").strip()
        if not user_email:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "X-User-Email header required"},
            )

        with session_factory() as auth_session:
            user = auth_session.scalar(user_query().where(User.email == user_email).limit(1))

        if user is None:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unknown user"},
            )

        request.state.api_user_email = user_email
        return await call_next(request)

    app.include_router(common_router)
    app.include_router(jobs_router)
    app.include_router(resident_router)
    app.include_router(admin_router)
    app.include_router(contractor_router)

    return app


app = create_app()
