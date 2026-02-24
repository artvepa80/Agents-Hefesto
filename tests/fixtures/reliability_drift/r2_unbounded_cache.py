# Fixture: R2 — @lru_cache(maxsize=None)
from functools import lru_cache


@lru_cache(maxsize=None)
def get_user(user_id):
    return {"id": user_id, "name": f"User {user_id}"}
