import email
import email.utils
import imaplib
import threading
import time
from email.header import decode_header, make_header

from . import db, notifier
from .parser import html_to_text, parse_email


def _decode(v):
    try:
        return str(make_header(decode_header(v or "")))
    except Exception:
        return v or ""


def extract_body(msg):
    plain, htm = [], []
    for part in msg.walk():
        if part.get_content_maintype() != "text" or part.get_filename():
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        (htm if part.get_content_subtype() == "html" else plain).append(text)
    if plain:
        return "\n".join(plain)
    return html_to_text("\n".join(htm))


def process_message(conn, cfg, raw, fallback_id):
    """Procesa un correo crudo. Devuelve la fila guardada o None si ya existía/se filtró."""
    msg = email.message_from_bytes(raw)
    sender = _decode(msg.get("From"))
    if cfg["allowed_senders"] and not any(s in sender.lower() for s in cfg["allowed_senders"]):
        return None
    subject = _decode(msg.get("Subject"))
    parsed = parse_email(subject, extract_body(msg))
    row = {
        "message_id": (msg.get("Message-ID") or fallback_id).strip(),
        "sent_at": msg.get("Date") or "",
        "sender": sender,
        "subject": subject,
        **parsed,
    }
    row_id = db.insert_email(conn, row)
    if row_id is None:
        return None
    row["id"] = row_id
    if row["kind"] != "otro":
        err = notifier.send(cfg, notifier.build_message(row))
        db.mark_notified(conn, row_id, err)
        row["notify_error"] = err
    return row


def check_once(conn, cfg):
    imap = imaplib.IMAP4_SSL(cfg["imap_host"])
    try:
        imap.login(cfg["imap_user"], cfg["imap_password"])
        imap.select(cfg["imap_folder"], readonly=True)
        last = db.get_state(conn, "last_uid")
        if last is None:
            if cfg["initial_days"] > 0:
                since = time.strftime("%d-%b-%Y", time.gmtime(time.time() - cfg["initial_days"] * 86400))
                _, data = imap.uid("search", None, "SINCE", since)
                uids = [int(u) for u in data[0].split()]
                last = (min(uids) - 1) if uids else 0
            else:
                _, data = imap.uid("search", None, "ALL")
                uids = [int(u) for u in data[0].split()]
                last = max(uids) if uids else 0
            db.set_state(conn, "last_uid", last)
        last = int(last)
        _, data = imap.uid("search", None, f"UID {last + 1}:*")
        uids = sorted(int(u) for u in data[0].split() if int(u) > last)
        for uid in uids:
            _, fetched = imap.uid("fetch", str(uid), "(BODY.PEEK[])")
            raw = next((p[1] for p in fetched if isinstance(p, tuple)), None)
            if raw:
                process_message(conn, cfg, raw, f"uid-{uid}")
            db.set_state(conn, "last_uid", uid)
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def run_forever(conn, cfg, stop: threading.Event):
    alerted = False
    while not stop.is_set():
        try:
            check_once(conn, cfg)
            db.set_state(conn, "last_check", time.time())
            db.set_state(conn, "last_error", "")
        except Exception as e:
            db.set_state(conn, "last_error", f"{type(e).__name__}: {e}")
        if cfg["silence_hours"] > 0:
            r = conn.execute("SELECT MAX(received_at) m FROM emails WHERE kind!='otro'").fetchone()
            quiet = r["m"] and (time.time() - r["m"]) > cfg["silence_hours"] * 3600
            if quiet and not alerted:
                notifier.send(cfg, f"⚠️ Hace más de {cfg['silence_hours']:g} h que no llega ningún SINPE/transferencia.")
                alerted = True
            elif not quiet:
                alerted = False
        stop.wait(cfg["poll_seconds"])
