from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin_router, common_router, contractor_router, jobs_router, resident_router
from app.api.deps import APP_DIR, user_query
from app.core.config import Settings, load_settings
from app.core.database import build_engine, build_session_factory, require_schema_ready
from app.core.security import verify_session_token
from app.models import User
from app.services import ensure_bootstrap_user, ensure_demo_data


def create_app(
    database_url: str | None = None,
    *,
    settings_override: Settings | None = None,
    demo_mode: bool | None = None,
) -> FastAPI:
    app_settings = settings_override or load_settings(
        database_url=database_url,
        demo_mode=demo_mode,
    )
    if database_url is not None and app_settings.database_url != database_url:
        app_settings = replace(app_settings, database_url=database_url)
    if demo_mode is not None and app_settings.demo_mode != demo_mode:
        app_settings = replace(
            app_settings,
            demo_mode=demo_mode,
            seed_demo_data=app_settings.seed_demo_data if demo_mode else False,
        )

    engine = build_engine(app_settings.database_url)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            require_schema_ready(engine)
            if app_settings.seed_demo_data:
                with session_factory() as session:
                    ensure_demo_data(session, demo_password=app_settings.demo_password)
                    ensure_bootstrap_user(
                        session,
                        name=app_settings.bootstrap_user_name,
                        email=app_settings.bootstrap_user_email,
                        password=app_settings.bootstrap_user_password,
                        organisation_name=app_settings.bootstrap_user_org_name,
                        role=app_settings.bootstrap_user_role,
                    )
                    session.commit()
            elif app_settings.bootstrap_user_email and app_settings.bootstrap_user_password:
                with session_factory() as session:
                    ensure_bootstrap_user(
                        session,
                        name=app_settings.bootstrap_user_name,
                        email=app_settings.bootstrap_user_email,
                        password=app_settings.bootstrap_user_password,
                        organisation_name=app_settings.bootstrap_user_org_name,
                        role=app_settings.bootstrap_user_role,
                    )
                    session.commit()
            yield
        finally:
            engine.dispose()

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)
    app.state.engine = engine
    app.state.SessionLocal = session_factory
    app.state.settings = app_settings
    app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

    @app.middleware("http")
    async def resolve_request_user(request: Request, call_next):
        request.state.current_user = None
        request.state.invalid_session = False

        session_token = (request.cookies.get(app_settings.session_cookie_name) or "").strip()
        if session_token:
            user_id = verify_session_token(session_token, secret=app_settings.session_secret)
            if user_id is None:
                request.state.invalid_session = True
            else:
                with session_factory() as auth_session:
                    user = auth_session.scalar(user_query().where(User.id == user_id).limit(1))
                if user is None:
                    request.state.invalid_session = True
                else:
                    request.state.current_user = user

        if request.url.path.startswith("/api") and request.state.current_user is None:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
            )

        return await call_next(request)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        if exc.status_code == status.HTTP_401_UNAUTHORIZED and not request.url.path.startswith("/api"):
            next_path = request.url.path if request.url.path.startswith("/") else "/"
            return RedirectResponse(f"/?next={quote(next_path)}", status_code=status.HTTP_303_SEE_OTHER)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)

    app.include_router(common_router)
    app.include_router(jobs_router)
    app.include_router(resident_router)
    app.include_router(admin_router)
    app.include_router(contractor_router)

    return app


app = create_app()
