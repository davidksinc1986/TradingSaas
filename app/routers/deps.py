from fastapi import Depends, HTTPException, Request, status

from app.db import get_db
from app.models import User
from app.security import decode_access_token


def current_user(request: Request, db=Depends(get_db)) -> User:
    auth = request.cookies.get("access_token")
    if not auth:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")
    token = auth.removeprefix("Bearer ")
    email = decode_access_token(token)
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


def optional_user(request: Request, db=Depends(get_db)) -> User | None:
    auth = request.cookies.get("access_token")
    if not auth or not auth.startswith("Bearer "):
        return None
    token = auth.removeprefix("Bearer ")
    email = decode_access_token(token)
    if not email:
        return None
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        return None
    return user
