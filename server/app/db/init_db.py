"""Create all database tables.

Run with:  python -m app.db.init_db
"""
from __future__ import annotations

from app.db.database import Base, engine
# Importing the models package registers every table on Base.metadata.
import app.models  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    tables = ", ".join(sorted(Base.metadata.tables.keys()))
    print(f"Database initialized. Tables created: {tables}")


if __name__ == "__main__":
    init_db()
