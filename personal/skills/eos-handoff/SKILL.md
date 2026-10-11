---
name: eos-handoff
description: Write a compact handoff so a fresh session (or a human) can continue - use when stopping on a loop limit, a blocker, a long/confused context, or at the end of a work session.
---
# eos-handoff: stop cleanly, resume cheaply

1. Overwrite `memory/handoff.md` (≤30 lines) with these sections:
   - **Goal**
   - **State**: what works, what fails, the exact failing command and the last ~10 output lines
   - **Tried**: each attempt and why it failed
   - **Hypotheses**, ranked
   - **Next step**: one concrete action
   - **Needs a human for**
2. Update `memory/active-context.md` (now / next / blockers) and append to `memory/progress.md` if something finished.
3. List any uncommitted changes (`git status --short`) and say whether they are safe to keep.
4. Tell the user: "Handoff written. Start a new session and say: *read memory/handoff.md and continue*."
Don't attempt further fixes after writing the handoff.
