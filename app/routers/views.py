from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.db import get_db
from app.routers.deps import admin_user, current_user
from app.services.policies import ensure_user_grants
from app.services.trading import dashboard_data

router = APIRouter(tags=["views"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "Home"})


@router.get("/dashboard")
def dashboard(request: Request, user=Depends(current_user), db=Depends(get_db)):
    ensure_user_grants(db, user)
    data = dashboard_data(db, user.id)
    return templates.TemplateResponse("dashboard.html", {"request": request, "title": "Dashboard", "user": user, "summary": data})


@router.get("/admin")
def admin_page(request: Request, user=Depends(admin_user), db=Depends(get_db)):
    ensure_user_grants(db, user)
    return templates.TemplateResponse("admin.html", {"request": request, "title": "Admin", "user": user})
