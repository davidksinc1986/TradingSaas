from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import get_db
from app.i18n import SUPPORTED_LOCALES, detect_locale, translate
from app.models import User
from app.schemas import UserLogin
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


def base_context(request: Request, **kwargs):
    locale = detect_locale(request)
    ctx = {
        "request": request,
        "locale": locale,
        "supported_locales": SUPPORTED_LOCALES,
        "tr": lambda key: translate(key, locale),
    }
    ctx.update(kwargs)
    return ctx


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", base_context(request, title="Login"))


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    raise HTTPException(status_code=403, detail="Self registration is disabled. Contact admin.")


@router.post("/register")
def register(email: str = Form(...), name: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    raise HTTPException(status_code=403, detail="Self registration is disabled. Contact admin.")


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    payload = UserLogin(email=email, password=password)
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled by admin")
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
