import pino from "pino";

const logger = pino();

export async function handler(req: Request, user: { id: string; email: string; apiKey: string; password: string }, tokenCount: number) {
  // ruleid: eos-js-log-secret
  console.log("login", user.password);
  // ruleid: eos-js-log-secret
  logger.info(`key ${user.apiKey}`);
  // ruleid: eos-js-log-secret
  logger.info({ auth: req.headers.get("authorization"), token: user.password }, "auth");
  // ok: eos-js-log-secret
  logger.info({ tokenCount }, "tokens used");
  // ruleid: eos-js-log-personal-data
  console.error("cannot email", user.email);
  // ok: eos-js-log-personal-data
  logger.info({ userId: user.id }, "emailed");
  // ruleid: eos-js-log-request-body
  console.log("body", await req.json());
  // ok: eos-js-log-request-body
  console.log("status", req.method);
}
