from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core import settings
from app.db import get_db
from app.i18n import SUPPORTED_LOCALES, detect_locale, translate
from app.models import PlanConfig, PricingConfig
from app.routers.deps import admin_user, current_user, optional_user
from app.services.policies import ensure_user_grants
from app.services.pricing import estimate_monthly_cost
from app.services.trading import dashboard_data

router = APIRouter(tags=["views"])
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


@router.get("/")
def home(request: Request, user=Depends(optional_user), db=Depends(get_db)):
    plans = db.query(PlanConfig).filter(PlanConfig.is_active.is_(True)).order_by(PlanConfig.sort_order.asc(), PlanConfig.id.asc()).all()
    pricing = db.query(PricingConfig).first()
    default_quote = estimate_monthly_cost(pricing, apps=3, symbols=15, daily_movements=20) if pricing else None
    return templates.TemplateResponse("index.html", base_context(
        request,
        title="Home",
        user=user,
        plans=plans,
        pricing=pricing,
        default_quote=default_quote,
        contact_name=settings.admin_name,
        contact_email=settings.admin_email,
    ))


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
