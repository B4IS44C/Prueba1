import json
import urllib.parse
import urllib.request


def format_money(amount, currency):
    if amount is None:
        return "monto no detectado"
    sym = "$" if currency == "USD" else "₡"
    return f"{sym}{amount:,.2f}"


def build_message(row):
    kind = "SINPE Móvil" if row["kind"] == "simpe" else "Transferencia"
    verbo = {"recibido": "recibió", "enviado": "envió"}.get(row.get("direction"), "registró")
    lines = [
        f"✅ Se {verbo} un {kind}",
        f"👤 De: {row.get('person') or 'nombre no detectado'}",
        f"🔖 ID: {row.get('reference') or 'no detectado'}",
        f"💰 Monto: {format_money(row.get('amount'), row.get('currency'))}",
    ]
    return "\n".join(lines)


def _post(url, data, headers):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        r.read()


def send(cfg, text):
    """Envía por todos los canales configurados. Devuelve None si todo bien o un texto de error."""
    errors, used = [], 0
    if cfg["telegram_token"] and cfg["telegram_chat"]:
        used += 1
        try:
            body = urllib.parse.urlencode({"chat_id": cfg["telegram_chat"], "text": text}).encode()
            _post(f"https://api.telegram.org/bot{cfg['telegram_token']}/sendMessage", body, {})
        except Exception as e:
            errors.append(f"telegram: {e}")
    if cfg["ntfy_topic"]:
        used += 1
        try:
            _post(f"{cfg['ntfy_server']}/{cfg['ntfy_topic']}", text.encode("utf-8"),
                  {"Title": "Pago recibido", "Priority": "high", "Tags": "moneybag"})
        except Exception as e:
            errors.append(f"ntfy: {e}")
    if used == 0:
        return "ningún canal de notificación configurado"
    return "; ".join(errors) or None
