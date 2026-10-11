# Screen 1: SME cash dashboard ("Kolo Pro")

**Product.** Kolo Pro helps small shop owners in Douala and Yaoundé see their money: cash sales they record,
mobile-money payments received, and money owed to them. Owners are busy, often on a mid-range Android phone,
sometimes on a shared laptop at the end of the day.

**Users.** Shop owners and one or two staff. French first, English second (switchable). Mixed reading comfort:
many read slowly in French; numbers matter more than words.

**The screen.** The home dashboard after login.
- Today's balance in FCFA (e.g. 1 245 500 FCFA), with in/out for today.
- Money in vs money out for the last 7 days (a chart people can read without a legend hunt).
- Pending mobile-money settlements (Orange Money, MTN Mobile Money) with expected time.
- Recent transactions (6 rows: date, label, amount, method, status).
- Main action: record a sale ("Enregistrer une vente"); secondary: withdraw ("Retirer").

**States to design:** first use (no data yet), loading, sync failed (offline, last updated 2 h ago),
a long French label, and a large amount (12 450 000 FCFA).

**Widths:** phone 360 px and desktop 1280 px. Light and dark.

**Constraints.** No invented brand assets or real logos (use operator names as text). Amounts use
`fr-CM` formatting (narrow no-break space thousands separator, no decimals). Fonts must be free to use
(say which licence). No external images.
