from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()

# ---------------------------------------------------------------------
# Database config
# ---------------------------------------------------------------------

# Dossier racine du backend (là où se trouve db.py)
BASE_DIR = Path(__file__).resolve().parent

# SQLite local toujours au même endroit: <backend>/data/tore.db (chemin ABSOLU)
DEFAULT_SQLITE_PATH = BASE_DIR / "data" / "tore.db"
DEFAULT_SQLITE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)

# Render/Heroku donnent parfois postgres:// -> SQLAlchemy veut postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    # Normalise la DB sqlite en chemin ABSOLU même si on te met un sqlite relatif en env
    # Formats possibles:
    # - sqlite:///relative/path.db
    # - sqlite:////absolute/path.db
    sqlite_path_str = DATABASE_URL.replace("sqlite:///", "", 1)
    sqlite_path = Path(sqlite_path_str)

    if not sqlite_path.is_absolute():
        sqlite_path = (BASE_DIR / sqlite_path).resolve()
        DATABASE_URL = f"sqlite:///{sqlite_path.as_posix()}"

    # Crée le dossier parent du fichier sqlite (ex: <backend>/data)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def now_utc() -> datetime:
    return datetime.utcnow()


def get_session() -> Session:
    return SessionLocal()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
