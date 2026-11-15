"use strict";
// Detecta SINPE Móvil / transferencias y extrae nombre, referencia y monto.
// Port de app/parser.py. Si un banco no se lee bien, agregue su ejemplo a test/parser.test.js.

const SIMPE_RE = /\bsi[nm]pe\b/i; // "simpe" es el error de dedo común de "sinpe"
const TRANSFER_RE = /transferencia|transfer\b|dep[oó]sito/i;

const AMOUNT_RE =
  /(?<cur>₡|¢|CRC|USD|US\$|\$|colones)\s*(?<num>\d[\d.,\s]*\d|\d)|(?<num2>\d[\d.,]*\d)\s*(?<cur2>colones|CRC|USD|d[oó]lares)/gi;

const REF_RE =
  /(?:n[uú]mero\s+de\s+(?:referencia|transacci[oó]n|comprobante|movimiento|operaci[oó]n|documento)|referencia|comprobante|transacci[oó]n|operaci[oó]n|movimiento|documento|\bid\b|\bno\.|\bn[°º])\s*[:#-]?\s*([A-Z0-9][A-Z0-9-]{4,})/gi;

const NAME_PREFIX_RE =
  /(?:enviad[oa]\s+por|realizad[oa]\s+por|remitente|ordenante|origen|desde|de\s+parte\s+de|a\s+favor\s+de|cliente\s+origen|nombre\s+del\s+(?:remitente|ordenante|emisor)|emisor)\s*[:-]?\s*/gi;
const NAME_AFTER_RE =
  /^([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+){0,4})/;
const NAME_UPPER_RE = /\bde\s+([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,4})/g; // "de JUAN PEREZ ROJAS"
const NAME_STOP = new Set(["su", "la", "el", "cuenta", "banco", "sinpe", "simpe", "movil", "móvil", "fecha", "monto"]);

const RECEIVED_RE = /recibi|acredit|a su favor|le (?:ha )?(?:envi|transfiri)|dep[oó]sito|ingres/i;
const SENT_RE =
  /debit|usted (?:ha )?(?:envi|realiz|transfiri)|realiz[oó]\s+(?:una\s+)?(?:transferencia|sinpe)|su transferencia|enviaste|envi[oó]\s+a\b/i;

function htmlToText(s) {
  return String(s || "")
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, " ")
    .replace(/<br\s*\/?>|<\/p>|<\/div>|<\/tr>|<\/li>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/[ \t ]+/g, " ")
    .replace(/\n\s*\n+/g, "\n")
    .trim();
}

// '5,000.00' -> 5000 ; '5.000,00' -> 5000 ; '5 000' -> 5000
function parseAmount(raw) {
  raw = raw.trim().replace(/\s/g, "");
  const sep = Math.max(raw.lastIndexOf("."), raw.lastIndexOf(","));
  if (sep !== -1 && [1, 2].includes(raw.length - sep - 1)) {
    return parseFloat(`${raw.slice(0, sep).replace(/[.,]/g, "")}.${raw.slice(sep + 1)}`);
  }
  return parseFloat(raw.replace(/[.,]/g, ""));
}

function currencyOf(tok) {
  const t = tok.toLowerCase();
  return t === "$" || t === "us$" || t === "usd" || t.startsWith("d") ? "USD" : "CRC";
}

function extractAmount(text) {
  for (const m of text.matchAll(AMOUNT_RE)) {
    const num = m.groups.num || m.groups.num2;
    const cur = m.groups.cur || m.groups.cur2;
    const val = parseAmount(num);
    if (Number.isFinite(val) && val > 0) return [val, currencyOf(cur)];
  }
  return [null, null];
}

function titleCase(s) {
  return s.toLowerCase().split(/\s+/).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

function cleanName(name) {
  const words = name.trim().replace(/^\.+|\.+$/g, "").split(/\s+/)
    .filter((w) => !NAME_STOP.has(w.toLowerCase().replace(/\./g, "")));
  const joined = words.join(" ");
  return joined.length >= 3 ? titleCase(joined) : null;
}

function extractPerson(text) {
  for (const m of text.matchAll(NAME_PREFIX_RE)) {
    const rest = text.slice(m.index + m[0].length);
    const mm = NAME_AFTER_RE.exec(rest);
    const name = mm && cleanName(mm[1]);
    if (name) return name;
  }
  for (const m of text.matchAll(NAME_UPPER_RE)) {
    const name = cleanName(m[1]);
    if (name) return name;
  }
  return null;
}

function extractReference(text) {
  for (const m of text.matchAll(REF_RE)) {
    if (/\d/.test(m[1])) return m[1];
  }
  return null;
}

function classify(subject, body) {
  const text = `${subject}\n${body}`;
  if (SIMPE_RE.test(text)) return "simpe";
  if (TRANSFER_RE.test(text)) return "transferencia";
  return "otro";
}

function parseEmail(subject, body) {
  subject = (subject || "").normalize("NFC");
  body = (body || "").normalize("NFC");
  const kind = classify(subject, body);
  if (kind === "otro") {
    return { kind, direction: "desconocido", person: null, reference: null, amount: null, currency: null };
  }
  const full = `${subject}\n${body}`;
  const [amount, currency] = extractAmount(full);
  let direction = "desconocido";
  if (SENT_RE.test(full) && !RECEIVED_RE.test(full)) direction = "enviado";
  else if (RECEIVED_RE.test(full)) direction = "recibido";
  return { kind, direction, person: extractPerson(full), reference: extractReference(full), amount, currency };
}

module.exports = { parseEmail, parseAmount, htmlToText };
