"""Fixture: psycopg2-style parameterized query (SAFE).

``%s`` is a DB-API placeholder, not a Python ``%`` operator — psycopg2
substitutes it server-side with proper escaping. Flagging this as SQL
injection is a classic production false positive.
"""


def fetch_user(cur, user_id):
    cur.execute("SELECT id, name FROM users WHERE id = %s", (user_id,))
    return cur.fetchone()


def fetch_active_between(cur, start, end):
    cur.execute(
        "SELECT id FROM users WHERE active = true AND created BETWEEN %s AND %s",
        (start, end),
    )
    return cur.fetchall()


def fetch_by_dict(cur, user_id):
    # Named-parameter form of the DB-API %s placeholder.
    cur.execute(
        "SELECT id FROM users WHERE id = %(uid)s",
        {"uid": user_id},
    )
    return cur.fetchone()
