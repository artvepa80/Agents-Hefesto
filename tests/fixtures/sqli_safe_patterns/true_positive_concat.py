"""Fixture: TRUE POSITIVE — real SQL injection via user-controlled concat.

This fixture MUST continue firing after the precision fix. If it stops
firing, we have over-tightened the detector and regressed on recall.
"""


def fetch_user_unsafe(cur, user_id):
    # Classic injection: user_id spliced into the literal via f-string.
    cur.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cur.fetchone()


def fetch_by_name_unsafe(cur, name):
    # Classic % interpolation at the Python level (not DB-API).
    query = "SELECT * FROM users WHERE name = '%s'" % name
    cur.execute(query)
    return cur.fetchone()


def fetch_by_status_unsafe(cur, status):
    # String concat with user input.
    cur.execute("SELECT * FROM users WHERE status = '" + status + "'")
    return cur.fetchone()
