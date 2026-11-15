import sqlite3

from app import db, mailwatch, notifier
from app.parser import parse_amount, parse_email


def test_amount_formats():
    assert parse_amount("5,000.00") == 5000.0
    assert parse_amount("5.000,00") == 5000.0
    assert parse_amount("12 500") == 12500.0
    assert parse_amount("1,250,000") == 1250000.0


def test_simpe_recibido():
    r = parse_email(
        "Notificación SINPE Móvil",
        "Se le acreditó un SINPE Móvil por ₡15,000.00 enviado por JUAN PEREZ ROJAS. Número de referencia: 2024112345678",
    )
    assert r["kind"] == "simpe" and r["direction"] == "recibido"
    assert r["amount"] == 15000.0 and r["currency"] == "CRC"
    assert r["person"] == "Juan Perez Rojas"
    assert r["reference"] == "2024112345678"


def test_simpe_typo_simpe():
    assert parse_email("Simpe recibido", "Monto: ₡2.500,00")["kind"] == "simpe"


def test_transferencia_usd():
    r = parse_email("Transferencia recibida", "Ha recibido una transferencia de $ 120.50 de MARIA LOPEZ. Comprobante: AB-99812")
    assert r["kind"] == "transferencia" and r["currency"] == "USD" and r["amount"] == 120.5
    assert r["person"] == "Maria Lopez" and r["reference"] == "AB-99812"


def test_irrelevante():
    assert parse_email("Su estado de cuenta", "Adjunto su estado de cuenta mensual.")["kind"] == "otro"


def test_pipeline_dedupe_and_notify(monkeypatch):
    sent = []
    monkeypatch.setattr(notifier, "send", lambda cfg, text: sent.append(text))
    conn = db.connect(":memory:")
    cfg = {"allowed_senders": ["banco"]}
    raw = (b"From: Banco <avisos@banco.cr>\nSubject: SINPE Movil\nMessage-ID: <a1>\n"
           b"Content-Type: text/plain; charset=utf-8\n\nSe acredito un SINPE de \xe2\x82\xa17,500 enviado por ANA SOTO. Referencia: 555123\n")
    assert mailwatch.process_message(conn, cfg, raw, "x")["amount"] == 7500.0
    assert mailwatch.process_message(conn, cfg, raw, "x") is None  # duplicado
    assert len(sent) == 1 and "Ana Soto" in sent[0] and "555123" in sent[0] and "7,500.00" in sent[0]
    other = raw.replace(b"Banco <avisos@banco.cr>", b"Otro <spam@x.com>").replace(b"<a1>", b"<a2>")
    assert mailwatch.process_message(conn, cfg, other, "y") is None  # remitente no permitido
