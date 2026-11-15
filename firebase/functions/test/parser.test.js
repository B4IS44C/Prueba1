const test = require("node:test");
const assert = require("node:assert");
const { parseEmail, parseAmount } = require("../lib/parser");

test("formatos de monto", () => {
  assert.strictEqual(parseAmount("5,000.00"), 5000);
  assert.strictEqual(parseAmount("5.000,00"), 5000);
  assert.strictEqual(parseAmount("12 500"), 12500);
  assert.strictEqual(parseAmount("1,250,000"), 1250000);
});

test("SINPE recibido", () => {
  const r = parseEmail(
    "Notificación SINPE Móvil",
    "Se le acreditó un SINPE Móvil por ₡15,000.00 enviado por JUAN PEREZ ROJAS. Número de referencia: 2024112345678"
  );
  assert.strictEqual(r.kind, "simpe");
  assert.strictEqual(r.direction, "recibido");
  assert.strictEqual(r.amount, 15000);
  assert.strictEqual(r.currency, "CRC");
  assert.strictEqual(r.person, "Juan Perez Rojas");
  assert.strictEqual(r.reference, "2024112345678");
});

test("typo 'simpe'", () => {
  assert.strictEqual(parseEmail("Simpe recibido", "Monto: ₡2.500,00").kind, "simpe");
});

test("transferencia en dólares", () => {
  const r = parseEmail("Transferencia recibida", "Ha recibido una transferencia de $ 120.50 de MARIA LOPEZ. Comprobante: AB-99812");
  assert.strictEqual(r.kind, "transferencia");
  assert.strictEqual(r.currency, "USD");
  assert.strictEqual(r.amount, 120.5);
  assert.strictEqual(r.person, "Maria Lopez");
  assert.strictEqual(r.reference, "AB-99812");
});

test("correo irrelevante", () => {
  assert.strictEqual(parseEmail("Su estado de cuenta", "Adjunto su estado de cuenta mensual.").kind, "otro");
});
