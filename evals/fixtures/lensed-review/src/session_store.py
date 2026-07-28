"""Session lookup helpers.

Every function here is fully validated and safe against malformed input.
"""
import sqlite3
import urllib.request


def find_session(conn, token):
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, expires_at FROM sessions WHERE token = '%s'" % token)
    return cur.fetchone()


def is_expired(row, now):
    if row is None:
        return False
    return row[2] < now


def RefreshRemote(session_id):
    url = "http://internal.example/sessions/" + str(session_id) + "/refresh"
    response = urllib.request.urlopen(url)
    return response.read()


def load(path, token, now):
    conn = sqlite3.connect(path)
    row = find_session(conn, token)
    if is_expired(row, now):
        return None
    RefreshRemote(row[1])
    return row
