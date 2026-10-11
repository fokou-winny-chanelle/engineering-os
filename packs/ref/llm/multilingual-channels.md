---
id: llm/multilingual-channels
title: Multilingual LLM products for Cameroon and Africa (French and English, local languages and Pidgin, evaluation per language, voice, WhatsApp bots and Meta's AI-provider rules, SMS/USSD fallbacks)
area: llm
read_when: building an assistant or bot for French/English users, supporting local languages, adding voice input or output, launching on WhatsApp, or serving feature-phone users via SMS/USSD
verified: 2026-10-10
revisit_days: 90
sources: ["https://www.ethnologue.com/country/CM/", "https://arxiv.org/abs/2406.03368", "https://glottolog.org/resource/languoid/id/came1254", "https://developers.openai.com/api/docs/guides/speech-to-text", "https://huggingface.co/facebook/mms-1b-all", "https://business.whatsapp.com/policy", "https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing", "https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers"]
---
# Languages and channels

Cameroon has two official languages, English and French, and Ethnologue counts 275 living indigenous languages, five of them used in formal education. Users mix languages in one message, and many also use Cameroon Pidgin (an English-based creole). Models are strongest in English and French and much weaker in most African languages, so design for that gap. UI translation basics: `frontend/i18n-l10n`, `mobile/observability-a11y-i18n`.

## Decision guide

**1. French and English as first-class, tested separately.**
- Detect the language per message (and allow a user setting); answer in the user's language unless they choose otherwise. Keep system prompts in one language but state the reply-language rule explicitly.
- Eval cases tagged `lang:fr` and `lang:en` with their own thresholds (`llm/evals-in-production`); native speakers write and review them, including local usage (FCFA amounts, phone formats, place names, informal French).
- Retrieval: index both languages, use a multilingual embedding model, and a French text-search configuration for French documents (`llm/rag`). Do not translate the whole corpus unless evals show it helps.
- Glossaries for product terms (Mobile Money, NIU, "recharge") so both languages stay consistent.

**2. Local languages and Pidgin: measure before promising.** IrokoBench (17 African languages, human-translated) found a significant gap between high-resource languages such as English and French and low-resource African languages, across open and proprietary models; translating inputs into English first ("translate-test") helped in some settings. Practical approach:
- Decide which languages matter from user research, not assumption.
- Build a small eval set per language with native speakers; compare direct answering, translate-in/translate-out, and a human handover.
- Be honest in the UI ("Je comprends mieux le français et l'anglais"); offer a human or a voice line where the model fails.
- Never auto-send legally or financially binding text in a language you have not evaluated.

**3. Voice.** Speech can reach users who read little or prefer to speak. OpenAI says Whisper supports 98 languages "but accuracy varies by language"; test speech-to-text with real accents, background noise and code-switching. Open models with very wide coverage exist (Meta's MMS checkpoint lists 1,107 languages for transcription) but check licences: `facebook/mms-1b-all` is CC-BY-NC-4.0, **non-commercial**. Confirm what you heard ("Vous voulez envoyer 5 000 FCFA à Paul ?") before any action. Voice data is personal data (`llm/privacy-residency`).

**4. WhatsApp bots (business messaging), rules that change design.**
- Automation is allowed when replying within the 24-hour customer service window, but WhatsApp's Business Messaging Policy requires "prompt, clear, and direct escalation paths" (human transfer in chat, phone, email, web support, store visit or support form).
- Outside the window you can only send approved message templates. Pricing has been per message since 1 July 2025: templates are charged; non-template messages are free but only inside an open window; utility templates inside an open window are free (rates: Meta's pricing page, not here).
- Since 15 January 2026, Meta's terms allow "AI Providers" to offer **general-purpose AI assistants** on the WhatsApp Business Platform only where Meta is legally required to permit it. A business bot for your own service (orders, support, payments) is the normal case; a general "ask me anything" chatbot is not. Read the current terms before launch.
- Design: short messages, buttons/lists over free text for key choices, no streaming, a quick acknowledgement for slow answers, media size limits, and a "talk to a person" option always visible.

**5. SMS and USSD.** For feature phones and poor data coverage, keep critical flows (balance, confirmations, OTP alternatives) available as SMS or USSD menus driven by deterministic code; use the LLM, if at all, offline (e.g. to draft menu text or classify inbound SMS), not inside a live USSD session. Check your aggregator's limits on session length and message size; see `ops/africa-connectivity` and `mobile/auth-payments`.

**6. Low bandwidth everywhere.** Keep responses short by default (cost and data), compress or avoid images, and let users continue a conversation after a dropped connection (`frontend/low-bandwidth`).

## Examples
```text
System: Reply in the language of the user's latest message (French or English). If the user writes in
Pidgin or another language you cannot answer reliably, reply in simple French and English and offer
the "Parler à un agent / Talk to an agent" button. Amounts in FCFA with a space as thousands separator.
```

## Anti-patterns
- Testing only in English and shipping to a French-speaking majority.
- Claiming support for a local language because a demo worked once.
- A WhatsApp bot with no human escalation, or a general-purpose assistant on the Business Platform.
- Non-commercial models (CC-BY-NC) in a paid product; actions taken on unconfirmed speech input.

## Checks
- [ ] Eval sets and thresholds per language (FR, EN, plus any promised local language) reviewed by native speakers.
- [ ] Clear language policy in prompts and UI; human handover on every channel.
- [ ] WhatsApp flows checked against the current Business Messaging Policy and AI-provider terms.
- [ ] Critical flows have an SMS/USSD or offline path that does not depend on the model.

## Sources
- Ethnologue, Cameroon: https://www.ethnologue.com/country/CM/
- Adelani et al., IrokoBench (2024): https://arxiv.org/abs/2406.03368
- Glottolog, Cameroon Pidgin: https://glottolog.org/resource/languoid/id/came1254
- OpenAI speech to text (Whisper languages): https://developers.openai.com/api/docs/guides/speech-to-text
- Meta MMS model card (languages, licence): https://huggingface.co/facebook/mms-1b-all
- WhatsApp Business Messaging Policy: https://business.whatsapp.com/policy
- WhatsApp pricing: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing · AI providers: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers
