# VALID user guide

## What VALID is

VALID answers questions about Cloud TPU using only the documentation for the TPU generation you mean, and shows you exactly how it got there.

Cloud TPU documentation differs by generation. A machine type, software version or number that is right for one generation can be wrong for another, and a general-purpose assistant will happily mix them. VALID fixes the generation first, from your question, before it searches anything, so content for other generations cannot slip into your answer. If the documentation for your generation does not say, VALID tells you so instead of guessing.

It is built for engineers, technical writers and reviewers who need a correct, checkable answer for TPU v5e, v5p, v6e (Trillium) or TPU7x (Ironwood). Every answer links to the documentation it came from, and every answer comes with a panel showing the reasoning.

## Getting started

You need two things from whoever invited you: a link and an access code.

1. Open the link. If it ends in `#code=…`, the access code is filled in for you and disappears from the address bar.
2. If it does not, type the code into the **Access code** box under the Ask button.
3. Type a question and press **Ask** (or Ctrl/Cmd+Enter).

The page has a question box, four clickable example questions, and a counter such as "49 of 50 demo questions left today (resets 00:00 UTC)". The 50 are shared by everyone using the demo. A question that only asks you to pick a generation, or that fails because the model is busy, is not counted.

Keep your link private. Anyone who has it can use up the day's questions. The **Help** button at the top right opens a short version of this guide at any time.

## Asking a question

Name the generation in your question and VALID takes it from there.

- **Name it directly:** v5e, v5p, v6e (or Trillium), TPU7x (or Ironwood).
- **Or name something only one generation has:** a machine type such as `ct5p-hightpu-4t` points to v5p, and `tpu7x-standard-4t` points to TPU7x.
- **Compare two:** name both, for example "Compare chips per host for v5p and TPU v6e". Each generation gets its own steps and sources.

If you name none, VALID does not guess. It asks "Which TPU generation do you mean?" and shows four buttons. Pick one and your question runs for that generation. A bare "v5" counts as none, because it could mean v5e or v5p.

Examples that work well:

- I'm on Ironwood. Which machine type do I use?
- How much HBM does v5e have per chip?
- Compare chips per host for v5p and TPU v6e

Questions are limited to 400 characters, and each one stands alone: VALID does not remember your previous question.

## Reading an answer

An answer card has five parts, top to bottom.

- **Badges.** A green "Answered" badge, and a "Checked" badge such as "2/2 citations in scope, 5/5 values grounded". Those numbers come from automatic checks described under *The reasoning panel*.
- **Scope.** The generation(s) the answer is about, for example TPU v5p and TPU v6e (Trillium).
- **Lead sentence.** The short answer in one line.
- **Steps.** One entry per generation, each with the statement, a command in a grey box when there is one, and a **Source** link. The link opens the exact line of the documentation file the statement came from.
- **Not documented.** A yellow-edged note appears when the documentation answers for some generations but not others, or leaves part of your question open. Treat it as part of the answer.

The last line, "Content for … was excluded on purpose", names the generations VALID left out. That is the version-awareness at work: their documentation was never searched for this question.

## When VALID declines

A decline means the documentation for your generation does not support an answer, and VALID would rather say so than guess. The card is headed "Declined, by design" and says what is missing.

It happens in three ways, all visible in the reasoning panel:

1. **Nothing close.** The search found no passage near enough to your question: "No content for this scope is close enough to the question."
2. **The passages do not contain it.** The model read the retrieved passages and judged they do not answer the question. Asking "On v5e, what is the capital of France?" ends here.
3. **The draft failed its checks.** A drafted answer contained a value the cited passage does not support, and two rewrites did not fix it. Nothing is sent.

What to do next: check the Scope badge is the generation you meant; reword using the documentation's own terms (machine type, slice shape, chips per VM); or ask about the generation you suspect has the fact. If the fact should be documented and is not, the decline is useful evidence for the documentation owners.

## The reasoning panel

Under every result, "How VALID got here" lists each step in order, with its time. It is how you check an answer instead of trusting it.

1. **Decide the scope.** Which generation(s) VALID fixed and which words in your question triggered it. Plain matching against the documentation's own list of generations; no AI model decides this.
2. **Search inside the scope.** The filter applied before any search (`in_v5e == true`, for example), the best distance found, and the table of passages retrieved.
3. **Gemini call.** Which model drafted the answer, whether it judged the question answerable, and which models were tried first. "Skipped: failed a moment ago" means a busy model is resting for a few minutes.
4. **Check the answer.** Plain code, not the model, confirms that every cited passage is in scope and that every command, flag, number and identifier in the answer appears in the passage it cites.

The footer gives total time, the model that answered, the number of calls, tokens used, and the cost, which is $0 on the free tier.

The retrieved-passages table reads like this:

| Column | Meaning |
| --- | --- |
| Chunk | The passage, named by documentation topic and section. |
| Meaning rank (distance) | Rank by closeness in meaning. Lower distance is closer; VALID declines when even the best is above 0.40. |
| Keyword rank | Rank by matching words. A dash means the passage had no keyword match. |
| Fused | The two rankings combined. The highest-scoring passages go to the model. |

## Tips for good questions

Be specific about the generation and the thing you want.

**Do**

- Name the generation: "On v6e, …".
- Use the documentation's terms: machine type, slice shape, chips per VM, HBM per chip.
- Ask for one fact, one procedure, or one comparison.

**Avoid**

- General knowledge questions. VALID answers only from the TPU documentation.
- Assuming "per VM" and "per host" mean the same. VALID treats them as different unless the documentation says otherwise.
- A bare "v5", which could be v5e or v5p.
- Generations outside the four covered, such as earlier TPU versions.

## Limits to know about

VALID is a concept demonstration built on free-tier services, and it is honest about what that means.

- **Speed varies.** When the answering model is quiet, replies take 2 to 3 seconds. When it is busy, 10 to 35 seconds, and VALID may fall back to an older model (shown in the panel).
- **50 questions a day**, shared by everyone, resetting at 00:00 UTC.
- **Coverage is bounded.** VALID knows a small, curated documentation set covering four generations. Absence from it does not mean a fact is untrue, only that VALID cannot cite it.
- **No conversation.** Each question is independent.
- **The checks have a known limit.** They verify values, commands and identifiers against the cited passage. They cannot detect a wrong plain-language sentence in the documentation itself. For anything important, follow the Source link.

## Troubleshooting

| What you see | What it means | What to do |
| --- | --- | --- |
| Model busy | Every answering model was overloaded or too slow. Nothing was answered, and the question was not counted. | Press **Try again**, or wait a minute. |
| Access code missing or wrong. | The code box is empty or incorrect. | Re-enter the code, or reopen your invitation link. |
| Too many wrong access codes from this address | Eight wrong codes in 15 minutes. | Wait 15 minutes, then use the correct code. |
| Today's question limit for this demo has been reached | The 50 shared questions are used. | Come back after 00:00 UTC. |
| Please keep the question under 400 characters | The question is too long. | Shorten it to one fact or one task. |
| Could not reach the server | A network problem, or the service is starting up. | Wait a few seconds and ask again. |
| An answer looks wrong | The scope may differ from what you meant, or the source says something different. | Check the Scope badge, open the Source link, and read the reasoning panel. If it is still wrong, report the question with the panel's details. |

## Glossary

| Term | Meaning |
| --- | --- |
| Generation | A TPU hardware generation: v5e, v5p, v6e (Trillium), TPU7x (Ironwood). |
| Scope | The generation(s) an answer is allowed to draw on, fixed before any search. |
| Chunk | A passage of documentation, such as one table row or one step, with the generations it applies to. |
| Source | The documentation file and line a statement came from. |
| Grounded | A value, command or identifier that appears in the passage the answer cites. |
| Decline | A designed outcome where VALID says the documentation does not answer, instead of guessing. |
| Fallback model | An older answering model used when the preferred one is busy. It rests for five minutes after a failure (a "cooldown"). |
