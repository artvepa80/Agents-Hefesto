"""Fixture: Django ORM raw() with params list (SAFE)."""


def fetch_users(User, min_id):
    # Django's raw() takes a params list and substitutes %s safely.
    return User.objects.raw(
        "SELECT id, name FROM users WHERE id >= %s",
        [min_id],
    )
