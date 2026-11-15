"use strict";

const money = (a, c) => (a == null ? "monto no detectado" : `${c === "USD" ? "$" : "₡"}${a.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

function buildPush(r) {
  const kind = r.kind === "simpe" ? "SINPE Móvil" : "Transferencia";
  const verbo = r.direction === "recibido" ? "recibió" : r.direction === "enviado" ? "envió" : "registró";
  return {
    title: `${kind} · ${money(r.amount, r.currency)}`,
    body: `✅ Se ${verbo} un ${kind}\n👤 De: ${r.person || "nombre no detectado"}\n🔖 ID: ${r.reference || "no detectado"}`,
  };
}

const DEAD = new Set(["messaging/registration-token-not-registered", "messaging/invalid-registration-token"]);

// Envía a todos los dispositivos del dueño. Devuelve null si todo bien o un texto de error.
async function pushAll(db, messaging, { title, body }) {
  const snap = await db.collection("devices").get();
  const tokens = snap.docs.map((d) => d.id);
  if (!tokens.length) return "ningún dispositivo con notificaciones activadas";
  const link = `https://${process.env.GCLOUD_PROJECT}.web.app/`;
  const res = await messaging.sendEachForMulticast({
    tokens,
    notification: { title, body },
    webpush: {
      headers: { Urgency: "high", TTL: "86400" },
      notification: { icon: "/icon-192.png", badge: "/icon-192.png" },
      fcmOptions: { link },
    },
    apns: { headers: { "apns-priority": "10" }, payload: { aps: { sound: "default" } } },
  });
  const errors = [];
  await Promise.all(res.responses.map(async (r, i) => {
    if (r.success) return;
    if (DEAD.has(r.error?.code)) await db.collection("devices").doc(tokens[i]).delete();
    else errors.push(r.error?.code || "error");
  }));
  if (res.successCount === 0 && !errors.length) return "ningún dispositivo vigente";
  return errors.length ? errors.join(", ") : null;
}

module.exports = { buildPush, pushAll };
