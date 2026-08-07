---
name: ebook-writer
description: "Use this skill whenever the user wants to write, draft, plan, or outline an ebook, e-book, digital book, guide, or short non-fiction book — including Portuguese requests like 'escrever um ebook', 'criar um e-book', 'montar um livro digital', or 'quero lançar um infoproduto em formato de livro'. Trigger even when the user only describes a topic and says they want to turn it into a book, guide, or downloadable PDF/Word product, without using the word 'ebook' explicitly. This skill guides the full pipeline: defining topic/audience, researching and fact-checking real, verifiable content, building a length-correct outline (default 30-35 pages, ~8,000-10,000 words), writing chapters using storytelling and engagement techniques that keep readers turning pages, checking readability, and handing off to the docx or pdf skill for final formatted delivery. Do not use this skill for short single-page content like blog posts, emails, or social media copy — use it for book-length, multi-chapter deliverables."
---

# Ebook Writer

Write ebooks that people actually finish: engaging enough to keep reading, but built on real, checked facts rather than invented statistics or plausible-sounding filler. Those two goals pull in opposite directions if you're not careful — pure engagement drifts toward hype and exaggeration, pure accuracy drifts toward dry and dense. This skill exists to hold both at once.

The default target is **30-35 pages** (~250-300 words/page, so **~8,000-10,000 words** of body content, excluding cover/TOC). Treat this as a real constraint to design toward, not a rough guess to hit by accident — see Stage 3 for the math.

Work through the stages below roughly in order. Don't skip Stage 1 (definition) or Stage 2 (research) even if the user is eager to start writing — an ebook built on a fuzzy topic or unverified claims will need a full rewrite later, which costs the user far more time than answering a few questions up front.

## Stage 1: Define the book with the user

Before writing anything, get clear on:

1. **Topic and angle** — what specifically is this book about? A book on "produtividade" is unwriteable; a book on "como profissionais autônomos brasileiros organizam a rotina sem perder clientes" has a spine.
2. **Audience** — who reads this, and what do they already know? This determines vocabulary, examples, and what needs explaining vs. what can be assumed.
3. **Goal** — is this a lead magnet, a paid infoproduct, a portfolio piece, personal knowledge-sharing? The goal shapes tone (a sales-funnel lead magnet leans more persuasive; a reference guide leans more neutral) and whether a call-to-action belongs at the end.
4. **Language and tone** — confirm the output language explicitly (the user may write to you in one language but want the book in another — this happens often with Portuguese-speaking users producing content for Brazilian or Portuguese audiences). Confirm formality (você vs. tu, formal vs. conversational).
5. **What the user already knows** — ask if they have existing material (notes, transcripts, a course, prior drafts, personal expertise) to draw from. Real expertise the user already has is often the most trustworthy source available — better than a fresh web search — so always ask before assuming research starts from zero.

Don't turn this into a rigid questionnaire — if the user's initial request already answers most of these, just confirm and move on. Only dig deeper where there's a real gap.

## Stage 2: Research and fact-check

This is what separates a trustworthy book from generic AI filler, so don't shortcut it. Read `references/research-and-factchecking.md` before this stage — it covers how to source claims, when to hedge vs. state plainly, and how to handle numbers/statistics (the single biggest source of embarrassing errors in AI-written non-fiction).

The short version: every non-obvious factual claim, statistic, or named study needs a real source you actually checked (web search, or material the user provided) — never state a number or claim from memory as if verified. If you can't verify something and it isn't essential, cut it or reframe it as the author's opinion/experience rather than fact. Flag anything you couldn't verify to the user before finalizing, rather than quietly dropping it.

## Stage 3: Build the outline, and validate the length budget

A 30-35 page book needs a spine before it needs prose. Propose:

- **Title** (and working subtitle if useful)
- **8-12 chapters**, each with a one-line description of its core idea and the reader's takeaway
- **Introduction** that hooks the reader in the first few sentences (see `references/engagement-techniques.md`) and sets expectations for what the book delivers
- **Conclusion**, and — only if the goal calls for it (Stage 1) — a closing call-to-action

**Do the length math out loud before writing, and share it with the user:**

```
Target: 30-35 pages x ~275 words/page ≈ 8,250-9,625 words of body content
Minus: intro (~400-600 words) + conclusion (~400-600 words)
Leaves: ~7,000-8,500 words across chapters
÷ 10 chapters ≈ 700-850 words per chapter
```

Adjust chapter count to keep per-chapter length in a range that can actually develop one idea well — roughly 600-1,000 words. Too few chapters (e.g., 5) forces bloated, unfocused chapters; too many (e.g., 20) forces shallow ones. If the topic naturally needs more or fewer chapters than the math suggests, flag the tension to the user rather than forcing an awkward fit.

Show the outline to the user before drafting full chapters. This is the cheapest point to catch "that's not what I meant" — much cheaper than after 8,000 words are written.

## Stage 4: Write chapter by chapter

Read `references/engagement-techniques.md` and `references/structure-and-pacing.md` before drafting — they cover the specific techniques (hooks, story-driven openings, rhythm, analogies for complex ideas, plain-language rewrites) that make non-fiction hard to put down without resorting to clickbait or exaggeration.

Write one chapter at a time rather than the whole book in one pass — it's easier for the user to redirect course after chapter 2 than after chapter 10 (same reasoning as validating the outline first). After drafting each chapter, briefly check word count against the per-chapter budget from Stage 3 and note if you're drifting significantly over or under.

Within each chapter, keep sentences short and concrete, prefer plain words over jargon, and when a technical or abstract concept is unavoidable, explain it with a concrete analogy or example before moving on — a reader who has to stop and re-read a sentence is a reader who closes the book.

## Stage 5: Review pass

Before formatting, re-read the full manuscript (not just the latest chapter) and check for:

- **Factual accuracy** — does every claim still trace back to something verified in Stage 2? Cut or hedge anything that snuck in unverified.
- **Consistency** — repeated terms, contradictions between chapters, examples that don't match earlier claims.
- **Readability** — any paragraph that's a wall of text, any sentence that needs two reads to parse, any unexplained jargon.
- **Engagement** — does each chapter open with something that pulls the reader in, or does it start with throat-clearing ("In this chapter, we will discuss...")? Cut throat-clearing.
- **Length** — total word count against the Stage 3 budget. If it's drifted far outside 8,000-10,000 words, trim or expand rather than leaving it as-is — the user asked for 30-35 pages for a reason (often a platform or print constraint).

## Stage 6: Deliver the formatted file

This skill produces the manuscript; it does not itself lay out documents. Once the manuscript is reviewed and approved by the user, hand off to whichever skill matches the requested output format:

- **Word document (.docx)** → use the `docx` skill in this repository
- **PDF** → use the `pdf` skill in this repository (or produce the `.docx` first via the `docx` skill, then convert)

Give the formatting skill a clear structure to work with: title page, table of contents, one heading per chapter (so a TOC can be generated), and consistent heading levels. After the file is generated, page count depends on real formatting (font size, margins, images) — if the rendered page count lands meaningfully outside 30-35 pages, adjust margins/font/line-spacing first, and only trim or expand the manuscript itself if a formatting adjustment isn't enough.
