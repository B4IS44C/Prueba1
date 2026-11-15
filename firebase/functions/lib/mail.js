"use strict";
const crypto = require("crypto");
const { ImapFlow } = require("imapflow");
const { simpleParser } = require("mailparser");
const { parseEmail, htmlToText } = require("./parser");

// Lee los correos nuevos (UID > lastUid) en modo solo lectura. No marca nada como leído.
async function fetchNew({ host, user, pass, folder }, lastUid) {
  const client = new ImapFlow({ host, port: 993, secure: true, auth: { user, pass }, logger: false });
  await client.connect();
  const lock = await client.getMailboxLock(folder, { readOnly: true });
  try {
    const uidValidity = String(client.mailbox.uidValidity);
    const newest = client.mailbox.uidNext - 1;
    // Primera vez (o buzón reconstruido): empezar desde ahora, sin procesar el historial.
    if (lastUid == null) return { uidValidity, newest, messages: [], reset: true };
    const messages = [];
    if (newest > lastUid) {
      for await (const m of client.fetch(`${lastUid + 1}:*`, { uid: true, source: true }, { uid: true })) {
        if (m.uid > lastUid) messages.push({ uid: m.uid, source: m.source });
      }
    }
    messages.sort((a, b) => a.uid - b.uid);
    return { uidValidity, newest, messages, reset: false };
  } finally {
    lock.release();
    await client.logout().catch(() => {});
  }
}

async function toRecord(uid, source, allowedSenders) {
  const p = await simpleParser(source);
  const sender = p.from?.text || "";
  if (allowedSenders.length && !allowedSenders.some((s) => sender.toLowerCase().includes(s))) return null;
  const subject = p.subject || "";
  const body = p.text || htmlToText(p.html || "");
  const messageId = p.messageId || `uid-${uid}`;
  return {
    id: crypto.createHash("sha1").update(messageId).digest("hex"),
    data: { messageId, sender, subject, sentAt: p.date ? p.date.toISOString() : null, ...parseEmail(subject, body) },
  };
}

module.exports = { fetchNew, toRecord };
