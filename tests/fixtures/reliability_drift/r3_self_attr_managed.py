"""R3 negative fixture: self-managed connection with explicit close() method.

Mirrors the lazy-getter cache pattern observed in
``swarm/storage/sqlite_store.py`` (PRO repo) which triggered an R3 false
positive during EPIC 4 Phase D warn soak (FP-1, 2026-05-08).

Expected behavior: R3 must NOT emit a finding for ``self._conn`` because
the same class defines a ``close()`` method that closes the connection.
"""

import sqlite3


class SwarmStoreLike:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
