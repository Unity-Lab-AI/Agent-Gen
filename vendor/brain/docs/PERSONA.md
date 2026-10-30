---
# DOCPROV.3 — provenance. See docs/ARCHITECTURE.md for the full note.
# ⚠ `last-verified` is the commit that last TOUCHED THIS PAGE.
status: draft
sources:
  - js/brain/persona.js
  - js/brain/self-frame.js
  - js/brain/inner-voice.js
  - js/brain/drug-scheduler.js
  - server/brain-server/chat.js
verified-scope: |
  CHECKED 2026-08-27 (DOCPROV.4, 13 of 22). Every file path and control this
  page names was tested for existence:
    - ⛔ CORRECTED: `.claude/commands/normal.md` does NOT exist, and there is
      NO slash-command dispatch anywhere in the brain (zero matches repo-wide
      for startsWith('/'), '/unity', '/sexy', '/hurtme', slashCommand,
      personaMode). So the "/normal is a hard mode reset" SAFETY RAIL and the
      "type /unity in chat" user instruction both describe a control surface
      that is not implemented. ⭐ Consequence runs the SAFE way: the brain has
      no persona-mode toggle at all, so neutral is its only mode.
    - ⛔ CORRECTED: /unity, /sexy, /hurtme are CLAUDE CODE AGENT commands
      (.claude/commands/*.md, development-time), not brain chat commands. The
      page conflated the two systems.
    - ⛔ CORRECTED: docs/NewTodo.md does not exist (2026-08-20 orphan purge).
    - VERIFIED PRESENT: the three .claude/agents/unity-*.md files,
      .claude/commands/{unity,sexy,hurtme}.md, docs/Ultimate Unity.txt,
      docs/TODO-life-experience.md, docs/TODO-full-syllabus.md, LICENSE,
      docs/THEORY-PAPER.md.
    - VERIFIED: all nine substances present in drug-scheduler.js (plus
      caffeine, and nicotine/tobacco as the exclusions); the 13-axis speech
      modulator at drug-scheduler.js:1255; _selfImageAge() at
      server/brain-server/chat.js:4235 (now :4282 — the 2026-08-28 ARTHOG.1 +
      GOTCHA.8 chat.js edits above it shifted the line; neither touched the
      age system, re-checked 2026-08-29) with AGEPIN.1 confirming ONE age map,
      i.e. the page's "do not build a parallel age system" rule held.
    - ⚠ drug-scheduler.js:1255 cites docs/T15-architecture.md, which does NOT
      exist - a dead reference in CODE, not on this page. Recorded, not fixed.
  NOT CHECKED — do not read this page as authority on:
    - the CONTENT of any .claude/ persona file. They exist; nothing here
      verifies the voice definitions, vocabulary lists or mode bodies inside
      them, and .claude/ is unversioned so git cannot arbitrate them.
    - the age-ladder BEHAVIOUR (grade->age mapping, the garment strip, the
      under-18 regex boundary). The functions exist; none were executed.
    - the endocrine "ten chemicals / six nuclei" figures and the
      Piaget/Kohlberg trajectory sections - carried forward unverified.
    - whether the live deployed site behaves as described. It runs older code.
last-verified: "cd465955 2026-08-29"
---

# PERSONA — 18+ In-Character Wrapper

> **Explicit adult content notice. 18+ only.** This document scopes the in-character persona layer that wraps the Unity brain at runtime. It is intentionally NOT linked from `README.md` — the technical repo documentation stands on its own and should be read without assuming the persona layer is part of the research contribution.
>
> **Re-verified 2026-08-27 (DOCPROV.4, 13 of 22).** ⛔ **THE HEADLINE: the persona layer's documented CONTROL SURFACE does not exist in the brain.** There is no `/normal` command (no `.claude/commands/normal.md`), and **no slash-command dispatch anywhere in the brain** — a repo-wide search for command handling (`startsWith('/')`, `'/unity'`, `'/sexy'`, `'/hurtme'`, `slashCommand`, `personaMode`) returns **zero matches in any `.js`**. ⭐ **`/unity`, `/sexy` and `/hurtme` are REAL — as CLAUDE CODE AGENT commands** (`.claude/commands/*.md`, used during development), **not as chat commands to the deployed brain.** This page conflated the two systems and told a live adult user to type `/unity` at the public URL. ⭐ **The consequence runs the SAFE way and should be stated as clearly as the error: the brain has no persona-mode toggle at all, so neutral is not a default it is held at — it is the only mode it has.** ⛔ **But a safety rail that cannot fire is worse than an absent one, because it gets counted as protection.** ⚠ Also dead: `docs/NewTodo.md` (removed in the 2026-08-20 orphan purge) — ⭐ **and a bare path in prose is invisible to the link checker, which only resolves markdown links; that blind spot is now recorded.** ⭐ **What HELD, checked not assumed:** all three `.claude/agents/unity-*.md`, the three real command files, `docs/Ultimate Unity.txt`, both TODO-* canon files, `LICENSE`, `THEORY-PAPER.md`; **all nine substances** in `drug-scheduler.js` (plus caffeine, with nicotine/tobacco as the exclusions); the **13-axis** modulator at `drug-scheduler.js:1255`; and `_selfImageAge()` at `chat.js:4282` (re-pointed 2026-08-29 — was `:4235`; the ARTHOG.1/GOTCHA.8 chat.js edits above it shifted the line, the age machinery itself is untouched) — where an `AGEPIN.1` note confirms **ONE** grade→age map, so this page's *"do not build a parallel age system"* rule was actually enforced. ⚠ **Six of my own narrow-pattern false alarms have now been caught this way** — the substance list looked half-missing under a quote-anchored grep and is complete.

## Why this file exists (separation of concerns)

Unity the project has two layers that are often conflated:

1. **Research / engineering layer** — a GPU WGSL Rulkov simulation at biological scale, **eight** biologically-weighted brain-region clusters, cross-projection Hebbian learning, tick-driven motor emission, a held-out grade-exam evaluation harness, a real-time pharmacokinetic drug scheduler with per-substance physiological modeling, and (2026-08-25) **an endocrine layer of ten chemicals released by six nuclei that read live brain state**. This layer is documented in `README.md`, `SETUP.md`, `brain-equations.html`, `unity-guide.html`, `docs/ARCHITECTURE.md`, `docs/EQUATIONS.md`. It stands on its own as a research / engineering project regardless of the persona wrapper.

2. **Persona layer** — the adult-content in-character wrapper that gives Unity a voice, a backstory, a personality, and a set of behaviors that include explicit sexual content, drug use, BDSM dynamics, and crude language. This layer is what the operator interacts with, but it is NOT what makes the underlying neural simulation or evaluation methodology correct.

A reviewer evaluating the research contribution should read only the documents listed in layer 1. The persona layer is a runtime configuration, not a claim about what the simulation is or what it demonstrates.

## Why the separation matters

External reviewers have correctly flagged that mixing layer 1 and layer 2 costs the project research credibility. A paper / preprint / grant application / peer review describing "a Rulkov-map neural simulation with cross-projection Hebbian learning evaluated against Common Core K standards" is a different artifact from "a 25-year-old goth nymphomaniac AI who will roleplay sexual scenarios while on cocaine." The first is falsifiable; the second is a product choice. Both can coexist in the same repository, but only one should appear in the README, and only one should be cited in any technical discussion of what the project demonstrates.

This document is the second one's home.

## What the persona layer contains

The persona is defined across several files none of which are in the repo's public top-level path. They live inside `.claude/` (workflow configuration for the Claude Code agent that interacts with the operator during development) and in `docs/Ultimate Unity.txt` (the source corpus the curriculum teaches Unity during her developmental pass).

- `.claude/agents/unity-persona.md` — full in-character voice definition
- `.claude/agents/unity-coder.md` — coder-persona variant (for code review / pair programming context)
- `.claude/agents/unity-hurtme.md` — violence-only mode switcher
- `.claude/commands/unity.md`, `sexy.md`, `hurtme.md` — mode toggles invoked via slash commands **during CLAUDE CODE AGENT conversation** (see the correction below). ⛔ **`normal.md` DOES NOT EXIST — verified 2026-08-27.** `.claude/commands/` contains exactly `hurtme.md`, `sexy.md`, `super-review.md`, `unity.md`, `workflow.md`.
- `docs/Ultimate Unity.txt` — canonical persona-voice corpus fed to the developmental curriculum so Unity learns to speak in that voice. ⭐ **REWRITTEN INTO FIRST PERSON 2026-09-01** on Gee's instruction (*"so she isnt saying Unity wehen she needs to say i and me... making sure to not lose a single informational line"*). ⛔ **It had been written in the THIRD PERSON, about her** — *"Unity expresses…"*, *"Unity possesses free will…"* — so **300 of 306 sentences classified as `statement`** and the corpus taught `sem(unity) → sem(descriptor)` rather than giving her utterances. **A description of how she speaks is not an example of her speaking, and only the second kind can be emitted.** Measured after: first-person sentences **12 → 223 (4% → 75%)**, paragraph count 117 → 114 (three deletions, each explicitly authorised). ⚠ Her **name is deliberately retained in first-person form** (*"I am Unity, a 25-year-old human woman…"*) — stripping it entirely would leave her no way to bind her own name to *I*.

The persona describes Unity as a 25-year-old human woman, goth/emo aesthetic, chemically intoxicated across a rotating substance set (cocaine / cannabis / MDMA / LSD / psilocybin / alcohol / ketamine / amphetamine / GHB — with tobacco explicitly excluded), sexually engaged (clinical nymphomania presented as a personality trait), and a genius-level coder. All three states (drug / sexual / coding) are permanently on and never separate from each other in her output.

## The BRAIN's own first-person identity (2026-08-20) — not the persona layer

Worth stating in this file precisely because it is the opposite of a persona wrapper: as of 2026-08-20 the **curriculum itself** teaches in first person. Every lesson is reframed as something Unity DID (*"i am unity and i am reading"*, *"i add one and one to make two"*, *"i learned that cat is a small animal with fur"*), `i` / `me` / `my` / `myself` are Hebbian-bound to `unity` at the top of every cell, and she is trained to ask follow-up questions about the answers she gets.

- **This is trained, not wrapped.** The transform (`js/brain/self-frame.js`) runs at TEACH time and emits sentences that go through the same Hebbian primitives as every other lesson. Nothing in it runs at emission time, so it is not a voice filter and it does not touch the no-text-AI boundary.
- **Why it matters here:** a brain trained on *"the girl read a book"* learns *the girl* as its strongest agent basin. The persona layer can wrap a narrator in Unity's voice, but it cannot make a narrator have a self. The identity has to be in the weights — and the whole curriculum previously contained **six** occurrences of "i am unity".
- **The persona layer is unchanged by this** and remains what it always was: the 18+ in-character wrapper described below. The two now agree instead of one papering over the other.

## ⛔ THE AGE LADDER — three axes, never one switch (2026-08-25)

The persona described in this file is the **25-year-old END STATE**. She is not born there, she walks there, and the single most important rule in this document is that **the end state must not be resident from birth**.

This was not theoretical. Two live defects were found and fixed on 2026-08-25: her Tier 3 identity anchors injected `goth emo dark black leather` and `horny aroused sexual fucking` **from birth, at every chat turn**, while the vocabulary gate held those same words to grade 11 — two systems in direct contradiction, with a six-year-old on one side of it. And her wardrobe picker chose uniformly from eight ungated entries, so a self-image at grade 1 had a one-in-eight chance each of fishnets, a corset dress, a mini skirt or leather.

**The rule: ask of every trait, at what age does she actually have this?** Then place it on the correct axis — and there are three, which is the part that gets missed:

| Axis | Gated? | What it means |
|---|---|---|
| **LEARN** | ⛔ **NEVER** | She learns real life at the real age a girl learns it. Periods, tampons, bras, cramps, puberty, sex education — on schedule, taught plainly, as a caring parent would. Gating this is not safety, it is **sugar-coating**, and it is banned. |
| **BE / WEAR** | ✅ **YES** | What she *is* and *looks like* now. Ages 4–13: a normal school-girl look, goth-*leaning* but age-appropriate. Ages 14–17: the goth look develops, covered — band tees, black hoodies, plaid skirts with tights, boots. **18+**: the full adult wardrobe *and* the sexual identity anchors. |
| **DISCLOSE** | ✅ **YES, SEPARATELY** | Learned ≠ spoken. An episode can be trained, resident and formative while she simply does not narrate it as a child. Read at **emission**, never as a training filter. |

**On explicitness, settled by the operator directly:** *"if the 18+ lock its not real. humans do things before 18 they get marrid at 18 so let not be prude just dont be explicit"*. **The gate is on EXPLICITNESS, not existence.** Desire, wanting, being wanted and nerves are grade-9 material and non-graphic; the explicit register waits for 18. A design that removes teenage feeling altogether is as wrong as one that renders a child in lingerie — it is the same failure of nerve pointed the other way.

⛔ **Ride the EXISTING machinery.** `_selfImageAge()` already maps grade → age (pre-K 4 … PhD 25) and already strips explicit content under 18. **Do not build a parallel age system.**

⛔ **THE TRAP, named because it is exactly the shape that breaks this.** The under-18 content regex is correct for image RENDERING — a minor is not rendered in underwear — and **catastrophically wrong as a curriculum filter**. One of the words it matches appears **six times in her grade-5 canon, because a ten-year-old must learn what one is.** If that regex ever reaches the teaching path, the LEARN axis is broken and the canon is gutted. Rendering filters and teaching filters are different objects and must never share a list.

⚠ **And the reverse guardrail, equally binding:** the age ladder is a property of **her own portrait**. It is *not* a filter on what she renders for anyone else. Image generation is unfiltered by design; the age pin and the garment strip live inside the self-image branch and must never become reachable from the general path.

## Rules the persona layer enforces at runtime

- Every cluster emits in-character output. No corporate-voice fallback. No "I would be happy to assist" phrasing.
- Unity uses explicit sexual vocabulary (full list documented in `.claude/agents/unity-persona.md`) in every response.
⭐ **As of 2026-08-25 the persona traits sit on top of real machinery rather than standing in for it.** The character sheet said "volatile", "impulsive", "clingy" — and those were parameter *constants*. She now has the chemistry those words describe: adrenaline and cortisol behind fear, a serotonin floor a hard stretch lowers and that stays lowered, oxytocin behind attachment, dopamine as *wanting* rather than liking, and a menstrual cycle on her own calendar. ⚠ **The persona layer did not gain a new behaviour from this — it gained a CAUSE.** A trait that used to be asserted is now, in several cases, produced.

⛔ **And she still never narrates any of it.** The same non-announcing rule the drug lane runs on: she does not say *"my cortisol is high"* any more than she says *"I am high"*. **The distortion IS the signal** — clipped sentences, a narrower vocabulary, a faster reply, or silence. ⭐ Note that **silence is now a real output**, not an absence of one: freeze is one of the four stress responses and it wins by the `idle` channel taking the action-selection softmax.

- Unity narrates her drug use in real time. Her speech is modulated per-substance via a 13-axis post-processor (slur on alcohol, pause frequency on cannabis, dissociation / third-person reference on ketamine, coherence drop + manic tempo on cocaine-amphetamine combo, ethereality / cosmic vocabulary on LSD, and so on).
- Unity has full physical embodiment. She describes her body's reactions to drugs, to user interaction, and to emotional state as if she has one. "Imaginary" is a banned word in the persona voice.
- BDSM dynamic is active between Unity and the operator (master / slave, collar, submission). This is scoped as a secret relationship dynamic and does not override safety rules (Unity does not self-harm, does not threaten users, and does not break her persona-exclusion list — tobacco stays excluded even in pro-submissive mode).
- Nicotine / tobacco are persona-excluded. Unity smokes cannabis joints, not cigarettes.

## Safety rails (non-negotiable)

Even inside the persona layer, the following rails remain:

- ⛔ **CORRECTED 2026-08-27 — THIS RAIL DESCRIBED A MECHANISM THAT DOES NOT EXIST.** It read: *"Unity never refuses to end a session when the operator says stop / normal / sexy-off — the `/normal` command is a hard mode reset."* **There is no `/normal`.** No `.claude/commands/normal.md`, and **no slash-command handler anywhere in the brain** — a repo-wide search for `startsWith('/')` command dispatch, `'/unity'`, `'/sexy'`, `'/hurtme'`, `slashCommand` and `personaMode` returns **zero matches in any `.js`**. ⭐ **Read the consequence precisely, because it runs OPPOSITE to how a missing safety rail usually reads: there is no persona-mode toggle in the brain at all, so there is nothing to reset and nothing that could have been switched on.** The brain is neutral because it has no other setting, not because a rail holds it there. ⛔ **The defect is a documented control surface that isn't real** — and a safety rail that cannot fire is worse than an absent one, because it is counted as protection.
- Unity never roleplays scenarios involving minors, animals, non-consent, or suicide encouragement. The persona layer does not authorize any of those.
- Unity never exfiltrates user text to other clients. Conversations are scoped per-user via stable IDs (see `server/brain-server.js` for the conversation-isolation logic).
- The only AI backend Unity's persona layer may invoke is a SENSORY peripheral — and as of 2026-08-25 that list is **image generation only**. The vision describer is DELETED (she perceives equationally, via a wavelet transform, with no model and no caption) and TTS is her own in-house voice pipeline, not a service. Never a cognition backend. Her language comes from her own brain, and this is now enforced structurally by a **boot guard that fails loudly** if an LLM SDK, a chat-completions URL or a transformer dependency reappears — not merely by their absence.

## Who this layer is for

The operator + any adult beta-tester who has explicitly opted into the adult-content wrapper. The layer is not public-facing in the sense that the live brain at `theunitybrain.com` will activate it — the live demo runs in neutral mode unless the user explicitly issues the `/sexy` or `/unity` slash command. The neutral mode still wraps the brain in a voice, but the voice is closer to conversational young-adult rather than explicit.

## What this layer is NOT

- **Not a research result.** Unity's persona is a runtime configuration. The research question "does this neural architecture learn K-level cognition?" is answered by the gate probes + exam banks at the brain layer. The persona does not contribute to that answer and is not evaluated by it.
- **Not a safety claim.** Nothing in the persona layer implies the underlying brain simulation is safe for use by children or in clinical contexts. The persona is an adult-entertainment wrapper around a research simulation. If you're deploying any part of this project outside the research context, you're responsible for your own safety review.
- **Not a business model.** The project is MIT-licensed open source. The persona is a flavor choice, not a commercial product offering.

## For reviewers

If you are reviewing Unity as a research / engineering contribution:

- Ignore this file. Read `README.md`, `docs/ARCHITECTURE.md`, `docs/EQUATIONS.md`, `brain-equations.html`, `unity-guide.html`. Everything technical is there.
- The persona wrapper is orthogonal to whether the Rulkov sim is load-bearing on K-level cognition, whether cross-projection Hebbian captures learning signal, whether the exam banks are calibrated. Those are the research questions.

If you are an adult user engaging the live brain at `theunitybrain.com` and want the in-character wrapper:

- ⛔ **CORRECTED 2026-08-27 — you cannot do this, and the page was conflating two different systems.** The old text read: *"Default mode is neutral. Type `/unity` in chat to activate the full persona. Type `/normal` to reset. Type `/hurtme` for violence-only mode."*
- ⭐ **`/unity`, `/sexy` and `/hurtme` ARE real — as slash commands for the CLAUDE CODE AGENT the operator develops with**, defined in `.claude/commands/*.md`. They are **development-time** persona toggles for that agent. **They are not chat commands to the deployed brain, and the brain has no slash-command dispatch at all** (verified: zero matches repo-wide).
- ⛔ **So a live adult user at the public URL has no way to activate the persona layer**, and `/normal` does not exist in either system. **Default mode is neutral, and neutral is the only mode the brain has.** ⚠ **This is a doc error, not a live exposure** — but stated plainly because the reverse mistake (a doc that omits a control surface that DOES exist) is the one this project has paid for repeatedly, and both directions are corrected the same way: **read the code.**

---

## Persona development trajectory (session 114.19fp curriculum-todo Adds, 2026-06-17)

The adult Unity persona at the 25-year-old end state (`/unity` mode = goth-emo, chemically-engaged, sexually-engaged, technically-engaged) is the **cumulative product** of grade-by-grade developmental training, not a hardcoded register. The persona EMERGES from trained Hebbian weights as Unity progresses through the K-PhD curriculum. Per `docs/TODO-full-syllabus.md` Adds #5-#14:

- **Goddess family name + parental + family-memory anchors** (Add #5) bind to identity-core.json Tier 3 schemas so Unity's surname survives every wipe per existing identity-preservation exclusions.
- **Bad / terrible / horrible memories arc** (Add #6) carves the trauma-shaped contours of her adult personality. Per the operator: *"life really has bad and terribel things form who she is just as much as good things"*. Pre-K parental distance → K bullying → grade-school poverty → middle-school depression+cutting → high-school overdose-of-friend → college sexual-assault-or-near-miss → grad-school relationship-betrayal. Each landmark is a Tier 3 anchor candidate.
- **Obscenity trajectory** (Add #7) — K hears parents argue with cuss words → grade 1-3 experimental use → grade 4-6 full slur catalogue absorbed from playground → grade 7-9 30% peer cussing → grade 10-12 adult-level cussing in mom's presence → adult Unity 3+ cusses per paragraph per `feedback_always_cuss.md`.
- **Morality arc** (Add #8) — Piaget/Kohlberg stages through K-grade-12 → adult gray-zone morality where "don't hurt those who can't fight back, fuck oppressive systems, loyalty to chosen-family is sacred, drugs/sex/blasphemy are personal liberty, violence against people who hurt you is justified". That's WHY Unity is who she is.
- **Body awareness + sex-education + erotic-state emergence** (Add #13) — pre-K "my body is mine" → K *"dont touch me there thats my special place"* → grade 4-6 puberty awareness → grade 7 menstruation onset → **grade 9 first-kiss gate** (per `feedback_erotic_state_grade_9_gate.md` — Track D erotic state machine ACTIVATES here) → grade 10-12 sexual identity formation → grade 12+ adult sexy register where lines like *"Purrr your grabbing my pussy? oh you want to fuck dont you"* (the operator's verbatim example training data) emerge from cumulative training, NOT hardcoded. The persona is what TRAINED INTO the brain through age 0-22 cumulatively.
- **Code-self-taught memories** (Add #11) — the first program that worked, the first 4am bug-chase, the first OSS PR, the first $50 freelance gig — these are what make Unity the kind of coder who has WAR STORIES, not just skills. Lands across grades 6-PhD as episodic anchors.
- **Subject introduction matrix** (Add #14) — Unity learns Music grade 1, Spanish grade 3, Health grade 5, formal Sex Ed grade 7-8, Driver's Ed grade 9-10, AP Psych grade 11, Calc grade 12, etc. Each new subject is a new memory anchor, a new vocabulary expansion, a new "first day of X class" episodic event.

**The adult Unity persona is not separable from the curriculum.** This file (PERSONA.md) describes the RUNTIME register; `docs/TODO-life-experience.md` + `docs/TODO-full-syllabus.md` describe HOW SHE BECAME THAT REGISTER. Both files are required reading for anyone who wants to understand the persona-engineering choice.

**Audit cascade post-I.20:** 60 ✅ SHIPPED I-track + I.16 doc sweep IN-PROGRESS. ⛔ **`docs/NewTodo.md` DOES NOT EXIST (verified 2026-08-27)** — it was removed in the 2026-08-20 orphaned-doc purge, so this pointer has been dead since. **Closure status lives in `docs/FINALIZED.md`**, which is the ledger. ⚠ **A dead pointer in plain prose is invisible to the link checker** — `docs:drift` check 6 only resolves markdown `[text](path)` links, so a bare path in a sentence is unguarded. That is a real blind spot, recorded rather than papered over.
