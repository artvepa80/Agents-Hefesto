"""`.run(` on a process or event-loop runner is not a SQL execute sink.

``subprocess.run`` and ``asyncio.run`` used to satisfy the SQL sink pre-check,
so every file that only started a process or an event loop paid for the
string-span pass of the SQL injection check. Driver-style ``.run(`` calls
(for example pg8000's ``conn.run``) and the other sinks keep counting.
"""

import pytest

from hefesto.analyzers import security
from hefesto.analyzers.security import SecurityAnalyzer, _has_sql_sink


def _sqli(code: str):
    return SecurityAnalyzer()._check_sql_injection(None, "app.py", code)


@pytest.mark.parametrize(
    "line",
    [
        "subprocess.run(['ls'])",
        "asyncio.run(main())",
        "subprocess . run(cmd)",
        "x = 1\nsubprocess.run(cmd)",
        "result = asyncio.run(coro)",
    ],
)
def test_runner_calls_are_not_sql_sinks(line):
    assert not _has_sql_sink(line)


@pytest.mark.parametrize(
    "line",
    [
        "cursor.execute(q)",
        "cur.executemany(q, rows)",
        "conn.executescript(script)",
        "session.execute(text(q))",
        "engine.connect().execute(q)",
        "User.objects.raw(q)",
        "cur.mogrify(q, args)",
        "conn.run(q)",
        "await con.run(q)",
        "self.conn.run(q)",
        "subprocess.run(a)\ncursor.execute(q)",
        "asyncio.run(m())\nconn.run(q)",
        "pool.acquire().run(q)",
        "conns[0].run(q)",
    ],
)
def test_sql_sinks_still_match(line):
    assert _has_sql_sink(line)


def test_runner_only_file_builds_no_string_spans(monkeypatch):
    calls = []

    def spy(*args, **kwargs):
        calls.append(args)
        return []

    monkeypatch.setattr(security, "string_spans_for", spy)
    code = (
        "import asyncio, subprocess\n"
        "def main(name):\n"
        '    msg = "SELECT " + name\n'
        "    subprocess.run(['echo', msg])\n"
        "    asyncio.run(work())\n"
    )
    assert _sqli(code) == []
    assert calls == []


def test_concat_with_only_subprocess_run_is_not_flagged():
    code = (
        "def f(name):\n"
        '    q = "SELECT * FROM t WHERE n = \'" + name + "\'"\n'
        "    subprocess.run(['psql', '-c', q])\n"
    )
    assert _sqli(code) == []


def test_driver_run_still_flagged():
    code = (
        "def f(name):\n"
        '    q = "SELECT * FROM t WHERE n = \'" + name + "\'"\n'
        "    return conn.run(q)\n"
    )
    assert len(_sqli(code)) >= 1


def test_execute_next_to_subprocess_run_still_flagged():
    code = (
        "def f(name):\n"
        "    subprocess.run(['true'])\n"
        '    q = "SELECT * FROM t WHERE n = \'" + name + "\'"\n'
        "    cursor.execute(q)\n"
    )
    assert len(_sqli(code)) >= 1
