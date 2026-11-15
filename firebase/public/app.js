import { initializeApp } from "https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signInWithRedirect, onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js";
import { getFirestore, collection, query, orderBy, limit, onSnapshot, doc, setDoc, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.14.1/firebase-firestore.js";
import { getFunctions, httpsCallable } from "https://www.gstatic.com/firebasejs/10.14.1/firebase-functions.js";
import { getMessaging, getToken, onMessage, isSupported } from "https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging.js";
import "/firebase-config.js";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const app = initializeApp(self.FIREBASE_CONFIG);
const auth = getAuth(app), db = getFirestore(app), fns = getFunctions(app, "us-central1");

let rows = [], state = null;
const secs = (ts) => (ts ? Date.now() / 1000 - ts.seconds : null);
const ago = (ts) => {
  const s = secs(ts); if (s == null) return "nunca";
  return s < 60 ? `hace ${Math.max(0, Math.round(s))}s` : s < 3600 ? `hace ${Math.round(s / 60)} min` : s < 86400 ? `hace ${Math.round(s / 3600)} h` : new Date(ts.seconds * 1000).toLocaleString();
};
const money = (a, c) => (a == null ? "—" : (c === "USD" ? "$" : "₡") + a.toLocaleString("es-CR", { minimumFractionDigits: 2 }));

function renderStatus() {
  const lastTx = rows.find((r) => r.kind !== "otro");
  const today = new Date().toDateString();
  const n = rows.filter((r) => r.kind !== "otro" && r.receivedAt && r.receivedAt.toDate().toDateString() === today).length;
  const stale = !state || secs(state.lastCheck) == null || secs(state.lastCheck) > 240;
  const bad = state?.lastError || stale;
  const msg = state?.lastError ? "Error de correo: " + esc(state.lastError)
    : stale ? "El servidor no ha revisado el correo en los últimos minutos"
    : "Revisando el correo (" + ago(state.lastCheck) + ")";
  $("status").innerHTML = `<span><span class="dot ${bad ? "bad" : "ok"}"></span>${msg}</span>
    <span>Último pago: <b>${ago(lastTx?.receivedAt)}</b></span><span>Hoy: <b>${n}</b></span>`;
}

function renderList() {
  const k = $("kind").value, q = $("q").value.toLowerCase();
  const list = rows.filter((r) => (k === "all" ? true : k ? r.kind === k : r.kind !== "otro") &&
    (!q || [r.person, r.reference, r.subject].some((v) => (v || "").toLowerCase().includes(q))));
  $("list").innerHTML = list.length ? list.map((r) => `<div class="tx"><div>
    <b>${esc(r.person || "Nombre no detectado")}</b> <span class="tag">${r.kind === "simpe" ? "SINPE" : r.kind === "transferencia" ? "Transferencia" : "Otro"}</span> <span class="tag">${esc(r.direction)}</span><br>
    <span class="mut">ID: ${esc(r.reference || "—")} · ${esc(r.sentAt ? new Date(r.sentAt).toLocaleString() : "")}</span><br>
    <span class="mut">${r.kind === "otro" ? esc(r.subject) : r.notified ? "🔔 Notificado" : "⚠️ No notificado: " + esc(r.notifyError || "pendiente")}</span></div>
    <div class="amt">${money(r.amount, r.currency)}</div></div>`).join("") : "<span class='mut'>Aún no hay registros.</span>";
}

async function setupPush() {
  const box = $("pushbox");
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  if (/iphone|ipad|ipod/i.test(navigator.userAgent) && !standalone) {
    box.innerHTML = "📲 <b>Para recibir notificaciones en iPhone:</b> toca <b>Compartir</b> → <b>Añadir a pantalla de inicio</b>, abre la app desde el ícono y actívalas aquí.";
    return;
  }
  if (!(await isSupported())) { box.textContent = "Este navegador no soporta notificaciones push."; return; }
  if (Notification.permission === "denied") { box.textContent = "Las notificaciones están bloqueadas. Actívalas en los Ajustes del dispositivo."; return; }
  const messaging = getMessaging(app);
  const reg = await navigator.serviceWorker.register("/firebase-messaging-sw.js");
  const register = async () => {
    const token = await getToken(messaging, { vapidKey: self.VAPID_KEY, serviceWorkerRegistration: reg });
    await setDoc(doc(db, "devices", token), { createdAt: serverTimestamp(), ua: navigator.userAgent.slice(0, 120) });
    box.textContent = "🔔 Notificaciones activadas en este dispositivo.";
  };
  onMessage(messaging, (m) => reg.showNotification(m.notification?.title || "Monitor SINPE", { body: m.notification?.body, icon: "/icon-192.png" }));
  if (Notification.permission === "granted") return register();
  box.innerHTML = '<button class="primary" id="en">🔔 Activar notificaciones</button>';
  $("en").onclick = async () => {
    if ((await Notification.requestPermission()) !== "granted") return setupPush();
    await register();
  };
}

let unsubs = [];
onAuthStateChanged(auth, async (user) => {
  unsubs.forEach((u) => u()); unsubs = [];
  $("login").hidden = !!user; $("app").hidden = !user;
  if (!user) return;
  try { await httpsCallable(fns, "claimOwner")(); }
  catch (e) { $("app").hidden = true; $("login").hidden = false; $("loginerr").textContent = "Esta cuenta no es la del dueño."; return signOut(auth); }
  unsubs.push(onSnapshot(query(collection(db, "emails"), orderBy("receivedAt", "desc"), limit(300)), (s) => {
    rows = s.docs.map((d) => d.data()); renderStatus(); renderList();
  }));
  unsubs.push(onSnapshot(doc(db, "state", "mail"), (s) => { state = s.data(); renderStatus(); }));
  setupPush().catch((e) => { $("pushbox").textContent = "Error al activar notificaciones: " + e.message; });
});

$("signin").onclick = async () => {
  const p = new GoogleAuthProvider();
  try { await signInWithPopup(auth, p); } catch { await signInWithRedirect(auth, p); }
};
$("out").onclick = () => signOut(auth);
$("q").oninput = renderList; $("kind").onchange = renderList;
$("test").onclick = async () => {
  const r = (await httpsCallable(fns, "sendTest")()).data;
  alert(r.ok ? "Enviada" : "Error: " + r.error);
};
setInterval(renderStatus, 15000);
