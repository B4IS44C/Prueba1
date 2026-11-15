# Monitor SINPE — versión Firebase (sin servidor propio)

- **Cloud Functions** (`checkMail`, cada minuto): lee Gmail por IMAP, analiza, guarda y envía push.
- **Firestore**: historial de correos (`emails`), estado de la revisión (`state/mail`), celulares (`devices`).
- **Cloud Messaging (FCM)**: notificaciones push a iPhone/Android.
- **Hosting**: la PWA (HTTPS incluido). **Auth**: inicio de sesión con Google; solo el dueño ve los datos.

## Puesta en marcha (una sola vez)
1. Consola Firebase → crea un proyecto y pásalo al plan **Blaze** (necesario para funciones programadas; con este uso suele quedar en la cuota gratuita).
2. Activa **Firestore** (modo producción), **Authentication → Google** y **Hosting**.
3. Configuración del proyecto → Tus apps → **Web**: copia la config en `public/firebase-config.js`.
   Configuración → Cloud Messaging → **Certificados push web** → genera la clave y pégala en `VAPID_KEY`.
4. Cambia el proyecto en `.firebaserc`.
5. En Gmail: activa verificación en 2 pasos y crea una **contraseña de aplicación** (https://myaccount.google.com/apppasswords).
6. Desde esta carpeta (`firebase/`):
   ```bash
   npm install -g firebase-tools && firebase login
   (cd functions && npm install)
   firebase functions:secrets:set IMAP_PASSWORD     # pega la contraseña de aplicación (no queda en el repo)
   ```
   Crea `functions/.env.<tu-proyecto>` con:
   ```
   IMAP_USER=tucorreo@gmail.com
   OWNER_EMAIL=tucorreo@gmail.com
   ALLOWED_SENDERS=bac,bncr,promerica
   ```
   Y despliega:
   ```bash
   firebase deploy
   ```
7. Abre `https://TU-PROYECTO.web.app`, entra con Google (la cuenta de `OWNER_EMAIL`) y activa las notificaciones.
   En iPhone: Safari → Compartir → **Añadir a pantalla de inicio**, abrir desde el ícono y activar (iOS 16.4+).

## Notas
- La primera ejecución solo toma el último correo como punto de partida: procesa lo que llegue **desde entonces**.
- Si el dueño no inicia sesión nunca, nadie puede leer los datos (las reglas lo impiden).
- Pruebas del análisis de correos: `cd functions && npm test`.
- Latencia: hasta ~1 minuto (mínimo de Cloud Scheduler).
