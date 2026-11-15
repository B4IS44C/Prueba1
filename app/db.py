import sqlite3
import threading
import time

_lock = threading.Lock()


def connect(path):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE,
            received_at REAL,          -- cuando la app lo procesó
            sent_at TEXT,              -- fecha del correo
            sender TEXT,
            subject TEXT,
            kind TEXT,                 -- simpe | transferencia | otro
            direction TEXT,            -- recibido | enviado | desconocido
            person TEXT,
            reference TEXT,
            amount REAL,
            currency TEXT,
            notified INTEGER DEFAULT 0,
            notify_error TEXT
        );
        CREATE TABLE IF NOT EXISTS push_subs (
            endpoint TEXT PRIMARY KEY,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            created_at REAL
        );
        CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT);
        """
    )
    conn.commit()
    return conn


def set_state(conn, key, value):
    with _lock:
        conn.execute("INSERT INTO state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        conn.commit()


def get_state(conn, key, default=None):
    r = conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def insert_email(conn, row):
    """Devuelve el id nuevo, o None si el correo ya estaba registrado."""
    with _lock:
        try:
            cur = conn.execute(
                """INSERT INTO emails(message_id,received_at,sent_at,sender,subject,kind,direction,person,reference,amount,currency)
                   VALUES(:message_id,:received_at,:sent_at,:sender,:subject,:kind,:direction,:person,:reference,:amount,:currency)""",
                {"received_at": time.time(), **row},
            )
        except sqlite3.IntegrityError:
            return None
        conn.commit()
        return cur.lastrowid


def mark_notified(conn, row_id, error=None):
    with _lock:
        conn.execute("UPDATE emails SET notified=?, notify_error=? WHERE id=?", (0 if error else 1, error, row_id))
        conn.commit()


def add_push_sub(conn, endpoint, p256dh, auth):
    with _lock:
        conn.execute(
            "INSERT INTO push_subs(endpoint,p256dh,auth,created_at) VALUES(?,?,?,?) "
            "ON CONFLICT(endpoint) DO UPDATE SET p256dh=excluded.p256dh, auth=excluded.auth",
            (endpoint, p256dh, auth, time.time()),
        )
        conn.commit()


def remove_push_sub(conn, endpoint):
    with _lock:
        conn.execute("DELETE FROM push_subs WHERE endpoint=?", (endpoint,))
        conn.commit()


def list_push_subs(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM push_subs")]
