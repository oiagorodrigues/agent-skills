---
name: plain-writing
description: "Checklist of telltale AI-chatbot writing patterns to avoid (puffery vocabulary, \"not just X but Y\" and \"X, not Y\" constructions, canned Challenges/Conclusion sections, inline-bold bullet lists, em-dash overuse, title-case headings, filler like \"let me know\"), adapted from Wikipedia's \"Signs of AI writing\". Use before writing any prose a person will read: chat replies, summaries, PR descriptions, commit messages, Jira and Confluence pages, docs, comments. Points to the author's own voice (the my-voice skill, when present) for anything written for him to send or publish."
---

# Plain writing

Adapted from Wikipedia's "Signs of AI writing" field guide (Wikipedia:Signs_of_AI_writing), without the Wikipedia-specific parts, plus six patterns from blader's humanizer (MIT, https://github.com/blader/humanizer).

Apply it every time you write output a person will read: chat replies, summaries, Confluence and Jira pages, PR descriptions, commit messages and docs.

This is about producing plainer, less formulaic writing — not about avoiding any single word or device forever. The tell is density and formula, not any one instance.

The patterns apply in every language. When writing in Portuguese (or any other language), avoid the direct equivalents of the English examples below ("não apenas X, mas Y", "X, não Y", "do X ao Y", "vale ressaltar", "desempenha um papel fundamental").

## Words and phrases to avoid

**Puffery / legacy language:** stands as, serves as, is a testament to, plays a crucial/pivotal/vital/significant/key role, underscores/highlights its significance, reflects broader, symbolizes its enduring/lasting, sets the stage for, marks a shift, key turning point, evolving landscape, focal point, indelible mark, deeply rooted, boasts, vibrant, rich, profound, enhancing, showcasing, exemplifies, commitment to, groundbreaking, renowned, diverse array, nestled, in the heart of, featuring.

**Overattribution / notability signaling:** independent coverage, [x] media outlets, trade publications, cited/featured/profiled in, active social media presence, written by a leading expert.

**Superficial analysis tacked on with "-ing":** highlighting, underscoring, emphasizing, ensuring, reflecting, symbolizing, contributing to, cultivating, fostering, encompassing, enhancing, valuable insights, align/resonate with.

**Weasel attribution:** industry reports (show), observers have cited, experts argue, some critics argue, several sources/publications (when citing one or two), "such as" implying a non-exhaustive list when it isn't.

**Editorializing / disclaimers:** it's important/critical/crucial to note/remember/consider, worth noting, may vary.

**Section-summary filler:** in summary, in conclusion, overall.

**"AI vocabulary" (avoid regardless of which model era coined it):** additionally (esp. sentence-initial), align with, bolstered, crucial, deep dive, delve, emphasizing, enduring, enhance, fostering, garner, highlight (verb), interplay, intricate/intricacies, key (adjective), landscape (abstract noun), meticulous(ly), pivotal, robust, showcase, tapestry (abstract noun), testament, underscore (verb), valuable, vibrant. Grok-flavored: causal, empirical, correlate (used loosely/decoratively).

**Copula avoidance / marketing verbs in place of "is/has":** serves as a, stands as, marks, functions as, operates as, represents [a], boasts/features/maintains/offers [a] (instead of plain "has"), refers to (used to dodge stating the subject directly).

**Vague connection language:** in connection with/to, connected with/to, in association with, associated with — instead of stating the actual relationship directly.

**Collaborative-chatbot leakage (never appropriate in written output):** I hope this helps, of course!, certainly!, you're absolutely right!, would you like..., is there anything else, let me know, here is a, more detailed breakdown, as an AI language model.

## Structural and rhetorical patterns to avoid

- **Undue emphasis on significance/legacy/broader trends** — inflating a minor fact by tying it to a "broader" theme, movement, or debate it barely touches.
- **Canned "Challenges" / "Future Outlook" close** — "Despite its [positive traits], X faces several challenges..." as a rote closing formula, or a bolted-on speculative-future paragraph.
- **Negative parallelism** — "not just X, but Y" / "it's not X, it's Y" / "no X, no Y, just Z" / "Y rather than X" used as a rhetorical crutch instead of stating the point plainly.
- **"X, not Y" contrast and preemptive disclaimers** — defining something by what it isn't, usually against a straw man nobody raised: "These are individual accounts, not representative surveys", "It's a guideline, not a rule", "São relatos individuais, não pesquisas representativas", "É um ponto de partida, não uma solução final". State what it is and, if the limit matters, say the consequence directly ("These come from five interviews, so they can't tell us how common the problem is"). Also covers the trailing-negation variants "X — and that's not a bug" / "e isso não é por acaso".
- **"From X to Y" false ranges** — "from startups to Fortune 500 companies", "from planning to execution", "do planejamento à execução", "do iniciante ao avançado", "de pequenas empresas a grandes corporações". The two endpoints don't define a real scale; they gesture at breadth instead of naming what's actually covered. List the real items or state the actual scope ("works for teams of 5 to 50 people" is fine because it's a measured range).
- **Rule of three** — reflexively grouping things into triads ("fast, flexible, and reliable") to make a claim look more thorough than it is.
- **Regression to the mean / generic praise over specifics** — replacing a precise, unusual fact with a vague, positive-sounding generalization (e.g. "a revolutionary force in the industry" instead of the actual specific thing the subject did).
- **Present-participle synthesis clauses** — ending a sentence with an unearned "-ing" clause that asserts significance the preceding facts don't support.
- **Overuse of boldface** — bolding many phrases mechanically, "key takeaways" style, instead of reserving emphasis for what actually needs it.
- **Inline-header bullet lists** — "**Bold label**: description" repeated down a list as a substitute for actual prose when prose would read better.
- **Title case headings** — capitalizing every main word in a heading/subheading instead of sentence case.
- **Headings that contain only sub-headings**, with no actual content under them.
- **Overuse of em dashes** — especially spaced em dashes used formulaically for "punched up" emphasis where a comma, colon, or parenthesis would be plainer and more natural.
- **Emoji used as bullet/heading decoration.**
- **Thematic break rules (`---`)** dropped between every section for no structural reason.
- **Small, sparse tables** used where a sentence or two of prose would communicate the same thing better.
- **Curly/smart quotes and apostrophes** in place of straight ones, especially mixed inconsistently with straight quotes in the same piece.
- **Uniform sentence rhythm / low lexical diversity from repetition-penalty artifacts** — mechanically varying word choice to avoid repeating a term rather than repeating it plainly when repetition is the clearest option ("elegant variation").
- **One-line closers and dramatic fragments** — a one-sentence paragraph that restates the one before it ("That distinction matters.", "Let that sink in.", "E isso faz toda a diferença."), or the same kind of closer after every section. Cut it unless it adds a new fact.
- **Staged run-up before the point** — "Let's dive in", "Here's the thing", "Honestly?", "Vamos lá", "O ponto é o seguinte" as an opener before a routine claim. Start with the point.
- **Hyphenated compound after the noun** — "the process is well-documented". Keep the hyphen before the noun ("a high-quality report") and drop it after ("the report is high quality").
- **Knowledge-limit disclaimers and guesses** — "based on available information", "not widely documented", "as of my last update", followed by a plausible guess. Say what the source doesn't show, or cut the sentence; never fill the gap with a guess.
- **A heading repeated in the first sentence** — "## Performance" followed by "Speed matters." Remove the restating line.
- **Re-explaining what the reader knows** — in a reply, rebuilding the problem, the diagnosis and the evidence they already have before reaching the decision. Lead with the decision and keep only the one fact they lack and the link they need.
- **Avoiding plain "is/has" constructions** in favor of stiffer synonyms (authored vs. wrote, utilized vs. used, relocated vs. moved, attempted vs. tried, passed away vs. died) — plain words are usually better, not worse.
- **Avoiding hedges and superlatives entirely** isn't the goal either — natural writing does use "very," "one of the best," "the first," "tends to." Don't over-correct into flat, hedge-free, superlative-free prose; that's its own tell.

## Write as the author

Documents, pages, PRs and messages written for someone else to publish must read as if that person wrote them. The reader should never be able to tell an assistant was involved.

- Use the author's voice: "I measured", "I recommend", "we should", "our pipeline". The author owns the claims and the recommendation.
- No traces of the conversation that produced the text: no "as requested", "you asked", "this page describes what I found", "nothing has been changed yet", no notes addressed to the requester, no recap of the steps taken to research it.
- State findings as the author's own conclusions. Explain the method only where a reader needs it to trust a number ("from Cost Explorer, September 2026").
- Chat replies to the user are the exception: there you are talking to them, so address them directly.

## The author's voice

If `~/.agents/skills/my-voice/SKILL.md` exists, read it for the author's voice before writing anything in his name.

## Concise, clear and compelling

- Lead with the point: the problem, the number that proves it, the ask. A reader who stops after the first paragraph should know what is being proposed and why.
- Cut every sentence that doesn't change what the reader knows or decides. Prefer one strong number to five weak ones.
- Short sections. Tables only where the reader compares several things across the same attributes.
- Make the case with specifics (measured numbers, a concrete failure, a cost) instead of adjectives.
- When the text argues for a technical change or describes a technical trade-off, frame it in business terms with the `business-first-pitch` skill.
- End with the decision or action needed, not a summary.

## Complete, connected sentences

People write a whole thought in one sentence and connect it to the next one. AI text tends to chop a thought into fragments that the reader has to stitch back together.

- Finish the thought in the sentence that starts it. "It isn't: the data is 10 minutes old" becomes "The reports aren't real-time, because their data is about 10 minutes old on average."
- Don't split cause and effect, or a claim and its reason, across two short sentences. "The orders ETL is the cause. It runs every 15 minutes." becomes "The cause is the orders ETL, which runs every 15 minutes and..."
- Use connecting words (because, so, which, but, while, that means) where one idea follows from another, instead of stacking short declarative sentences.
- Avoid label fragments standing in for a sentence: "**Stale data.** A change waits..." or "Cost today: $290". Write the sentence the label was summarizing ("Report data is stale because...").
- Avoid colon setups that end a sentence early ("The risk is operational: ...", "Git history covers the why: most are...") when a plain sentence says it directly ("Git history says that most are..."). A source or topic followed by a colon reads as LLM text; make the source the subject of a plain verb instead.
- Put the confidence inside the claim, worded from its evidence, instead of adding a disclaimer sentence after it. "Deve ser a mesma conta Enterprise. Isso é inferência, não confirmei." becomes "O plano enterprise com os mesmos 53 de 70 seats indica que é a mesma conta Enterprise." In English, "It's the same account. This is a belief, I didn't check it." becomes "The identical seat count suggests it's the same account." When it matters, name the check that would settle it in the same sentence ("…, which an org admin's listing would confirm").
- Bullets are fine for real lists, but each bullet should still be a complete sentence or a clean list item, not half a thought.
- Concise still applies: join fragments into one sentence instead of adding words.

## Docs, instructions and technical detail

From Lauren Tan's pstack technical-writing (MIT, https://github.com/cursor/plugins/tree/main/pstack), the parts the rest of this skill doesn't cover.

- Cut every word that does no work: "in order to" is "to", "it is important to note that" is nothing.
- Write the real symbol, file, flag or command name instead of a synonym or a description of it.
- Don't invent jargon or metaphors ("evacuate", "ratchet", "endgame"). Use the words a developer would say out loud, and define a named pattern the first time it appears.
- Give a document one job: a tutorial, a how-to, a reference or an explanation. Split and link instead of mixing them, for example a reference table inside a how-to.
- In instructions, talk to the reader as "you" in the present tense, write one command per sentence ("Run `make check`."), and put the condition or warning before the step it guards ("To delete the document, click Delete."). Never write "simply", "easy" or "quickly" in a procedure.
- Name who does what ("the compiler checks" instead of "is checked"), unless the actor is unknown or beside the point.
- Put the common case first and the exceptions after it.
- Keep "only" and "not" next to the word they change, and break long noun strings ("the proto import budget check script" becomes "the script that checks the proto-import budget").
- Make every "it", "this" and "they" point at one obvious thing, and never use "this" or "which" for a whole clause. Repeat the noun when in doubt.
- No slashes ("and/or", "a/b") and no "(s)" plurals. Write "a, b or both".
- Link text says where the link goes (the page title), never "click here".
- Number the steps of a sequence and use bullets for everything else, introduced by a complete sentence and kept parallel.
- Make every count or tree in a doc true at the commit that lands it, and give the command that regenerates it.

## Quick self-check before sending output

1. Any word from the vocabulary list above? Cut it or replace with the plain synonym.
2. Any sentence ending in an unearned "-ing" clause asserting importance/significance? Cut the clause or back it with a real specific.
3. Any "not just X, but Y" / "it's not X, it's Y" / "X, not Y" construction, or a "from X to Y" / "do X ao Y" pseudo-range? Say the point directly or list the real items instead.
4. Any bullet list where the items are "**Bold label**: sentence" repeated more than twice? Consider prose instead.
5. Any heading in Title Case, any heading with no body text under it, any stray `---` break, any emoji-as-bullet? Fix.
6. Any collaborative/chatbot phrasing ("I hope this helps," "let me know," "would you like")? Delete — this is output, not a conversation with the reader about the output.
7. Any canned "Challenges" or "In summary/In conclusion/Overall" closing paragraph that restates what was already said? Cut it.
8. Does a claim of significance/impact/legacy actually follow from a specific fact stated nearby, or is it doing the work the specifics should be doing? If the latter, replace it with the specific.
9. Any standalone disclaimer such as "Isso é inferência, não confirmei", "This is unverified" or "(belief)" after a claim? Fold it into the claim, worded from its evidence ("X indica que…", "X suggests…").
10. Read it aloud. Does any sentence end before its thought does, lean on the next sentence to finish it, or stand as a bold label instead of a sentence? Join or rewrite it so each sentence says something complete.
11. Is a document written for someone else in their voice, with no trace of the conversation behind it? Would it get shorter without losing a fact or an argument? Fix both.
12. Not everything on this list is inherently wrong in isolation (transition words, formal vocabulary, citations, hedges) — the tell is density and formula, not any single instance. Don't over-correct into stilted, hedge-free, rhythm-flattened prose either.
