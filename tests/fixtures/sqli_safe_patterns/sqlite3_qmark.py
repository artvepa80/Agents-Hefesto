"""Fixture: sqlite3 ``?`` qmark-style placeholder (SAFE)."""


def fetch_user(cur, user_id):
    cur.execute("SELECT id, name FROM users WHERE id = ?", (user_id,))
    return cur.fetchone()


def delete_user(cur, user_id):
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
