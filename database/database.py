from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from fastapi import Depends # type:ignore
from typing import Annotated
from utils.config import DataBase_config as dbconfig


class Base(DeclarativeBase):
    pass


class DatabaseManager:
    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        if not dbconfig.cloud_db:
            raise ValueError("Database URL (cloud_db) is not configured")

        self._engine = create_engine(
            dbconfig.cloud_db,
            echo=True,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=10,
            max_overflow=20
        )
        self._session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._engine
        )
        self._initialized = True

    @property
    def engine(self):
        return self._engine

    def get_session(self) -> Session:
        return self._session_factory()

    def get_db(self):
        db = self.get_session()
        try:
            yield db
        finally:
            db.close()

    def health_check(self) -> bool:
        """Verify database connection is alive."""
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"[DatabaseManager] Health check failed: {e}")
            return False

    def dispose(self) -> None:
        """Close all connections in the pool — call on app shutdown."""
        self._engine.dispose()
        print("[DatabaseManager] Connection pool disposed.")


# --- Single instance ---
db_manager = DatabaseManager()

# --- FastAPI dependency ---
db_dependency = Annotated[Session, Depends(db_manager.get_db)]