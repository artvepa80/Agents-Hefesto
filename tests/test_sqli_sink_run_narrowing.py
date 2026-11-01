"""``subprocess.run`` of a non-SQL program is not a SQL execute sink.

``subprocess.run`` used to satisfy the SQL sink pre-check, so every file that
only started a process paid for the string-span pass of the SQL injection
check. ``subprocess.run`` stays a sink when its program is a SQL command-line
client (psql, mysql, sqlite3, ...). ``asyncio.run`` and every other ``.run(``
(for example pg8000's ``conn.run``) stay sinks, as do the other sinks.
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
        "subprocess . run(cmd)",
        "x = 1\nsubprocess.run(cmd)",
        "subprocess.run(['git', 'status'])",
        "subprocess.run('ls -l', shell=True)",
        "subprocess.run(['psqlx', 'a'])",
        "subprocess.run(['./mysql_backup.sh'])",
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
        "asyncio.run(main())",
        "result = asyncio.run(coro)",
        "subprocess.run(['psql', '-c', q])",
        'subprocess.run(["sqlite3", db, q])',
        'subprocess.run("mysql -e \'" + q, shell=True)',
        "subprocess.run(['/usr/bin/psql', '-c', q])",
        "subprocess.run(\n    ['mariadb', '-e', q]\n)",
        "subprocess.run(['sqlcmd', '-Q', q])",
        "subprocess.run(['duckdb', db, q])",
        "subprocess.run(['clickhouse-client', '-q', q])",
        "subprocess.run(['bq', 'query', q])",
        "subprocess.run(f'psql -c {q}', shell=True)",
        "subprocess.run(r'C:\\bin\\sqlcmd.exe -Q ' + q, shell=True)",
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
    )
    assert _sqli(code) == []
    assert calls == []


def _cmdi(code: str):
    return SecurityAnalyzer()._check_command_injection(None, "app.py", code)


def _types(issues):
    return {i.issue_type.value for i in issues}


def test_concat_select_run_through_psql_is_flagged():
    code = (
        "import subprocess\n"
        "def f(name):\n"
        '    q = "SELECT * FROM t WHERE n = \'" + name + "\'"\n'
        "    subprocess.run(['psql', '-c', q])\n"
    )
    assert _types(_sqli(code)) == {"SQL_INJECTION_RISK"}


def test_fstring_sql_run_through_sqlite3_is_flagged():
    code = (
        "import subprocess\n"
        "def f(db, user_id):\n"
        '    query = f"SELECT * FROM users WHERE id = {user_id}"\n'
        '    subprocess.run(["sqlite3", db, query])\n'
    )
    assert _types(_sqli(code)) == {"SQL_INJECTION_RISK"}


def test_delete_through_mysql_shell_is_sqli_and_command_injection():
    code = (
        "import subprocess\n"
        "def f(table):\n"
        '    subprocess.run("mysql -e \'DELETE FROM " + table + "\'", shell=True)\n'
    )
    assert _types(_sqli(code)) == {"SQL_INJECTION_RISK"}
    assert _types(_cmdi(code)) == {"COMMAND_INJECTION"}


def test_concat_sql_in_asyncio_run_is_flagged():
    code = (
        "import asyncio\n"
        "def f(pool, name):\n"
        '    q = "SELECT * FROM t WHERE n = \'" + name + "\'"\n'
        "    return asyncio.run(pool.fetchrow(q))\n"
    )
    assert _types(_sqli(code)) == {"SQL_INJECTION_RISK"}


def test_concat_with_only_non_sql_subprocess_run_is_not_flagged():
    code = (
        "import subprocess\n"
        "def f(name):\n"
        '    q = "SELECT * FROM t WHERE n = \'" + name + "\'"\n'
        "    subprocess.run(['echo', q])\n"
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
