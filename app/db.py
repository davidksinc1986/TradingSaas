import sqlite3
import time

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core import settings

connect_args = {"check_same_thread": False, "timeout": 30} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()


def is_sqlite_locked_error(exc: Exception) -> bool:
    if not settings.database_url.startswith("sqlite"):
        return False
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


def rollback_safely(db) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def commit_with_retry(db, *, attempts: int = 3, delay_seconds: float = 0.2):
    last_exc = None
    for attempt in range(1, max(attempts, 1) + 1):
        try:
            db.commit()
            return
        except OperationalError as exc:
            rollback_safely(db)
            last_exc = exc
            if not is_sqlite_locked_error(exc) or attempt >= attempts:
                raise
            time.sleep(delay_seconds * attempt)
        except Exception:
            rollback_safely(db)
            raise
    if last_exc is not None:
        raise last_exc


def flush_with_retry(db, *, attempts: int = 3, delay_seconds: float = 0.2):
    last_exc = None
    for attempt in range(1, max(attempts, 1) + 1):
        try:
            db.flush()
            return
        except OperationalError as exc:
            rollback_safely(db)
            last_exc = exc
            if not is_sqlite_locked_error(exc) or attempt >= attempts:
                raise
            time.sleep(delay_seconds * attempt)
        except Exception:
            rollback_safely(db)
            raise
    if last_exc is not None:
        raise last_exc


@event.listens_for(engine, "connect")
def configure_sqlite_connection(dbapi_connection, _connection_record):
    if not settings.database_url.startswith("sqlite") or not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        rollback_safely(db)
        raise
    finally:
        db.close()
