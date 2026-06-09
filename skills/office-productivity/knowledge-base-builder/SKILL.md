---
name: knowledge-base-builder
description: Build and query markdown knowledge bases from files, notes, memories, and research evidence with structure, provenance, and update discipline.
---

# Knowledge Base Builder

## Purpose

Create durable markdown knowledge bases that the assistant and user can search later. This skill favors clear structure, source links, and update workflows over one-off summaries.

## When To Use

Use for project wikis, personal knowledge bases, research collections, docs indexes, FAQ sets, and reusable notes.

## Inputs And Evidence

- Topic, source files/links, desired structure, audience, and update cadence.
- Existing notes and memory/search results.

## Tool Map

- `search_workspace`
- `read_file`
- `write_note`
- `memory_search`
- `research_webpages`
- `doc-coauthoring`
- `agent_skill_script_catalog`
- `agent_skill_script_run`

## Native Scripts

- `scripts/build_markdown_index.py`: builds a JSON index of markdown files with titles, relative paths, and link counts. Use it for a mechanical inventory before model-led knowledge-base organization.

## Workflow

1. Define the knowledge base purpose and folder/note structure.
2. Collect source evidence and avoid duplicate pages.
3. Write concise pages with source references.
4. Add indexes, tags, and cross-links when useful.
5. Record update rules or triggers if ongoing maintenance is desired.
6. Verify created notes and searchability.

## Native Implementation Boundaries

- Use Humungousaur file, memory, and web tools.
- Do not import external reference llm-wiki scripts.
- Do not build hidden vector stores unless a native retrieval tool exists.

## Safety And Approval

- Respect source privacy and copyright.
- Keep personal/private knowledge out of public folders.
- Do not overwrite existing notes without confirmation.

## Verification

- Confirm created paths and key source links.
- Search for duplicate/related notes.
- Report what is not covered.

## Failure Modes

- Creating a pile of summaries without navigation.
- Losing provenance.
- Mixing private and public knowledge.

## References

- Shortlist item: `knowledge-base-builder`.
