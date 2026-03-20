from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core import settings
from app.db import get_db
from app.i18n import SUPPORTED_LOCALES, detect_locale, translate
from app.routers.deps import admin_user, current_user
from app.services.policies import ensure_user_grants
from app.services.pricing import estimate_monthly_cost
from app.services.trading import dashboard_data

router = APIRouter(tags=["views"])
templates = Jinja2Templates(directory="app/templates")


def base_context(request: Request, **kwargs):
    locale = detect_locale(request)
    ctx = {
        "request": request,
        "locale": locale,
        "supported_locales": SUPPORTED_LOCALES,
        "static_version": settings.static_version,
        "tr": lambda key: translate(key, locale),
    }
    ctx.update(kwargs)
    return ctx


@router.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", base_context(request, title="Home"))


@router.get("/dashboard")
def dashboard(request: Request, user=Depends(current_user), db=Depends(get_db)):
    ensure_user_grants(db, user)
    data = dashboard_data(db, user.id)
    return templates.TemplateResponse("dashboard.html", base_context(request, title="Dashboard", user=user, summary=data))


@router.get("/admin")
def admin_page(request: Request, user=Depends(admin_user), db=Depends(get_db)):
    ensure_user_grants(db, user)
    return templates.TemplateResponse("admin.html", base_context(request, title="Admin", user=user))


@router.get("/set-language/{lang}")
def set_language(lang: str, request: Request):
    language = lang if lang in SUPPORTED_LOCALES else "es"
    response = RedirectResponse(url=request.headers.get("referer") or "/", status_code=303)
    response.set_cookie("lang", language, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response
