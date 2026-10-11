# Design studio A/B evaluation

Question: do the studio sources (impeccable, ui-ux-pro-max, review-animations) make our agents design better
screens than our own packs alone? The studio stays only if it wins (rule below).

## Layout
- `arm-a/`: baseline. Our design packs and refs only.
- `arm-b/`: the same, plus the studio in `arm-b/.eos/studio/`.
- Both arms have the same three specs (`specs/`) and the same `PROMPT.md` except its "Context" section.

## Steps
1. **Produce.** Open a fresh agent session in `arm-a/` and give it `PROMPT.md`. Then a fresh session in
   `arm-b/` with its `PROMPT.md`. Same agent, model, settings and time budget for both. Do not reuse a session.
   For a stronger result, repeat with a second pair of sessions in new workspaces.
2. **Score automatically and blind.** `{{EOS}} design ab score <workspace> [--shoot]`. This runs
   `eos design check` on every screen (saved in `auto.json`), copies the screens to `scoring/<screen>/X|Y`
   (random per screen), writes a blank critique sheet for each and `scoring/shoot.sh` (Playwright screenshots
   at 360 px light/dark, 1280 px and 320 px). The key is `.ab-key.json`; the scorer must not open it. If a
   "blinding leak" is reported, hide that text first.
3. **Score by hand.** A person who did not run the sessions scores each `X-critique.md` and `Y-critique.md`
   with the 12-row rubric (0/1/2 per row; judge the screenshots, not the code).
4. **Decide.** `{{EOS}} design ab report <workspace>` unblinds, applies the rule and writes `REPORT.md`.

## Decision rule
Keep the studio only if ALL hold:
1. arm B's mean critique total is at least 2 points (of 24) above arm A's;
2. B scores higher on at least 2 of the 3 screens;
3. B has no 0 on gate rows 5, 7, 9 or 10 where A scored above 0 on the same screen;
4. B's total `eos design check` errors are not higher than A's.

Otherwise drop it (`eos studio off`; do not sign off the sources). Ties and small wins are a drop.

impeccable's own `detect` counts are recorded as a secondary signal only: arm B read its rules, so it is not a
fair judge.
