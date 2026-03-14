from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core import settings
from app.db import get_db
from app.i18n import SUPPORTED_LOCALES, detect_locale, translate
from app.models import User
from app.services.alerts import format_failure_message, send_telegram_alert_sync
from app.schemas import UserLogin
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


def base_context(request: Request, **kwargs):
    locale = detect_locale(request)
    ctx = {
        "request": request,
        "static_version": settings.static_version,
        "locale": locale,
        "supported_locales": SUPPORTED_LOCALES,
        "tr": lambda key: translate(key, locale),
    }
    ctx.update(kwargs)
    return ctx


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    error = request.query_params.get("error")
    return templates.TemplateResponse("login.html", base_context(request, title="Login", error=error))


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    raise HTTPException(status_code=403, detail="Self registration is disabled. Contact admin.")


@router.post("/register")
def register(email: str = Form(...), name: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    raise HTTPException(status_code=403, detail="Self registration is disabled. Contact admin.")


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    payload = UserLogin(email=email.strip().lower(), password=password)
    user = db.query(User).filter(User.email == payload.email).first()
    accepts_html = "text/html" in (request.headers.get("accept") or "")

    def _fail(detail_html: str, detail_api: str, code: int):
        send_telegram_alert_sync(format_failure_message("Login", f"email={payload.email} reason={detail_api}"))
        if accepts_html:
            return templates.TemplateResponse(
                "login.html",
                base_context(request, title="Login", error=detail_html),
                status_code=code,
            )
        raise HTTPException(status_code=code, detail=detail_api)

    if not user:
        return _fail("Cannot find user", "cannot find user", status.HTTP_401_UNAUTHORIZED)

    if not verify_password(payload.password, user.hashed_password):
        return _fail("Incorrect password", "incorrect password", status.HTTP_401_UNAUTHORIZED)

    if not user.is_active:
        return _fail("Unable to login: account disabled by admin", "unable to login: account disabled", status.HTTP_403_FORBIDDEN)

    token = create_access_token(user.email)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        "access_token",
        f"Bearer {token}",
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        max_age=60 * 60 * 12,
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie("access_token")
    return response
