from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from urllib.parse import parse_qs

from app.api.deps import get_session, home_path_for, lookup_current_user, render_login_page
from app.core.security import sign_session_token
from app.models import User
from app.schema import LoginRequest, LoginResponse
from app.services import AuthenticationError, authenticate_user


router = APIRouter()


def _safe_next_path(next_path: str | None, *, fallback: str = "/") -> str:
    if next_path and next_path.startswith("/"):
        return next_path
    return fallback


def _set_session_cookie(response, *, request: Request, user: User) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        settings.session_cookie_name,
        sign_session_token(user_id=user.id, secret=settings.session_secret),
        httponly=True,
        samesite="lax",
    )


def _request_expects_json(request: Request) -> bool:
    return "application/json" in (request.headers.get("content-type") or "").lower()


async def _read_login_payload(request: Request) -> LoginRequest:
    if _request_expects_json(request):
        return LoginRequest.model_validate(await request.json())

    form = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    return LoginRequest.model_validate(
        {
            "email": form.get("email", [""])[0],
            "password": form.get("password", [""])[0],
            "next_path": form.get("next_path", ["/"])[0],
        }
    )


@router.get("/", include_in_schema=False)
def home(
    request: Request,
    session: Session = Depends(get_session),
):
    invalid_cookie, current_user = lookup_current_user(request, session)
    if current_user is not None:
        return RedirectResponse(home_path_for(current_user.role), status_code=status.HTTP_303_SEE_OTHER)

    next_path = _safe_next_path(request.query_params.get("next"))
    response = render_login_page(
        request=request,
        session=session,
        auth_error="Your session is no longer valid." if invalid_cookie else None,
        next_path=next_path,
    )
    if invalid_cookie:
        response.delete_cookie(request.app.state.settings.session_cookie_name)
    return response


@router.post("/login", include_in_schema=False)
async def login(
    request: Request,
    session: Session = Depends(get_session),
):
    expects_json = _request_expects_json(request)
    try:
        payload = await _read_login_payload(request)
    except ValidationError:
        if expects_json:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Email and password are required")
        return render_login_page(
            request=request,
            session=session,
            auth_error="Enter both email and password.",
            next_path="/",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    try:
        user = authenticate_user(
            session,
            email=payload.email,
            password=payload.password,
            demo_mode=request.app.state.settings.demo_mode,
        )
    except AuthenticationError as exc:
        if expects_json:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        return render_login_page(
            request=request,
            session=session,
            auth_error=str(exc),
            next_path=payload.next_path,
            email_value=payload.email,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    redirect_path = _safe_next_path(payload.next_path, fallback=home_path_for(user.role))
    if redirect_path == "/":
        redirect_path = home_path_for(user.role)

    if expects_json:
        response = JSONResponse(LoginResponse(redirect_path=redirect_path).model_dump())
    else:
        response = RedirectResponse(redirect_path, status_code=status.HTTP_303_SEE_OTHER)
    _set_session_cookie(response, request=request, user=user)
    return response


@router.post("/logout", include_in_schema=False)
def logout(request: Request):
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(request.app.state.settings.session_cookie_name)
    return response


@router.get("/switch-user", include_in_schema=False)
def switch_user(
    request: Request,
    email: str,
    next: str = "/",
    session: Session = Depends(get_session),
):
    if not request.app.state.settings.demo_mode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    user = session.scalar(select(User).where(User.email == email).limit(1))
    if user is None or not user.is_demo_account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown user")

    safe_next = _safe_next_path(next, fallback=home_path_for(user.role))
    response = RedirectResponse(safe_next, status_code=status.HTTP_303_SEE_OTHER)
    _set_session_cookie(response, request=request, user=user)
    return response
