from contextlib import contextmanager
from typing import Iterator, Optional, TypeVar

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# Adjust to your project: if database.py already exposes get_db, import that instead
# and delete the function below.
from database.database import db_manager


def get_db() -> Iterator[Session]:
    db = db_manager.get_session()
    try:
        yield db
    finally:
        db.close()


T = TypeVar("T")


def or_404(obj: Optional[T], what: str = "Resource") -> T:
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return obj


@contextmanager
def conflict_as_409():
    """Translate DB integrity errors (duplicate key, bad foreign key) into HTTP 409."""
    try:
        yield
    except IntegrityError as e:
        raise HTTPException(
            status_code=409,
            detail="Integrity constraint violated (duplicate record or invalid foreign key)") from e
