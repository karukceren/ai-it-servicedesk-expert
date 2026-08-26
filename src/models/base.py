"""
SQLAlchemy Base & Database Connection Configuration
====================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Provides the declarative base, engine initialization with active host discovery,
    session factory, and FastAPI dependency helpers.
"""

import os
import subprocess
from pathlib import Path
from typing import Generator, Optional, List

import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

# Load environment variables
project_root = Path(__file__).resolve().parent.parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy ORM models."""
    pass


def discover_db_host() -> str:
    """
    Actively probes database hosts (configured host, localhost, WSL IP)
    to find the active PostgreSQL instance in hybrid development environments.
    """
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_pass = os.getenv("POSTGRES_PASSWORD", "password123")
    db_name = os.getenv("POSTGRES_DB", "it_support_db")
    db_port = int(os.getenv("POSTGRES_PORT", "5432"))

    candidates: List[str] = []
    env_host = os.getenv("POSTGRES_HOST")
    if env_host and env_host not in ("localhost", "127.0.0.1"):
        candidates.append(env_host)

    candidates.extend(["localhost", "127.0.0.1"])

    # Try WSL discovery if on Windows
    commands = [
        ["wsl", "-d", "Ubuntu", "hostname", "-I"],
        ["wsl", "hostname", "-i"]
    ]
    for cmd in commands:
        try:
            out = subprocess.check_output(cmd, text=True, timeout=2).strip()
            ips = [x for x in out.split() if "." in x and not x.startswith("127.")]
            for ip in ips:
                if ip not in candidates:
                    candidates.append(ip)
        except Exception:
            continue

    # Probe candidates for active connection
    for h in candidates:
        try:
            conn = psycopg2.connect(
                host=h,
                port=db_port,
                user=db_user,
                password=db_pass,
                dbname=db_name,
                connect_timeout=1
            )
            conn.close()
            return h
        except Exception:
            continue

    return "localhost"


def get_database_url() -> str:
    """Constructs the PostgreSQL connection URL from environment or defaults."""
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_pass = os.getenv("POSTGRES_PASSWORD", "password123")
    db_name = os.getenv("POSTGRES_DB", "it_support_db")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_host = discover_db_host()

    return f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"


DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI & context manager dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initializes vector extension, all database tables, and seeds initial data."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
    except Exception as e:
        pass

    Base.metadata.create_all(bind=engine)

    # Automatically seed knowledge base chunks if empty
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM knowledge_base;")).scalar()
            if count == 0:
                from src.data.embed_and_store import VectorStoreManager
                active_host = discover_db_host()
                manager = VectorStoreManager(db_host=active_host)
                manager.run_pipeline()
    except Exception as e:
        pass
