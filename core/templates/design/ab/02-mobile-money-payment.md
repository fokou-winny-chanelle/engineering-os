# Screen 2: Pay an electricity bill with mobile money

**Product.** A bill-payment flow inside a consumer wallet app in Cameroon. Users pay their ENEO electricity
bill with Orange Money or MTN Mobile Money.

**Users.** Adults of all ages, many on low-end Android phones and prepaid data, some paying for a relative.
French first, English available. Some users read slowly; amounts and the recipient must be unmistakable.

**The flow (one screen per step, phone first).**
1. Bill: meter/contract number (with where-to-find-it help), amount due fetched (e.g. 15 000 FCFA).
2. Pay with: operator choice (Orange Money / MTN Mobile Money as text), phone number (+237, 9 digits).
3. Review: recipient ENEO, meter, amount, fee (e.g. 150 FCFA), total; confirm button.
4. Result: pending (waiting for the operator's confirmation on the phone), success with a reference to read
   out, failure with what to do.

**States to design:** invalid meter number, wrong phone format, operator timeout, offline before submit,
double-tap on confirm (must not pay twice).

**Widths:** phone 360 px (main) and 320 px (must still work); desktop 1280 px as a centred column.
Light and dark.

**Constraints.** No real logos (operator names as text). Amounts in `fr-CM` format, no decimals.
Free-licence fonts only. No external images.
