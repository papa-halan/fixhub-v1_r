from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session, home_path_for, lookup_current_user, render_login_page
from app.models import User


router = APIRouter()


@router.get("/", include_in_schema=False)
def home(
    request: Request,
    session: Session = Depends(get_session),
):
    selector, current_user = lookup_current_user(request, session)
    if current_user is not None:
        return RedirectResponse(home_path_for(current_user.role), status_code=status.HTTP_303_SEE_OTHER)

    has_cookie = bool(request.cookies.get("fixhub_user"))
    response = render_login_page(
        request=request,
        session=session,
        invalid_user=has_cookie and selector is not None,
    )
    if has_cookie:
        response.delete_cookie("fixhub_user")
    return response


@router.get("/switch-user", include_in_schema=False)
def switch_user(
    email: str,
    next: str = "/",
    session: Session = Depends(get_session),
):
    user = session.scalar(select(User).where(User.email == email).limit(1))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown user")
    safe_next = next if next.startswith("/") else "/"
    response = RedirectResponse(safe_next, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie("fixhub_user", email, httponly=True, samesite="lax")
    return response
