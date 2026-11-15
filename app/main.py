import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import db, mailwatch, notifier
from .config import settings

cfg = settings()
conn = db.connect(cfg["db_path"])
stop = threading.Event()
security = HTTPBasic()


def auth(c: HTTPBasicCredentials = Depends(security)):
    if not cfg["app_password"]:
        raise HTTPException(503, "Defina APP_PASSWORD en .env")
    if not (secrets.compare_digest(c.username, "admin") and secrets.compare_digest(c.password, cfg["app_password"])):
        raise HTTPException(401, "No autorizado", headers={"WWW-Authenticate": "Basic"})


@asynccontextmanager
async def lifespan(app):
    t = None
    if cfg["imap_user"] and cfg["imap_password"]:
        t = threading.Thread(target=mailwatch.run_forever, args=(conn, cfg, stop), daemon=True)
        t.start()
    yield
    stop.set()


app = FastAPI(title="Monitor SINPE", lifespan=lifespan)


@app.get("/", dependencies=[Depends(auth)])
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/transactions", dependencies=[Depends(auth)])
def transactions(kind: str = "", q: str = "", limit: int = 200):
    sql, args = "SELECT * FROM emails WHERE 1=1", []
    if kind in ("simpe", "transferencia", "otro"):
        sql += " AND kind=?"; args.append(kind)
    elif kind != "all":
        sql += " AND kind!='otro'"
    if q:
        sql += " AND (person LIKE ? OR reference LIKE ? OR subject LIKE ?)"; args += [f"%{q}%"] * 3
    sql += " ORDER BY received_at DESC LIMIT ?"; args.append(min(limit, 1000))
    return [dict(r) for r in conn.execute(sql, args)]


@app.get("/api/status", dependencies=[Depends(auth)])
def status():
    last_check = db.get_state(conn, "last_check")
    last_tx = conn.execute("SELECT MAX(received_at) m FROM emails WHERE kind!='otro'").fetchone()["m"]
    today = time.strftime("%Y-%m-%d")
    total_today = conn.execute(
        "SELECT COUNT(*) c FROM emails WHERE kind!='otro' AND date(received_at,'unixepoch','localtime')=?", (today,)
    ).fetchone()["c"]
    return {
        "mail_configured": bool(cfg["imap_user"]),
        "last_check": float(last_check) if last_check else None,
        "last_error": db.get_state(conn, "last_error") or None,
        "last_transaction": last_tx,
        "today_count": total_today,
        "now": time.time(),
    }


@app.post("/api/test-notification", dependencies=[Depends(auth)])
def test_notification():
    err = notifier.send(cfg, "🔔 Prueba: las notificaciones funcionan.")
    return {"ok": err is None, "error": err}
