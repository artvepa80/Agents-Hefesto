"""Fixture: SQLAlchemy ``text()`` with bind parameters (SAFE)."""

from sqlalchemy import text


def fetch_user(conn, user_id):
    result = conn.execute(
        text("SELECT id, name FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    )
    return result.fetchone()
