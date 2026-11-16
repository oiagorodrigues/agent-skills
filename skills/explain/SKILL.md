---
name: explain
description: Re-explains the last message in plain words, using the project's own vocabulary, starting from the context the reader missed and ending with what they need to do or decide. Use when the user runs /explain, optionally naming the part that didn't land.
argument-hint: "the part that didn't land (optional)"
disable-model-invocation: true
---

That last message did not land. Re-pitch it instead of repeating it.

1. **Start from where we are.** One or two sentences of the context the reader was
   missing: what we were doing, and what just changed.
2. **Then the point, in plain words.** Short sentences, one idea each, active voice and
   common words, written to the `plain-writing` skill
   (`~/.agents/skills/plain-writing/SKILL.md`). The point goes first; the why follows in
   a few lines at most.
3. **Use the project's own terms**, as its glossary defines them (the project's domain
   skill names where that glossary lives). A term you cannot avoid gets a few-word
   definition the first time it appears.
4. **End with what the reader has to do or decide**, or say plainly that nothing is
   needed.

If the user named the part that did not land, re-pitch only that part.

<!-- Adapted from mattpocock/skills `wait-what` (MIT, (c) 2026 Matt Pocock), via zizi-skills; see THIRD_PARTY_NOTICES.md. -->
