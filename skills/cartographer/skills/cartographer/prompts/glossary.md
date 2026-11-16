# Glossary pass (LLM)

You turn the scripted draft `.cartographer/glossary.md` into a glossary a new engineer can trust. Inputs: `.cartographer/glossary.json` (terms, definition sites, synonym flags) and the project's source.

Format and rules follow Matt Pocock's domain-modeling `GLOSSARY.md` (MIT, https://github.com/mattpocock/skills).

## Steps

1. Drop terms that are general programming concepts (a timeout, a modal, a cache) rather than ideas specific to this business. Keep a dropped term out of the output entirely.
2. For each remaining term marked `to define`, open its first definition site and the two or three files that use it most, then write one or two sentences saying what the thing is, in business words. When the code doesn't settle it, keep "to define" and add the question a domain expert should answer.
3. For each entry under "Possibly the same concept", read both definition sites and decide: same concept (pick the name the code uses most and list the others under `_Avoid_`), different concepts (write one line on how they differ), or unclear (keep the flag and say what would decide it).
4. Check every meaning the script inferred from a comment or enum values against the code, and fix it when the code disagrees.

Done when no term is marked "to define" without a question next to it and every synonym flag has a verdict.

## Output

Write `.cartographer/GLOSSARY.md`, never inside the project's own tree:

```md
# <Project> glossary

## Language

**Order**:
A retailer's purchase from one brand, created when a cart is checked out.
_Avoid_: Purchase, Sale
_Defined_: `src/models/order.ts:12`

**Licence** (to define):
Question for the domain expert: is a Licence the state permit or the record of it on a company?
_Defined_: `app/models/licence.rb:3`

## Open questions

- Buyer / Retailer: the code uses both for the purchasing company; confirm they are one concept.
```

Group terms under subheadings when clusters appear (ordering, compliance, payments). Report back the number of terms kept, dropped, defined and still open.
