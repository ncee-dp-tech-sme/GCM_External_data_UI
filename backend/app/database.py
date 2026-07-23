"""
Database configuration and session management
Uses SQLAlchemy for ORM

Changes:
- 2026-07-25: Added migrate_db() to ADD new columns to existing tables without Alembic.
- 2026-07-25: Updated migrate_db() with confirmed GCM column set: added protocol_version,
  servicename, databasename, databasetype, version, application_id, patch.
  Removed contains_classified_data, is_encrypted, total_pqc_violation (not in GCM payload).
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=settings.debug
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency function to get database session
    Yields a database session and ensures it's closed after use
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def migrate_db():
    """Add new columns to existing tables (no-op if column already exists)."""
    migrations = [
        # it_assets — fields added 2026-07-25 (round 1)
        ("it_assets", "total_violation", "INTEGER"),
        ("it_assets", "pqc_readiness_flag", "VARCHAR"),
        ("it_assets", "exploitability_score", "FLOAT"),
        ("it_assets", "is_exception", "VARCHAR"),
        # it_assets — fields added 2026-07-25 (round 2, confirmed GCM payload)
        ("it_assets", "protocol_version", "VARCHAR"),
        ("it_assets", "servicename", "VARCHAR"),
        ("it_assets", "databasename", "VARCHAR"),
        ("it_assets", "databasetype", "VARCHAR"),
        ("it_assets", "version", "VARCHAR"),
        ("it_assets", "application_id", "VARCHAR"),
        ("it_assets", "patch", "VARCHAR"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in migrations:
            try:
                conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                    )
                )
                conn.commit()
            except Exception:
                # Column already exists — safe to ignore
                pass

# Made with Bob
