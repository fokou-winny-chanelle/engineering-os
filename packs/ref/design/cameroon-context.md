---
id: design/cameroon-context
title: Designing for users in Cameroon (bilingual French/English and local languages, lower literacy, mobile-first and costly data, low-end Android, money and trust, research with local users)
area: design
read_when: designing for Cameroonian or Central African users, choosing languages and tone, designing for lower literacy or first-time smartphone users, low bandwidth or data cost matters, mobile money or FCFA amounts, recruiting local usability participants
verified: 2026-10-10
revisit_days: 180
sources: ["https://datareportal.com/reports/digital-2025-cameroon", "https://api.worldbank.org/v2/country/CMR/indicator/SE.ADT.LITR.ZS?format=json", "https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-economy/africa/", "https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/wp-content/uploads/2014/03/Grameen-Presentation.pdf", "https://www.nngroup.com/articles/writing-for-lower-literacy-users/", "https://en.wikipedia.org/wiki/Languages_of_Cameroon", "https://en.wikipedia.org/wiki/General_Alphabet_of_Cameroon_Languages", "https://www.itu.int/itu-d/reports/statistics/facts-figures-2025/"]
---
# Cameroon context

These are national averages and research from comparable settings, not facts about *your* users. Use them to ask better questions, then check with 5 real users (`design/critique-rubric`). Never design from stereotypes; Douala office workers and rural farmers are different audiences.

## Decision guide

**1. Know the baseline (DataReportal Digital 2025, early 2025).** Population 29.5 million, median age 18.0, 60.2% urban. 25.5 million cellular connections (86.3% of the population; some people hold several SIMs), 12.4 million internet users (41.9%), so about 17.1 million people (58.1%) were offline. Ookla's median fixed download speed was 9.48 Mbps. Across Africa, GSMA reports that almost 1 billion people (63%) don't use mobile internet despite coverage; the barriers it names are device affordability, limited digital skills and a lack of relevant content. ITU counts 2.2 billion people offline worldwide in 2025, most in low- and middle-income countries. Design consequence: many first-time and occasional users, on phones, paying for data.

**2. Languages.** French and English are official; Cameroon "is home to at least 250 languages"; lingua francas include Cameroonian Pidgin English (widely used in the English-speaking Northwest and Southwest), Camfranglais in cities, Fulfulde and others (Wikipedia, Languages of Cameroon).
- Ship French and English with equal quality (both reviewed by fluent speakers), switchable everywhere, remembered, and never mixed on one screen by accident.
- Consider Pidgin or a local language for onboarding audio/video or support where your users need it; Grameen Foundation's mobile-money usability research with women in India and the Philippines (shared by GSMA, 2014) recommends "Use language I know".
- Names and places: support Latin Extended letters (ɛ ɔ ŋ ə) and tone marks in inputs, storage (UTF-8, NFC normalisation), search and fonts (`design/typography`). Don't force first/last name splits; allow one name field.

**3. Lower literacy is common, and different from illiteracy.** Adult literacy was 72.6% (2018, World Bank / UNESCO data), 66.2% for women. NN/g's research on lower-literacy users: they read word for word ("plow" the text), miss elements outside a narrow field of view, lose their place when scrolling, satisfice on little information and struggle to spell search queries. Their advice: put the main point at the very top, a single main column, a linear menu of main choices, no moving text, misspelling-tolerant search.
- Pair icons with words, keep one icon per meaning, use photos of real objects (the meter, the receipt) where that helps recognition.
- Numbers people can trust: big, clear amounts; "Drop the decimals" (GSMA/Grameen); FCFA formatted with Intl (`15 000 FCFA`).
- Fewer steps: women in that research tried to memorise the steps "but falter after 3-4 steps". Count taps for the main task and cut.
- Offer audio or a call-back/WhatsApp help line for complex tasks; assisted use (a relative, an agent) is common; that research found "assisted transactions are not the exception, but the norm", so avoid flows that only the account owner can follow.

**4. Devices and data.** Design for a low-end Android phone on a slow or interrupted connection with prepaid data:
- small pages and images, no autoplay video, offline-tolerant flows with clear "saved/queued" states (`frontend/low-bandwidth`);
- show sizes before large downloads ("Télécharger (2,4 Mo)") and let people choose lighter options;
- test on a real entry-level phone in bright light; 360 px wide is a sensible minimum to design for, 320 px to survive.

**5. Money and trust.**
- Show who receives the money, the exact amount, fees and the operator before confirming; give a receipt with a reference people can read out on the phone.
- Pending is a real state: mobile-money confirmations can arrive late; say what happens next and never charge twice (`security/payments`).
- Familiar brands and channels build trust: show the operator's name the user knows (e.g. Orange Money, MTN Mobile Money) as text, with their logo only if you have the right to use it.

**6. Research with local users.** Recruit through existing networks (associations, markets, churches, schools, partner agents), pay or thank fairly, test in their language and on their phones, in person where possible, and get consent in plain words. Read local design and civic-tech work, and cite it when you use it.

## Examples
```
Payer ENEO — étape 2 sur 3
┌───────────────────────────────┐
│ Montant à payer               │
│ 15 000 FCFA        (big)      │
│ Frais Orange Money : 150 FCFA │
│ Total : 15 150 FCFA           │
│ [ Confirmer et payer ]        │
│ [icône] Écouter  [icône] Aide │  ← icon + word, never icon alone
└───────────────────────────────┘
```

## Anti-patterns
- English-only or machine-translated French; one language for UI and another for error messages.
- Long paragraphs, small grey text, many choices per screen, flows of 8+ steps.
- Heavy hero images and animations on data-priced connections.
- Assuming a credit card, an email address or a fixed address.
- Treating "Cameroonian users" as one group; skipping local testing because statistics exist.

## Checks
- Critique rubric row 11 (context) is scored by a person who knows the audience, not by an agent alone.
- Tap count for the top task; page weight budget (`frontend/web-vitals-budgets`); a 360 px screenshot on a low-end device.
- A usability round with 5 local users per main group, in their language, before launch.

## Sources
- DataReportal, Digital 2025: Cameroon: https://datareportal.com/reports/digital-2025-cameroon
- World Bank API, Literacy rate, adult total, Cameroon (UNESCO UIS data): https://api.worldbank.org/v2/country/CMR/indicator/SE.ADT.LITR.ZS?format=json
- GSMA, The Mobile Economy Africa 2025: https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-economy/africa/
- GSMA / Grameen Foundation, Gender and usability (mobile financial services): https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/wp-content/uploads/2014/03/Grameen-Presentation.pdf
- NN/g, Lower-literacy users: https://www.nngroup.com/articles/writing-for-lower-literacy-users/
- Wikipedia, Languages of Cameroon: https://en.wikipedia.org/wiki/Languages_of_Cameroon
- Wikipedia, General Alphabet of Cameroon Languages: https://en.wikipedia.org/wiki/General_Alphabet_of_Cameroon_Languages
- ITU, Facts and Figures 2025: https://www.itu.int/itu-d/reports/statistics/facts-figures-2025/
