"""
test_hybrid_conn_sync_commit.py — covers _HybridConn.commit() in database.py.

_restore_from_turso() rebuilds the local SQLite file from Turso on every
container boot (the local file lives in the container's ephemeral
filesystem, not Railway's persistent volume, when running in hybrid mode).
commit() used to push writes to Turso in a background daemon thread and
return immediately — so if the container redeployed before that thread
finished, the write never reached Turso, and the next boot's restore threw
it away with no error anywhere. This happened for real: ~50 rows inserted
by /admin/recover-montos were lost this way when a routine redeploy landed
minutes later.

commit() must now block until the Turso sync attempt has actually
finished, so "committed" means the same thing to the caller as it will to
the next container boot.
"""
import sys, os, threading, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def test_commit_blocks_until_turso_sync_returns(monkeypatch):
    calls = []

    def fake_turso_sync(host, token, writes):
        calls.append((host, token, list(writes)))
        time.sleep(0.05)  # simulate network latency

    monkeypatch.setattr(database, "_turso_sync", fake_turso_sync)

    conn = database._HybridConn(":memory:", "fake-host", "fake-token")
    conn._db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES (?)", ("hello",))

    conn.commit()  # must not return before fake_turso_sync has run

    assert len(calls) == 1, "commit() must synchronously invoke the Turso sync exactly once"
    assert calls[0][0] == "fake-host"
    assert "INSERT INTO t" in calls[0][2][0]["sql"]


def test_commit_does_not_spawn_a_background_thread(monkeypatch):
    active_before = threading.active_count()

    def fake_turso_sync(host, token, writes):
        pass

    monkeypatch.setattr(database, "_turso_sync", fake_turso_sync)

    conn = database._HybridConn(":memory:", "fake-host", "fake-token")
    conn._db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES (?)", ("hello",))
    conn.commit()

    # Give any stray thread a moment to appear, then confirm none did.
    time.sleep(0.05)
    assert threading.active_count() == active_before


def test_commit_with_no_writes_does_not_call_turso_sync(monkeypatch):
    calls = []
    monkeypatch.setattr(database, "_turso_sync", lambda *a: calls.append(a))

    conn = database._HybridConn(":memory:", "fake-host", "fake-token")
    conn._db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.commit()  # nothing written yet

    assert calls == []


def test_a_write_followed_by_immediate_restore_is_not_lost(monkeypatch):
    # Simulates the exact failure: commit(), then (as if the container had
    # just redeployed) _restore_from_turso pulls straight back from what
    # was actually sent to Turso. With a synchronous commit, that data
    # must already be there.
    turso_state = {}  # host -> table -> list[dict]

    def fake_turso_sync(host, token, writes):
        for w in writes:
            turso_state.setdefault(host, []).append(w)

    monkeypatch.setattr(database, "_turso_sync", fake_turso_sync)

    conn = database._HybridConn(":memory:", "fake-host", "fake-token")
    conn._db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES (?)", ("recovered-row",))
    conn.commit()

    # If a redeploy happened right here (as it did in production), Turso
    # must already have the write.
    assert any("recovered-row" in str(w["args"]) for w in turso_state["fake-host"])
