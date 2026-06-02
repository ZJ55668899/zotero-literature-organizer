---
name: zotero-literature-organizer
description: Organize papers in a Zotero collection by title, keywords, abstracts, and PDFs; create subcollections, controlled tags, and Chinese literature notes. Use when the user asks Codex to classify, tag, summarize, or annotate papers in a Zotero folder/collection.
---

# Zotero Literature Organizer

Use this skill to organize a Zotero Desktop collection into a compact research structure:

1. Create a small number of child collections from paper titles, keywords, abstracts, and local PDFs.
2. Create a controlled set of Chinese tags, capped at 10 total tags.
3. Add or update one Chinese child note under every paper item.

The bundled script is intentionally semi-automatic. It generates a draft first and mutates Zotero only when run with `--apply`.

## Quick Start

Generate a draft for a collection:

```powershell
python C:\Users\dagu1\.codex\skills\zotero-literature-organizer\scripts\organize_zotero_collection.py `
  --collection-name "调度优化" `
  --pdf-dir "D:\桌面\调度优化文献6.2"
```

Review the generated JSON and Markdown draft. Then apply it:

```powershell
python C:\Users\dagu1\.codex\skills\zotero-literature-organizer\scripts\organize_zotero_collection.py `
  --collection-name "调度优化" `
  --pdf-dir "D:\桌面\调度优化文献6.2" `
  --apply
```

Use `--collection-key <key>` instead of `--collection-name` when multiple collections have the same name.

## Workflow

1. **Read Zotero and papers**
   - Probe `http://127.0.0.1:23119/api/`.
   - Read top-level items from the target collection.
   - Use Zotero metadata first: title, abstract, item type, existing tags.
   - Match local PDFs by title/filename and extract the first pages when `pypdf` is available.

2. **Draft organization**
   - Keep child collections few, usually 3-5. Each paper should normally appear in exactly one new child collection.
   - Keep tags controlled and reusable, capped at 10 total. A paper may receive several tags.
   - Keep child collections and tags semantically different: child collections are the primary theme; tags are cross-cutting retrieval facets.
   - Generate one note per top-level item with this structure:
     - 困境/难点
     - 方法
     - 解决的问题
     - 效果对比
     - 原理与创新点

3. **Apply only after review**
   - Never write Zotero from the first pass unless the user explicitly requests `--apply`.
   - Before applying, close Zotero and create a SQLite backup under `<Zotero data dir>\codex-backups`.
   - Reuse existing child collections and tags by name.
   - Update an existing child note with the same note title instead of creating duplicates.

## Script Interface

```powershell
python scripts\organize_zotero_collection.py `
  --collection-name "调度优化" `
  --pdf-dir "." `
  --max-subcollections 5 `
  --max-tags 10 `
  --draft-out zotero-literature-organizer-draft.json `
  --note-title "调度研究解读（Codex）"
```

Important flags:

- `--collection-name` or `--collection-key`: required target collection selector.
- `--pdf-dir`: local paper folder; defaults to the current working directory.
- `--max-subcollections`: default `5`.
- `--max-tags`: default `10`.
- `--draft-out`: JSON draft path; a sibling `.md` file is also written.
- `--apply`: perform Zotero writes. Omit for dry-run.
- `--keep-zotero-closed`: do not restart Zotero after applying.

## Safety Rules

- Treat Zotero writes as user-data mutations.
- Use dry-run output for review before applying.
- Do not delete user-created collections, tags, notes, or attachments.
- On repeated runs, update notes with the same title and reuse matching collections/tags.
- If Zotero is locked or the database cannot be backed up, stop and report the blocker.

## More Detail

Read `references/workflow.md` when you need the full workflow rules or need to adjust classification/tagging policy.
