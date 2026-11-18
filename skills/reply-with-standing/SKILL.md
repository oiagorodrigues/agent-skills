---
name: reply-with-standing
description: Use every time you write, rewrite or review a message that goes to another person on the user's behalf - a Slack reply, DM or channel post, a PR review comment or a reply to one, a Jira or Confluence comment, an email, a request for review or a decision, a follow-up on a cold thread, or pushback on someone's idea. Also use when the user pastes their own draft and asks "how do I reply", "is this ok", "rewrite this", or vents about someone and wants to answer them. Checks the facts on both sides and tells the user which side the evidence supports, then drafts a reply of 250 characters or less that leads with the answer, can't read as sarcastic, defensive or needy, and ends with one concrete ask when someone has to act, followed by a Learning section. Applies on top of plain-writing and inside other skills that draft replies (triage, review-pr, jira-workflow). PR descriptions use create-pr instead.
---

# Reply with standing

The goal of every reply is that the reader takes the user seriously: as a peer whose point needs an answer, not someone they can skip, talk over or treat as junior. Two failure modes lose that standing, and they look opposite:

- Too sharp: sarcasm, passive aggression, terse one-liners to hard questions, reading motives out loud. These hand the other person the role of "the reasonable one" and give everyone else a reason to route around the user.
- Too soft: open-ended asks ("whenever you have time"), apologies before the ask, "feel free to ignore", "or I can drop it", vague closers ("add it to our radar"). These tell the reader the message can wait forever.

A good reply is calm, specific, direct and short: 250 characters or less, written to a peer who already knows their own area.

## Who the user is becoming

Every reply should move the user toward this reputation: the senior engineer and technical leader who brings the plan, knows the business and the product, leads technical teams, handles the unknown calmly, and looks ahead. People should see him as up to date and disruptive in a useful way, someone to follow and admire. He must never come across as condescending, and never as invisible (a wallflower who only answers when asked).

Turn that into concrete moves in the message:

- **Product and business first.** When the reply touches business topics (revenue, customers, ROI, priorities, trade-offs), load the `business-first-pitch` skill for the framing: lead with what changes for customers, orders or revenue, and keep the technical metric as the evidence behind it. Use the `product-lens` skill when a message touches a product decision.
- **Bring the plan.** When raising a problem, include the proposed next step and, if there's a real choice, two options with a recommendation and who decides: "I recommend A because X. B is faster but leaves Y open. I can start A on Monday." Don't hand over a problem without a direction.
- **The right question at the right time.** Ask before work starts (goal, success criteria, owner, deadline), at decision points, and when an assumption is about to become expensive. One well-formed question with its context, aimed at what blocks the decision. Skip questions whose answer the user could find in the code or the ticket.
- **Ownership.** First person, active: "I found", "I decided", "I'll ship it Thursday". Tools are never credited. The message still says what he did and what happens next.
- **Point to resources, not people.** When something was fixed, decided, confirmed or broken, cite the PR, ticket, release, feature or Slack thread that shows it ("fixed in traceability-service#2291", "confirmed in the #metrc thread [link]"), not who did it or who missed it. No "X's fix", "Y confirmed", "Z broke it". Name a person only when the message speaks to them directly: a question, an ask or an @mention.
- **Lead in the thread.** Summarize decisions after a discussion, name owners and dates, unblock others, close loops. Whoever writes the summary is seen as the one running the work.
- **Handle the unknown out loud.** Say what's known, what isn't, how he'll find out and when: "I don't know yet whether OK follows the federal rule. I'll confirm with the PM today and update the ticket by EOD."
- **Look ahead with specifics.** When he brings something new (an improvement, a feature, AI tooling, modernization, a better architecture), anchor it to a current problem, the business outcome it should move, a number and a small first step, not to hype. The message should show we're delivering the right thing with the right business outcome.
- **Not condescending.** Don't explain what the reader already knows: how their own product area works, a feature they use every day, their job, or what was said earlier in the thread. Answer what they asked and stop. Ask before correcting, never "obviously", "as I said", "simply", or orders to peers.
- **Not invisible.** Speak early in threads, state an opinion as a recommendation ("I recommend", "I'd go with") instead of "maybe we could", and share wins with their impact.
- **Think like a staff or principal engineer.** Hold a strong opinion and let the evidence set it (see "Technical proposals and design pushback" in step 2). Aim for what is best for the project, the product and the business. Who proposed something, how senior they are and how sure they sound don't count as evidence.

## 1. Read before drafting

- Read the whole thread, not only the message being answered (Slack MCP `slack_read_thread`, `gh pr view --comments`, Atlassian MCP for Jira). Note who said what, in order, and what is still unanswered.
- Work out what the user's message is actually about before judging their wording. A short line that looks like criticism of someone's work may be about a flag, an edge case or an earlier message. If you can't tell, ask the user one question instead of inventing a critique.
- Only quote or cite what you have actually read in full. If a tool returned headers or previews, say so and read the real content before relying on it.
- Write down, for yourself: what the other person said, what the user wants to happen next (a decision, a fix, credit, a review, scope), and who else is reading.

## 2. Check the facts before drafting

Do this for every reply, before the first draft and not only after someone pushes back. It covers every fact the reply states and every position it takes, including when the user asks you to argue for one side ("we want to win this"). A reply that wins on wording and loses on facts costs more standing than agreeing early, because the other person corrects it in public.

1. Check every claim on both sides, the user's, the other person's and any you were about to add, with the "Facts and evidence" rule in `~/.agents/AGENTS.md` and the `prod-evidence` skill (which queries to run, which sources to use, how to report the numbers).
2. **Tell the user the verdict before drafting:** which side the evidence supports, the one or two numbers that decide it, and the weakest point in the user's position. When the evidence favors the other person, recommend agreeing and draft that reply: acknowledge them in the first sentence and say what changes. Draft the user's side only if they still want it after hearing this, and put the weak point in "check before sending".

3. Claims about people are facts too. Say who owns or knows an area only with evidence (the repo's CODEOWNERS, git history, the team's page). A reviewer's comment doesn't change a ticket's acceptance criteria; only the user or the ticket's owner does.

Keep the research proportional: one or two queries per decisive claim. Stop once a claim is settled.

### Technical proposals and design pushback

When the thread is about how to build or fix something (a GitHub comment, a Slack thread, an email), settle the proposal on facts before taking a side. The same check applies to the other person's proposal, to the user's own and to code the agent wrote. A pattern that already exists in the codebase only shows that someone used it before, so judge it on the same evidence.

- Collect the evidence that supports or refutes the proposal: metrics and query counts, an `EXPLAIN` plan, a reproduction or a failing test, the incident or Sentry history, and what the pattern costs elsewhere (check it against the anti-pattern catalog at `~/.agents/skills/backend-design/skills/anti-patterns/README.md`).
- Name at least two alternatives, including doing less, and why each loses. For a concurrency fix that means the other guards too: a unique constraint, an idempotency key, a conditional update, a retry with backoff, or a change to the code path that removes the race.
- When a reviewer asks for a design defense ("why a lock instead of another guard, a retry or rethinking the path?"), answer with the decision and the one deciding fact. If the defense holds, write it in full where it can be read later (the PR description through `create-pr`, or the ticket) and link it. If no defense survives the check, say so in the first sentence and propose the alternative the evidence favors.
- When the evidence shows the other person is right, say so plainly in the first sentence, even when the code is the user's or the agent's own.

## 3. Separate the feeling from the message

The user may be frustrated, and the frustration may be justified. The reply still has to work on the reader. So:

- Acknowledge the frustration to the user in one line if they voiced it. Don't argue with their read of the other person, and don't confirm motives you can't see. If the thread doesn't support a claim (for example "he only thinks about himself"), say once, plainly, that you can't confirm it from the thread, and move on.
- Keep motives, sarcasm and resignation out of the reply. "I guess he can ask the agent to figure it out" or "I'll just do it myself then" reads as a jab even when it's true, and it lets the reader dismiss the point.
- Facts on the record beat a sharp line. A calm, specific reply that goes unanswered is evidence the user raised the issue. A sarcastic one is evidence against them.

## 4. Shape of the reply

Hard limit: 250 characters, URLs not counted. Count with `printf %s "<reply>" | wc -m` before handing it back. The only exception is a PR description, which follows `create-pr`. If the reply doesn't fit, it's answering more than was asked: keep the answer and drop the rest.

In one message, in this order:

1. The answer, in the first words ("Confirmed, there's no mass import today.").
2. The reason or evidence, only when the reader doesn't already have it: the edge case, the number, the past incident, a link.
3. One concrete ask by default: a yes/no, a choice, an owner, a date. Decide each time whether it's needed:
   - Ask when someone has to decide, act or give information before the work moves on, when you raise a problem or a proposal, or when the thread would otherwise stall with no owner.
   - Skip it when the answer closes the question and the reader has nothing left to do (a factual answer, a status update, closing a loop), or when the answer already tells them what to do next ("The brand can add them under Customers.").

Cut, every time:

- Openers and filler: "Thanks for raising this", "Good question", "Hi team", restating the question.
- Anything the reader already knows: how the feature they asked about works, background from earlier in the thread, their own process. Write to the reader as an expert in their area.
- Hedging and extras nobody asked for: alternative workarounds they didn't ask about, offers of future work, "let me know".

### When the reader isn't technical or is skimming

Support, CS, account managers, sales and leadership read threads between other tasks. They look at the first line, decide whether they got their answer, and move on. Write the first message for that glance and add detail only when they ask for it.

- About 150 characters, two lines at most: the answer and what to do or tell the customer now. If they have to read it twice, it's too long.
- Answer the next obvious question in the same line, because a short reply that leaves it open costs another round trip. For a lost order or record: can it be restored, who did it, what to tell the customer. For a bug: who is affected and when it's fixed.
- Leave out tables, timestamps with time zones, UI labels in bold, step-by-step reconstructions and links to tools the reader can't open (Datadog, Sentry, the admin). Keep them in your notes for the user, ready for a follow-up (see "What to hand back").
- Supporting material the reader needs to act (the item list to recreate an order, a file) goes in a short follow-up message or an attachment after the answer, or as an offer ("I can send the item list."). It doesn't go inside the answer.
- Each follow-up answers the new question directly in one line. Don't point back to an earlier message ("see the details above") and don't close with "Is there something else I can help you with?", which reads as a brush-off.

### One message per reader

Keep it to one message per reader. Several short replies in a row (question, warning, "needs tweaking", edit) read as nagging and are easy to skip. Edit the earlier message or post one consolidated reply.

Don't mix readers in one message. A question for someone outside the conversation (a PM, the feature owner, another team) never goes at the end of an answer to the person who asked, because the asker reads the thread as still open and comes back with "any update?". Ask that person in a DM, and if their answer changes what the asker should do, post the outcome in the thread as one line.

## 5. Rules by situation

**Asking for review, approval or a decision**
- Ask for a decision, not for time: "I need a yes, no or not now on X by Thursday, Nov 6."
- Name one person who decides. A channel-wide or multi-tag ask spreads responsibility until nobody owns it.
- Say what to read and how long it takes: a one-page summary or the two PRs that matter, and which one first.
- Make "no" and "not me" acceptable answers ("If you aren't the right person, who is?"). It makes replying cheap.
- Don't open with apologies, unrelated bad news, or permission to ignore it. Put risk controls (cost cap, scope limit, compliance gate) in the body as facts, not as apologies.

**Answering a hard question or criticism**
- Never reply with only the conclusion ("Yes. That's covered in the docs.", "That's the default link color."). Give the answer and the reason, in that order.
- If the critic is right, say so in the first sentence and say what changes. It costs little and earns credibility for the next disagreement.
- If they're wrong, show the evidence and stop. No "as I said before", no "haven't we explained this already".

**Pushing back on someone's work or announcement**
- Raise it early and once, with evidence: the case that breaks, the repro, the past incident, and a proposed fix.
- If the work was just announced, consider a DM first, then a public summary if it isn't addressed.
- Make the critique about the change, never the person: "This flag hides stores for multi-store carts" beats "this needs tweaking".

**Credit and ideas**
- Put ideas in a ticket or a thread before meetings so authorship has a timestamp.
- When someone builds on the user's idea without credit, reply neutrally and link the earlier message: "Glad this is moving. It builds on the backfill I proposed above [link]. Happy to help implement." No accusation, no sarcasm.

**Customer feedback or a support escalation**
- The person who brought it needs to know what to do next, not why the company made its choice. Answer what to tell the customer now, plus what we need from them or who does what when that fits in the 250 characters.
- Turn the complaint into product input in a ticket, not in the reply: what the customer uses, what the replacement is missing, where that goes (ticket, owner), and what condition must be met before anything changes for them.
- Take the engineering part yourself ("I'll compare X with Y and add the gaps to the ticket by Thursday") so the plan has your name on it.
- Don't defend the strategy or lecture ("the company is modernizing, as you may know"). The strategy is not what was asked.
- The support person relays your words to the customer, so write the first line so they could forward it as is. Evidence (session replays, timestamps, logs) stays with the user until the customer disputes the answer, and then the follow-up gives the one fact that settles it.
- If you want product to confirm whether the behavior is intended, ask the owner in a DM, not in the support thread (see "One message per reader").

**Closing loosely**
- Replace "add it to our radar", "something to think about", "just my 2 cents" with a concrete action: a ticket, an owner, a date. "No rush" is fine next to a concrete ask, not instead of one.

**Reviving a cold thread or unanswered DM**
- Wait 3 to 5 business days before the first bump (longer for execs and fractional roles).
- Bump with new value, not "any update?": a result, a number, a prototype, or a narrower question.
- Narrow the ask each time: decision, then a 15-minute call, then "who should I ask instead?"
- Tag one person.
- After two bumps, close the loop yourself: "I'll park this until [date]. Ping me if priorities change." Then take it to the next route (manager, sponsor, 1:1) instead of a third bump in the same place.

**Being ignored or rejected repeatedly**
- Don't escalate inside the thread. Move it to a DM or a 1:1 with the person who decides, with links to the threads as the record.

**Masked disrespect, being used or talked over**

Answer the behavior with a calm fact and a question or a term, never with a jab or silence. The goal is that the other person has to engage with the substance, in writing.

- Dismissed without a reason ("that opens a can of worms"): "What's the specific risk you see? If it's X, I can cover it with Y." Make them name it.
- Idea repeated as someone else's: link the original neutrally (see Credit and ideas) and claim a role in what happens next.
- Work dropped on him, a last-minute ask, or "just stamp this": set terms instead of absorbing it. "I can review it by Thursday. If it's needed sooner, which of A or B should I pause?" / "I'll review it properly. What's the context on the change to X?"
- Scope or ownership taken without a word: ask the decider in writing, once, without accusation: "I noticed X moved to [name]. Is that the plan going forward? I'd like to keep owning Y; what do you need from me for that?"
- Talked over or interrupted (in a thread or a meeting): restate the point once, shorter, with the ask: "To close my earlier point: X breaks for multi-store carts. Can we add that case before shipping?"
- Condescension ("as you may not know..."): don't mirror it and don't over-explain. Answer the substance at peer level and move to the next step.
- Never apologize for asking, for having an opinion, or for following up.

## 6. Check the draft (yours or the user's)

Flag and fix any of these before handing it back:

- Sarcasm, irony, "I guess", "just", "obviously", "as I said", "clearly", scare quotes, rhetorical questions aimed at the reader.
- Motive-reading or blame ("you ignored", "nobody cares about").
- A bare conclusion to a hard question, with no reason.
- Several fragments that should be one message.
- A table, timestamp, bold UI label or link to an internal tool in a first reply to a non-technical reader.
- A question or @mention for someone other than the asker inside the answer. Move it to a DM.
- A follow-up that points back to an earlier message instead of answering, or ends with "Is there something else I can help you with?".
- Self-undercutting: apologies before the ask, "sorry to bother", "feel free to ignore", "no hard feelings", "or I'll drop it".
- A vague closer with no action.
- A problem with no proposed plan, or an opinion phrased as "maybe we could" instead of a recommendation.
- A technical trade-off described only in technical terms, or decided without telling the people who own the business call.
- A technical point with no business or user impact when the reader is product, business or leadership (latency, throughput, error rate or job count stated without what it means for customers, orders, revenue, support or team time).
- Missing ownership: credit to a tool, or passive voice hiding what the user did and what happens next.
- Profanity, venting, typos or grammar slips.
- Claims about numbers, dates, scope or what a tool checks that you haven't verified. List these for the user to check.
- An argument that rests on what the code supports, or on a single event, without the usage number behind it (active customers, orders, occurrences in the last 12 months). Run step 2 or drop the argument.
- Agreement or a defense with no evidence behind it: conceding because the other person is senior or confident, or holding the user's or the agent's own design because it follows an existing pattern. Run "Technical proposals and design pushback" first.
- Plain-writing issues, and a reply that doesn't sound like the author. Load the `plain-writing` skill, including its author's voice section.

If the user's draft is already good, say so and change only what makes it weaker. Don't rewrite for the sake of it.

## 7. What to hand back

- When the reply takes a position: the verdict from step 2 first, in two or three lines (which side the evidence supports, the deciding numbers with their source, and the weakest point in the user's position).
- The reply, ready to paste, in the language of the thread (the user may talk to you in Portuguese about an English thread). Put it inside a fenced code block, never in a `>` blockquote, because the user copies it from the terminal and the blockquote's side bar gets copied with the text. When the reply itself contains a ``` code block, use `~~~` for the outer fence.
- A "check before sending" list with every assumption you filled in (dates, deadlines, which PR matters more, what the doc covers). No placeholders in the reply itself unless the user can't avoid filling them; if a value is unknown, pick a sensible one and list it here.
- For a non-technical reader, "If they ask": two or three one-line follow-up replies, ready to paste, for the questions they're likely to ask next ("who deleted it?", "how did they download it then?"), each with the evidence behind it in a note for the user. This is the detail layer that stays out of the first message.
- When someone outside the thread needs to confirm something, the DM to them as a separate draft.
- Optional variants only when the choice is the user's to make (for example whether to offer to own the work).
- A "Learning" section, always, on every reply. See below.

### Learning section

The user wants to learn to talk this way without help, in writing and out loud. So every reply ends with a short lesson tied to this specific message. Write it in the language the user is talking to you in (usually Portuguese), and keep quoted phrases in the language of the thread.

Include, in 3 to 6 bullets or short sentences:

- What changed and why. When the user gave a draft, quote the exact phrase you changed or cut, show what replaced it, and say how the reader would have taken the original ("'I guess he can ask the agent' soa como ironia, e quem lê passa a ver você como o irritado da conversa"). With no draft, point at the one choice in the reply that does the most work.
- The principle behind it, named in a few words so it sticks (for example "pedir decisão, não tempo", "reconhecer antes de discordar", "fato no registro vale mais que frase afiada", "uma mensagem completa, não fragmentos").
- One reusable phrase or sentence frame the user can use again in other situations, including in meetings and 1:1s ("Faz sentido. Minha preocupação é X, porque Y. Podemos Z?").
- When it helps, how the same move works spoken: what to say first in a meeting, or how to stop after making the point instead of repeating it.
- When the message has a chance to build the reputation in "Who the user is becoming" (bringing the plan, a business angle, a well-timed question, leading the thread, holding ground), point it out so he learns to spot those moments himself.

Rules:

- Teach one or two things per reply, the ones this message actually shows. Don't restate the whole skill each time.
- Don't repeat a lesson already given earlier in the same conversation; pick the next most useful one, or say in one line that the same principle applies again.
- When the user's own draft was already good, say what they did right and why it works, so they keep doing it.
- Be direct and specific, never preachy. Talk about the effect on the reader, not about the user's character.

Never send, post or schedule the message yourself unless the user says to. If they do, read the channel topic first (Slack MCP rule) and confirm the exact text. Never send through the Slack connector: `slack_send_message` appends "Sent using @Claude", and the connector can't edit or delete the message afterward. Send it from Slack web in Chrome with the claude-in-chrome tools instead, where it goes out as the user with no footer:

1. Get the conversation id (`slack_search_users` gives the user id, and `slack_read_channel` with it shows the `D...` DM id) and the team id (the `T...` in any Slack bot address or channel link).
2. Open a new tab at `https://app.slack.com/client/<team id>/<conversation id>`. If Slack shows a sign-in page, stop and ask the user to sign in.
3. Click the composer (`find` "Message to <name>"), type the text, check it with `get_page_text` or a screenshot before pressing Enter.
4. Check that the message shows in the conversation without a footer, close the tab and give the user the message link.

If the browser can't do it (the tools aren't connected, Slack asks to sign in, the page doesn't respond), send it with the Slack MCP and tell the user it went through the connector, with the footer.

## Example

Thread: the user asked whether a local-only validation skill would work for a new engineer on Windows and in CI. The owner answered: "Not supported on Windows. Local only, not suitable for CI."

User's first draft (don't send): "I understand. I'm just trying to improve onboarding for a new engineer, but I guess he can ask the agent to figure this out."

Reply:

```
Got it. Then a new engineer on Windows can't run it and CI doesn't enforce it. Can we open a ticket to run the schema checks in CI? I can scope it.
```

Learning:

- "I guess he can ask the agent to figure this out" soa como ironia. Quem lê não discute o seu ponto, discute o seu tom, e o dono da skill sai como o razoável. A versão nova mantém a mesma preocupação sem a farpa.
- Princípio: fato no registro vale mais que frase afiada. Se ninguém responder à versão calma, ela fica como prova de que você levantou o problema.
- "Add to our radar" deixa a thread morrer. "Can we open a ticket? I can scope it." pede um sim ou não e ainda te dá o escopo.
- Frase para reusar: "Got it. Then X breaks for Y. Can we Z?" Funciona igual falando numa reunião: diga o impacto uma vez, faça a pergunta e pare de falar.
