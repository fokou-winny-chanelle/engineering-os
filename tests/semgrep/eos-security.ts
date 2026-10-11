// Fixtures for core/scaffold/security/semgrep.yml (semgrep --test). Not executed.
import crypto from "node:crypto";
import cors from "cors";
import express from "express";
import jwt from "jsonwebtoken";

const app = express();

// ruleid: eos-js-jwt-verify-disabled
jwt.verify(token, key, { algorithms: ["HS256", "none"] });
// ruleid: eos-js-jwt-verify-disabled
const claims = jwt.decode(token);
// ok: eos-js-jwt-verify-disabled
jwt.verify(token, key, { algorithms: ["RS256"], audience: "api", issuer: "https://issuer" });

function check(signature: string, expected: string) {
  // ruleid: eos-js-non-constant-time-compare
  if (signature === expected) return true;
  // ok: eos-js-non-constant-time-compare
  if (signature === "") return false;
  // ok: eos-js-non-constant-time-compare
  return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected));
}

// ruleid: eos-js-webhook-without-signature-check
app.post("/webhooks/payments", async (req, res) => {
  await credit(req.body.amount);
  res.sendStatus(200);
});

// ok: eos-js-webhook-without-signature-check
app.post("/webhooks/stripe", express.raw({ type: "application/json" }), (req, res) => {
  const event = stripe.webhooks.constructEvent(req.body, req.headers["stripe-signature"], secret);
  res.json({ received: event.id });
});

// ok: eos-js-webhook-without-signature-check
app.post("/api/orders", (req, res) => res.sendStatus(201));

// ruleid: eos-js-math-random-secret
const resetToken = Math.random().toString(36).slice(2);
// ok: eos-js-math-random-secret
const jitter = Math.random() * 100;
// ok: eos-js-math-random-secret
const sessionId = crypto.randomBytes(32).toString("hex");

async function find(db: any, email: string) {
  // ruleid: eos-js-sql-template-literal
  await db.query(`SELECT * FROM users WHERE email = '${email}'`);
  // ok: eos-js-sql-template-literal
  await db.query("SELECT * FROM users WHERE email = $1", [email]);
}

// ruleid: eos-cors-wildcard-credentials
app.use(cors({ origin: true, credentials: true }));
// ok: eos-cors-wildcard-credentials
app.use(cors({ origin: ["https://app.example.com"], credentials: true }));

// ruleid: eos-tls-verify-disabled
const agent = new https.Agent({ rejectUnauthorized: false });
// ok: eos-tls-verify-disabled
const agent2 = new https.Agent({ keepAlive: true });
