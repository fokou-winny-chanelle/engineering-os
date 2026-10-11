import { pgTable, real, doublePrecision, numeric, bigint } from "drizzle-orm/pg-core";

export const orders = pgTable("orders", {
  // ruleid: eos-money-float-drizzle
  amount: doublePrecision("amount").notNull(),
  // ruleid: eos-money-float-drizzle
  totalPrice: real(),
  // ok: eos-money-float-drizzle
  price: numeric({ precision: 12, scale: 2 }).notNull(),
  // ok: eos-money-float-drizzle
  amountMinor: bigint({ mode: "bigint" }).notNull(),
  // ok: eos-money-float-drizzle
  latitude: doublePrecision(),
  // ok: eos-money-float-drizzle
  taxRate: real(),
  // ruleid: eos-money-float-drizzle
  generatedAmount: real(),
});

export function parse(body: { amount: string; ratio: string }) {
  // ruleid: eos-money-float-js
  const amount = parseFloat(body.amount);
  // ok: eos-money-float-js
  const ratio = parseFloat(body.ratio);
  return { amount, ratio };
}
