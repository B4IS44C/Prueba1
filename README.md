# Monitor SINPE Móvil / Transferencias

Revisa un buzón de correo (IMAP). Cuando llega un aviso de **SINPE Móvil** o **transferencia**, extrae
nombre, ID/referencia y monto, **notifica al dueño** (Telegram y/o ntfy) y lo guarda en un historial
consultable en la web, donde también se ve si el correo está siendo revisado y cuándo llegó el último pago.

## Uso
```bash
pip install -r requirements.txt
cp .env.example .env     # completar IMAP, APP_PASSWORD y un canal de notificación
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Abrir `http://localhost:8000` (usuario `admin`, contraseña `APP_PASSWORD`).

- **Gmail**: activar IMAP y usar una *contraseña de aplicación*.
- **Telegram**: crear bot con @BotFather, poner `TELEGRAM_BOT_TOKEN` y tu `TELEGRAM_CHAT_ID`.
- **ntfy** (push al celular sin cuenta): instalar la app ntfy y suscribirse a un `NTFY_TOPIC` difícil de adivinar.
- Botón "Probar notificación" en la web; `SILENCE_ALERT_HOURS` avisa si dejan de llegar pagos.
- Para producción, ponerlo detrás de HTTPS (la autenticación básica no cifra por sí sola).

## Ajustar al formato de tu banco
El análisis (`app/parser.py`) usa heurísticas. Si un banco no se lee bien, añade el texto de ejemplo
(sin datos reales sensibles) a `tests/test_parser.py` y ajusta los patrones. `pytest` para probar.
