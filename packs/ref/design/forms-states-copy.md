---
id: design/forms-states-copy
title: Forms UX, empty/loading/error/offline states and microcopy (labels, validation, error messages, skeletons vs spinners, empty states, bilingual French/English tone)
area: design
read_when: designing or reviewing a form, validation or error messages, loading indicators or skeletons, empty states, offline or failure screens, writing button labels and UI text in French and English, choosing tone (vous/tu, you)
verified: 2026-10-10
revisit_days: 180
sources: ["https://design-system.service.gov.uk/components/error-message/", "https://design-system.service.gov.uk/patterns/question-pages/", "https://www.nngroup.com/articles/form-design-placeholders/", "https://www.nngroup.com/articles/error-message-guidelines/", "https://www.nngroup.com/articles/response-times-3-important-limits/", "https://www.nngroup.com/articles/skeleton-screens/", "https://www.nngroup.com/articles/empty-state-interface-design/", "https://carbondesignsystem.com/patterns/empty-states-pattern/", "https://www.canada.ca/en/treasury-board-secretariat/services/government-communications/canada-content-style-guide.html", "https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html", "https://en.wikipedia.org/wiki/Telephone_numbers_in_Cameroon"]
---
# Forms, states and microcopy

Most user time is spent filling, waiting and recovering. Design these on purpose: every screen gets a state matrix (`ux-design` pack) and every message is written, not left to the framework default.

## Decision guide

**1. Forms.**
- Ask less: every field needs a reason. One thing per page for long or unfamiliar flows (GOV.UK: "start by asking one question per page"); short familiar forms can be one page.
- Visible labels above fields. Placeholders are hints that "disappear when the user types" (NN/g), so never use them as labels.
- Right input types and keyboards (`inputmode="numeric"`, `type="tel"`, `autocomplete` tokens); Cameroonian phone numbers with the +237 prefix pre-filled (national numbers have 9 digits since November 2014); amounts in FCFA without decimals.
- Mark optional fields "(facultatif)" / "(optional)" rather than starring required ones; group related fields; one primary button with a verb.
- Validate on submit (and on blur for format errors once a field was touched), never on every keystroke; check server-side too.

**2. Error messages** (GOV.UK, NN/g, WCAG 3.3.1).
- Show the message next to the field and in an error summary at the top that links to each field; use the same text in both. Red border plus text plus an icon, never colour alone.
- Say what happened and how to fix it, in plain words: "Entrez un numéro à 9 chiffres, par exemple 6XX XX XX XX" / "Enter a 9-digit number".
- GOV.UK's do-not list: technical jargon ("error 0x0000000643"), blame words ("forbidden", "illegal", "you forgot"), "please", "sorry", "valid/invalid", humour like "oops".
- Keep everything the user typed (both passing and failing answers). Don't use field errors for problems the user can't fix (no permission, service down): show a page or banner with what to do next.
- Match severity: warnings for risky but allowed actions, errors for blocking ones.

**3. Waiting.** NN/g's limits: 0.1 s feels instant, 1 s keeps the flow of thought, 10 s is the limit of attention.
| Expected wait | Show |
|---|---|
| < 1 s | nothing (an indicator just flashes) |
| 1–10 s, whole page | skeleton screen shaped like the content |
| 1–10 s, one module | spinner in that module |
| > 10 s | progress bar with an estimate; let people leave and come back |
Optimistic UI for safe, reversible actions; never for payments (show "pending" honestly; see `security/payments`).

**4. Empty states.** Carbon distinguishes first use (no data yet), user action (cleared, no results) and error cases. NN/g: an empty state should communicate system status, teach, and give a direct pathway to the key task. Write: what this area is for + one action ("Aucune facture pour l'instant. Ajoutez votre compteur ENEO pour suivre vos factures. [Ajouter un compteur]"). No-results states repeat the query and offer to broaden it.

**5. Offline and failure.** Say it plainly, keep what works usable (cached data with a "last updated" time), queue safe actions and say they are queued, offer retry. Distinguish "no connection" from "our server failed" (`frontend/low-bandwidth`, `frontend/errors-observability`).

**6. Microcopy and tone, in two languages.**
- Canada.ca (a bilingual EN/FR guide with parallel French sections): write directly to the person ("you"), active voice, familiar words, sentences ideally under 15–20 words, paragraphs of one idea and at most three sentences, descriptive links (never "click here"). People with literacy challenges "read word by word".
- Buttons are verbs naming the result: "Payer 15 000 FCFA", "Enregistrer", "Save changes"; the same action keeps the same name across the flow.
- French register: decide *vous* or *tu* in direction.md and keep it everywhere; money, health and government flows usually call for *vous*. Use accented capitals and French punctuation spacing (`design/typography`).
- Write both languages from the start and have a fluent speaker review each; don't ship machine translation unreviewed. Keep strings in catalogs with ICU plurals (`frontend/i18n-l10n`, `eos i18n check`).
- No jokes or idioms in errors; they translate badly and read as careless when money is involved.

## Examples
```
Error summary (top):   Il y a un problème
                       • Entrez votre numéro de téléphone   → links to #phone
Field:   Numéro de téléphone
         Hint: Le numéro utilisé pour Mobile Money
         [ +237 | 6__ __ __ __ ]   ← red border
         ⚠ Entrez un numéro à 9 chiffres, par exemple 6XX XX XX XX
```

## Anti-patterns
- Placeholder-only fields; clearing the form after an error; validation on every keystroke.
- "Une erreur est survenue" / "Something went wrong" with no next step; "Oops!"; error codes as the message.
- Spinners for full-page loads over 10 s with no progress; skeletons that flash for 200 ms.
- Blank tables and lists; "No data" with no explanation or action.
- English strings hard-coded in components; French added at the end by machine translation.

## Checks
- `eos i18n check` (missing keys, ICU arguments) and `eos verify` lane checks.
- Playwright: submit the empty form, assert the error summary and focus move; axe on the error state.
- Screenshot every state in the matrix during critique (rubric rows 7 and 8); a French and an English speaker read the copy.

## Sources
- GOV.UK Design System, Error message: https://design-system.service.gov.uk/components/error-message/
- GOV.UK Design System, Question pages: https://design-system.service.gov.uk/patterns/question-pages/
- NN/g, Placeholders in form fields are harmful: https://www.nngroup.com/articles/form-design-placeholders/
- NN/g, Error-message guidelines: https://www.nngroup.com/articles/error-message-guidelines/
- NN/g, Response times: the 3 important limits: https://www.nngroup.com/articles/response-times-3-important-limits/
- NN/g, Skeleton screens 101: https://www.nngroup.com/articles/skeleton-screens/
- NN/g, Designing empty states in complex applications: https://www.nngroup.com/articles/empty-state-interface-design/
- Carbon Design System, Empty states pattern: https://carbondesignsystem.com/patterns/empty-states-pattern/
- Canada.ca Content Style Guide: https://www.canada.ca/en/treasury-board-secretariat/services/government-communications/canada-content-style-guide.html
- WCAG 2.2 Understanding 3.3.1 Error Identification: https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html
- Wikipedia, Telephone numbers in Cameroon: https://en.wikipedia.org/wiki/Telephone_numbers_in_Cameroon
