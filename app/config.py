import os


def _load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()


def env(name, default=""):
    return os.environ.get(name, default)


def settings():
    return {
        "imap_host": env("IMAP_HOST", "imap.gmail.com"),
        "imap_user": env("IMAP_USER"),
        "imap_password": env("IMAP_PASSWORD"),
        "imap_folder": env("IMAP_FOLDER", "INBOX"),
        "poll_seconds": int(env("POLL_SECONDS", "30")),
        "allowed_senders": [s.strip().lower() for s in env("ALLOWED_SENDERS").split(",") if s.strip()],
        "initial_days": int(env("INITIAL_DAYS", "0")),
        "app_password": env("APP_PASSWORD"),
        "telegram_token": env("TELEGRAM_BOT_TOKEN"),
        "telegram_chat": env("TELEGRAM_CHAT_ID"),
        "ntfy_topic": env("NTFY_TOPIC"),
        "ntfy_server": env("NTFY_SERVER", "https://ntfy.sh").rstrip("/"),
        "silence_hours": float(env("SILENCE_ALERT_HOURS", "0")),
        "db_path": env("DB_PATH", "data.db"),
        "vapid_key_file": env("VAPID_KEY_FILE", "vapid_private.pem"),
        "vapid_subject": env("VAPID_SUBJECT", "mailto:admin@example.com"),
    }
