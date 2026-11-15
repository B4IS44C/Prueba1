"""Detecta si un correo es un SINPE Móvil o una transferencia y extrae nombre, referencia y monto.

Los bancos redactan distinto, así que se usan heurísticas tolerantes. Si un banco
no se reconoce bien, agregue su texto de ejemplo a tests/test_parser.py y ajuste
los patrones de aquí.
"""
import html
import re
import unicodedata

# "simpe" es el error de dedo común de "sinpe": se aceptan ambos.
SIMPE_RE = re.compile(r"\bsi?n?mpe\b|\bsinpe\b|\bsimpe\b", re.I)
TRANSFER_RE = re.compile(r"transferencia|transfer\b|deposito|dep[oó]sito", re.I)

AMOUNT_RE = re.compile(
    r"(?P<cur>₡|¢|CRC|USD|US\$|\$|colones)\s*(?P<num>\d[\d.,\s]*\d|\d)"
    r"|(?P<num2>\d[\d.,]*\d)\s*(?P<cur2>colones|CRC|USD|d[oó]lares)",
    re.I,
)

REF_RE = re.compile(
    r"(?:n[uú]mero\s+de\s+(?:referencia|transacci[oó]n|comprobante|movimiento|operaci[oó]n|documento)"
    r"|referencia|comprobante|transacci[oó]n|operaci[oó]n|movimiento|documento|\bid\b|\bno\.|\bn[°º])"
    r"\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-]{4,})",
    re.I,
)

NAME_RES = [
    re.compile(
        r"(?:enviad[oa]\s+por|realizad[oa]\s+por|remitente|ordenante|origen|desde|de\s+parte\s+de|a\s+favor\s+de|"
        r"cliente\s+origen|nombre\s+del\s+(?:remitente|ordenante|emisor)|emisor)"
        r"\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+){0,4})",
    ),
    re.compile(r"\bde\s+([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,4})"),  # "de JUAN PEREZ ROJAS"
]
NAME_STOP = {"su", "la", "el", "cuenta", "banco", "sinpe", "simpe", "movil", "móvil", "fecha", "monto"}

RECEIVED_RE = re.compile(r"recibi|acredit|a su favor|le (?:ha )?(?:envi|transfiri)|dep[oó]sito|ingres", re.I)
SENT_RE = re.compile(r"debit|usted (?:ha )?(?:envi|realiz|transfiri)|realiz[oó]\s+(?:una\s+)?(?:transferencia|sinpe)|su transferencia|enviaste|envi[oó]\s+a\b", re.I)


def html_to_text(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def parse_amount(raw):
    """'5,000.00' -> 5000.0 ; '5.000,00' -> 5000.0 ; '5 000' -> 5000.0"""
    raw = raw.strip().replace(" ", "")
    last_dot, last_comma = raw.rfind("."), raw.rfind(",")
    sep = max(last_dot, last_comma)
    if sep != -1 and len(raw) - sep - 1 in (1, 2):
        dec = raw[sep + 1:]
        whole = re.sub(r"[.,]", "", raw[:sep])
        return float(f"{whole}.{dec}")
    return float(re.sub(r"[.,]", "", raw))


def _currency(tok):
    t = tok.lower()
    return "USD" if t in ("$", "us$", "usd") or t.startswith("d") else "CRC"


def extract_amount(text):
    for m in AMOUNT_RE.finditer(text):
        num = m.group("num") or m.group("num2")
        cur = m.group("cur") or m.group("cur2")
        try:
            val = parse_amount(num)
        except ValueError:
            continue
        if val > 0:
            return val, _currency(cur)
    return None, None


def extract_person(text):
    for rx in NAME_RES:
        for m in rx.finditer(text):
            name = m.group(1).strip(" .")
            words = [w for w in name.split() if w.lower().strip(".") not in NAME_STOP]
            if words and len(" ".join(words)) >= 3:
                return " ".join(words).title()
    return None


def extract_reference(text):
    for m in REF_RE.finditer(text):
        ref = m.group(1)
        if any(c.isdigit() for c in ref):
            return ref
    return None


def _norm(s):
    return unicodedata.normalize("NFC", s)


def classify(subject, body):
    text = f"{subject}\n{body}"
    if SIMPE_RE.search(text):
        return "simpe"
    if TRANSFER_RE.search(text):
        return "transferencia"
    return "otro"


def parse_email(subject, body_text):
    subject, body_text = _norm(subject or ""), _norm(body_text or "")
    kind = classify(subject, body_text)
    if kind == "otro":
        return {"kind": "otro", "direction": "desconocido", "person": None, "reference": None, "amount": None, "currency": None}
    full = f"{subject}\n{body_text}"
    amount, currency = extract_amount(full)
    direction = "desconocido"
    if SENT_RE.search(full) and not RECEIVED_RE.search(full):
        direction = "enviado"
    elif RECEIVED_RE.search(full):
        direction = "recibido"
    return {
        "kind": kind,
        "direction": direction,
        "person": extract_person(full),
        "reference": extract_reference(full),
        "amount": amount,
        "currency": currency,
    }
