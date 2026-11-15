"use strict";
const { onSchedule } = require("firebase-functions/v2/scheduler");
const { onCall, HttpsError } = require("firebase-functions/v2/https");
const { setGlobalOptions } = require("firebase-functions/v2");
const { defineString, defineSecret } = require("firebase-functions/params");
const { initializeApp } = require("firebase-admin/app");
const { getFirestore, FieldValue, Timestamp } = require("firebase-admin/firestore");
const { getMessaging } = require("firebase-admin/messaging");
const { fetchNew, toRecord } = require("./lib/mail");
const { buildPush, pushAll } = require("./lib/notify");

setGlobalOptions({ region: "us-central1", maxInstances: 3 });
initializeApp();
const db = getFirestore();

const IMAP_HOST = defineString("IMAP_HOST", { default: "imap.gmail.com" });
const IMAP_USER = defineString("IMAP_USER");
const IMAP_FOLDER = defineString("IMAP_FOLDER", { default: "INBOX" });
const ALLOWED_SENDERS = defineString("ALLOWED_SENDERS", { default: "" });
const OWNER_EMAIL = defineString("OWNER_EMAIL");
const IMAP_PASSWORD = defineSecret("IMAP_PASSWORD");

const stateRef = db.doc("state/mail");

// Revisa el correo cada minuto.
exports.checkMail = onSchedule(
  { schedule: "every 1 minutes", secrets: [IMAP_PASSWORD], timeoutSeconds: 120, memory: "512MiB" },
  async () => {
    const allowed = ALLOWED_SENDERS.value().split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
    const st = (await stateRef.get()).data() || {};
    try {
      const out = await fetchNew(
        { host: IMAP_HOST.value(), user: IMAP_USER.value(), pass: IMAP_PASSWORD.value(), folder: IMAP_FOLDER.value() },
        st.uidValidity ? st.lastUid : null
      );
      // Primera ejecución o buzón reconstruido (UIDVALIDITY cambió): empezar desde ahora.
      const restart = out.reset || st.uidValidity !== out.uidValidity;
      let lastUid = restart ? out.newest : st.lastUid;
      if (restart) out.messages = [];
      try {
        for (const m of out.messages) {
          const rec = await toRecord(m.uid, m.source, allowed);
          if (rec) {
            const ref = db.collection("emails").doc(rec.id);
            try {
              await ref.create({ ...rec.data, receivedAt: Timestamp.now(), notified: false, notifyError: null });
              if (rec.data.kind !== "otro") {
                const err = await pushAll(db, getMessaging(), buildPush(rec.data));
                await ref.update({ notified: !err, notifyError: err });
              }
            } catch (e) {
              if (e.code !== 6) throw e; // 6 = ALREADY_EXISTS: correo ya registrado
            }
          }
          lastUid = m.uid;
        }
      } finally {
        await stateRef.set({ lastUid, uidValidity: out.uidValidity }, { merge: true });
      }
      await stateRef.set({ lastCheck: FieldValue.serverTimestamp(), lastError: null }, { merge: true });
    } catch (e) {
      await stateRef.set({ lastError: `${e.name || "Error"}: ${e.message}`.slice(0, 300) }, { merge: true });
      throw e;
    }
  }
);

// El primer inicio de sesión con el correo OWNER_EMAIL se convierte en el dueño de los datos.
exports.claimOwner = onCall(async (req) => {
  const t = req.auth?.token;
  if (!t) throw new HttpsError("unauthenticated", "Inicie sesión");
  if (!t.email_verified || t.email.toLowerCase() !== OWNER_EMAIL.value().trim().toLowerCase()) {
    throw new HttpsError("permission-denied", "Esta cuenta no es la del dueño");
  }
  await db.doc("config/owner").set({ uid: req.auth.uid, email: t.email });
  return { ok: true };
});

exports.sendTest = onCall(async (req) => {
  const owner = (await db.doc("config/owner").get()).data();
  if (!req.auth || !owner || owner.uid !== req.auth.uid) throw new HttpsError("permission-denied", "No autorizado");
  const err = await pushAll(db, getMessaging(), { title: "Prueba", body: "🔔 Las notificaciones funcionan." });
  return { ok: !err, error: err };
});
