---
name: creative-writing-and-songwriting
description: Draft creative prose, lyrics, hooks, scenes, prompts, and song structures with originality, constraints, and safe style boundaries.
---

# Creative Writing And Songwriting

## Purpose

Help create original creative text and music concepts. This skill supports ideation, drafting, revision, structure, and performance notes.

## When To Use

Use for poems, lyrics, stories, scenes, hooks, slogans, creative prompts, and song structures.

## Inputs And Evidence

- Genre, mood, theme, language, length, structure, audience, and forbidden elements.
- Existing draft or references.

## Tool Map

- `creative_brief_create`
- `creative_brief_inspect`
- `song_structure_create`
- `song_structure_inspect`
- `creative_revision_packet_create`
- `creative_revision_packet_inspect`
- `writing_draft_create`
- `writing_draft_inspect`
- `sound_spec_create`
- `sound_spec_inspect`
- `music-and-sound-generation`
- `humanized-writing`
- `write_note`
- `voice_response_prepare`

## Workflow

1. Clarify genre, theme, and constraints.
2. Use `creative_brief_create` for story, poem, scene, prompt, slogan, or lyric planning before drafting.
3. Use `song_structure_create` for verse/chorus/bridge, hook, rhyme, and production planning.
4. Use `creative_revision_packet_create` when revising an existing user-provided draft with protected elements and variants.
5. Create original material rather than copying protected works.
6. Offer variants for tone or intensity.
7. Add performance or production notes when useful.
8. Inspect artifacts before reporting or turning them into writing/audio specs.

## Native Implementation Boundaries

- Do not import Hermes songwriting scripts.
- Audio generation requires native/provider-approved tools.
- Do not claim music was generated when only lyrics/prompts were written.
- Native creative artifacts are local Markdown/JSON specs; they are not posted, published, or converted to audio automatically.
- Song structures must keep `audio_generation_status: not_generated` unless a separate approved audio tool proves otherwise.

## Safety And Approval

- Do not reproduce copyrighted lyrics.
- Do not imitate living artists' voices too closely.
- Respect sensitive subject constraints.

## Verification

- Confirm output matches requested structure.
- Mark prompt/lyrics/artifact type clearly.
- Inspect creative briefs, song structures, and revision packets for counts, status, and safety notes.
- Check originality constraints.

## Failure Modes

- Generic lyrics without imagery.
- Too-close imitation.
- Confusing prompt draft with generated audio.

## References

- Shortlist item: `creative-writing-and-songwriting`.
