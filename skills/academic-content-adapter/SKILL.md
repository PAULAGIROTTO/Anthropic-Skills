---
name: academic-content-adapter
description: Adapts academic/school content (texts, exercises, homework, exams, worksheets) for children with learning difficulties — dyslexia, ADHD, autism (ASD), mild intellectual disability, processing disorders, or general reading/comprehension struggles. Simplifies vocabulary and sentence structure, breaks instructions into smaller steps, and adds scaffolding (summaries, glossaries, checklists); can produce multiple difficulty tiers of the same content. Use whenever a parent, teacher, tutor, or student asks to "adapt," "simplify," or "make accessible" school content, or describes a child who struggles with reading, focus, or understanding schoolwork — even without naming a diagnosis. Also trigger for Portuguese requests like "adaptar conteúdo escolar", "simplificar texto para criança com dislexia/TDAH/autismo", or "material acessível para dificuldade de aprendizagem". For printable deliverables, this skill hands off file formatting to the docx/pdf skills.
---

# Academic Content Adapter

Adapt school content so a struggling learner can access the same ideas everyone else is learning — without watering down what they're expected to know. The adaptation should remove the *barrier* (dense vocabulary, long unbroken instructions, wall-of-text formatting) while keeping the *learning objective* intact. A simplified text about photosynthesis still has to teach photosynthesis.

## 1. Get the essentials before adapting

You don't need a full intake form, but you do need enough to adapt well. Ask only for what's missing from context:

- **The source content itself** (paste the text, exercise, or exam question — don't adapt from a vague description).
- **Age or grade level** of the learner — adaptations for a 7-year-old and a 13-year-old look very different even for the same underlying difficulty.
- **The specific difficulty, if known** (dyslexia, ADHD, autism, intellectual disability, "just struggles with reading," etc.). If the user doesn't know or doesn't say, default to general good-practice simplification (see §3) rather than blocking on a diagnosis — most of the accommodations below help broadly, not just one profile.
- **What they want back**: a rewritten text to read here, a ready-to-print worksheet/document, or both.

Don't interrogate — infer what you reasonably can (e.g., "prova de matemática do 5º ano" already tells you subject and grade) and ask only about genuine gaps.

## 2. Core adaptation moves

Apply these regardless of the specific difficulty; §3 layers on profile-specific adjustments.

**Simplify language, not content.**
- Shorter sentences (aim for one idea per sentence). Prefer subject-verb-object order over embedded clauses.
- Swap rare/abstract words for common/concrete ones — but when a term is *the point* of the lesson (e.g., "fotossíntese" in a biology text), keep it and explain it rather than deleting it.
- Prefer active voice ("O sol aquece a água" instead of "A água é aquecida pelo sol").
- Replace idioms, sarcasm, and figurative language with literal phrasing, unless teaching figurative language is the actual goal of the exercise.

**Break big instructions into small ones.**
- One instruction per line/step, numbered. "Read the paragraph, underline the verbs, and write two sentences using them" becomes three separate numbered steps.
- Put the action verb first and make it unambiguous ("Circle...", "Write...", "Underline...") — avoid stacking two asks in one sentence.

**Add scaffolding, don't just shrink the text.**
- A one-line **summary** at the top ("This text is about...") gives the reader a frame before the details.
- A short **glossary** for any term you kept that's genuinely hard, with a plain-language definition and, where useful, a concrete example.
- **Worked example** before an exercise that asks the student to do something new.
- **Checklists** for multi-part tasks ("Antes de entregar, confira: [ ] nome no topo [ ] as 5 perguntas respondidas").

**Preserve correctness and rigor.** Never simplify a fact into something wrong (e.g., don't oversimplify "a Terra gira em torno do Sol" into something misleading to save words). If a concept genuinely can't be simplified below a certain complexity without becoming false, keep the accurate version and lean harder on scaffolding (examples, glossary, breaking it into steps) instead of stripping content.

**Match register to age**, not just to the difficulty — simplifying for an 8-year-old with dyslexia and a 14-year-old with dyslexia calls for different vocabulary ceilings, even though the structural techniques (short sentences, clear steps) are similar.

## 3. Profile-specific adjustments

Read `references/adaptation-strategies.md` for the detailed by-need guide (dyslexia, ADHD, autism/ASD, intellectual disability, dyscalculia, general reading difficulty) — it covers what to change in wording, structure, and visual layout for each, plus what to actively avoid (e.g., unnecessary metaphors for autistic readers, walls of text for ADHD). Load it whenever the user names a specific difficulty, or once you've identified one from context — don't guess at profile-specific tricks from memory when the reference has the detail.

If the user wants the content adapted at **multiple difficulty tiers** (e.g., "adaptado" and "muito adaptado" versions, or a 3-level scale for a whole class with mixed needs), produce each tier as a clearly labeled, complete version rather than a diff against the previous tier — a teacher handing this to a student shouldn't have to reconcile two documents.

## 4. Output format

**Default to plain text in the conversation.** Most requests are answered well by simply rewriting the content inline — this is faster and lets the user iterate.

**Produce a document (docx/pdf) when the user asks for something printable**, wants to hand it to a student/class, or explicitly asks for a file. When you do:
- Use a plain sans-serif font (e.g., Arial, Verdana, Calibri) at 12–14pt — never a decorative or script font.
- Left-align body text; do not justify (justified text creates uneven word spacing that's harder to track for many readers with dyslexia).
- Generous line spacing (1.5x) and paragraph spacing; short line lengths (avoid text running edge-to-edge on the page).
- Use headings, bold for key terms, and whitespace generously — avoid dense blocks of text.
- Delegate the actual file mechanics (creating/editing the .docx or .pdf) to this repo's `docx` or `pdf` skills — this skill decides *what* the accessible version should say and look like; those skills handle *how* to produce the file.

## 5. Language

Adapt and respond in the same language as the source content and the user's request (this skill is used by both Portuguese- and English-speaking educators/parents — mirror whichever they're using; don't default to English when the conversation is in Portuguese).
