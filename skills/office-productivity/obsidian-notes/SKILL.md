---
name: obsidian-notes
description: Search, create, and organize markdown notes or Obsidian vault content through native file tools while respecting vault boundaries and user organization.
---

# Obsidian Notes

## Purpose

Support local markdown-based knowledge work, including Obsidian vaults, without requiring a plugin. Humungousaur can search/read/write notes inside allowed workspace roots.

## When To Use

Use for markdown notes, vault search, daily notes, backlinks/plans, knowledge capture, and note cleanup.

## Inputs And Evidence

- Vault path, note title/path, tags, links, source evidence, and desired output.
- Existing note contents and naming conventions.

## Tool Map

- `search_workspace`
- `list_files`
- `read_file`
- `write_note`
- `memory_write`
- `knowledge-base-builder`

## Workflow

1. Confirm vault/path boundary.
2. Search existing notes before creating duplicates.
3. Preserve user naming, tags, and link style.
4. Write concise notes with source evidence.
5. Use memory only for durable assistant context, not every note.
6. Verify created note path or updated content.

## Native Implementation Boundaries

- Use Humungousaur file/note tools.
- Do not import external reference Obsidian scripts.
- Do not depend on Obsidian app plugins unless a native adapter exists.

## Safety And Approval

- Vaults may contain private personal data.
- Avoid broad rewrites.
- Do not expose notes to external channels without approval.

## Verification

- Confirm file path and content.
- Check for duplicate note titles when relevant.
- Report if path is outside allowed roots.

## Failure Modes

- Creating duplicate scattered notes.
- Breaking backlink conventions.
- Mixing memory records with vault notes.

## References

- Shortlist item: `obsidian-notes`.
