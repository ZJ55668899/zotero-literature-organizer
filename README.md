# Zotero Literature Organizer

Turn a messy Zotero collection into a structured literature-review workspace.

`zotero-literature-organizer` is a Codex skill for researchers who collect papers faster than they can organize them. It reads a Zotero collection, local PDFs, titles, keywords, and abstracts, then drafts a clean research structure:

- A small set of topic subcollections
- No more than 10 reusable paper tags
- One Chinese reading note under every Zotero item
- A safe dry-run first, with database backup before any write

If you use Zotero for fast-moving literature reviews, scheduling optimization, reinforcement learning, smart manufacturing, or any paper-heavy field, this skill is meant to save the boring hours.

## Why Star This

Most Zotero automation tools stop at import/export. This one helps with the part researchers actually dread:

- "Which folder should this paper go into?"
- "What tags are useful without creating 80 noisy tags?"
- "What did this paper solve, how did it solve it, and why does it matter?"
- "Can I generate notes without damaging my Zotero library?"

The workflow is deliberately conservative: it drafts first, writes only with `--apply`, reuses existing folders/tags, updates existing notes instead of duplicating them, and backs up `zotero.sqlite` before mutation.

## What It Creates

For a target Zotero collection, the skill can create:

| Output | Rule |
| --- | --- |
| Child collections | Few topic buckets, usually 3-5 |
| Tags | Controlled vocabulary, capped at 10 |
| Paper notes | One child note per item |
| Draft files | JSON plus Markdown review draft |
| Backup | SQLite backup before applying changes |

The default note structure is:

1. 困境/难点
2. 方法
3. 解决的问题
4. 效果对比
5. 原理与创新点

## Quick Start

Install the skill by cloning this repository into your Codex skills directory:

```powershell
cd C:\Users\<you>\.codex\skills
git clone https://github.com/ZJ55668899/zotero-literature-organizer.git
```

Generate a draft without writing to Zotero:

```powershell
python C:\Users\<you>\.codex\skills\zotero-literature-organizer\scripts\organize_zotero_collection.py `
  --collection-name "调度优化" `
  --pdf-dir "D:\your\paper-folder"
```

Review the generated files:

- `zotero-literature-organizer-draft.json`
- `zotero-literature-organizer-draft.md`

Apply the result only after review:

```powershell
python C:\Users\<you>\.codex\skills\zotero-literature-organizer\scripts\organize_zotero_collection.py `
  --collection-name "调度优化" `
  --pdf-dir "D:\your\paper-folder" `
  --apply
```

Use `--collection-key <key>` if multiple Zotero collections have the same name.

## Example Use Case

For a Zotero folder of scheduling optimization papers, the skill can draft:

**Subcollections**

- 动态扰动调度
- 图网络与注意力
- 多智能体协同
- 多目标与资源约束
- 综述与趋势

**Tags**

- 深度强化学习
- 多智能体强化学习
- 图神经网络
- Transformer与注意力
- 动态扰动
- 多目标优化
- 分布式与运输
- 柔性作业车间
- 人机资源约束
- 综述与前沿

**Reading note**

Each paper gets a concise Chinese note explaining the research difficulty, method, solved problem, experimental comparison, and method principle/innovation.

## Safety Model

This project is designed for local Zotero Desktop, not the Zotero cloud API.

Dry-run mode:

- Reads Zotero through `http://127.0.0.1:23119/api/`
- Reads local PDFs when available
- Writes only draft JSON/Markdown files
- Does not mutate Zotero

Apply mode:

- Closes Zotero Desktop first
- Locates the real Zotero data directory from profile preferences
- Backs up `zotero.sqlite`
- Creates or reuses child collections and tags
- Creates or updates one note per paper
- Restarts Zotero unless `--keep-zotero-closed` is passed

## Requirements

- Zotero Desktop with local API enabled
- Python 3.10+
- Optional: `pypdf` for local PDF text extraction

Install optional PDF support:

```powershell
python -m pip install pypdf
```

## Command Reference

```powershell
python scripts\organize_zotero_collection.py `
  --collection-name "调度优化" `
  --pdf-dir "." `
  --max-subcollections 5 `
  --max-tags 10 `
  --draft-out zotero-literature-organizer-draft.json `
  --note-title "调度研究解读（Codex）"
```

Useful flags:

- `--collection-name`: Select a Zotero collection by display name.
- `--collection-key`: Select a Zotero collection by Zotero key.
- `--pdf-dir`: Folder containing local PDFs.
- `--max-subcollections`: Maximum topic folders, default `5`.
- `--max-tags`: Maximum generated tags, default `10`.
- `--draft-out`: JSON draft output path.
- `--note-title`: Zotero note title to create or update.
- `--apply`: Write changes into Zotero.
- `--keep-zotero-closed`: Do not restart Zotero after applying.

## Repository Layout

```text
.
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── workflow.md
└── scripts/
    └── organize_zotero_collection.py
```

## Roadmap

- Better multilingual note generation
- User-editable tag vocabularies
- Preview UI for draft approval
- Safer rollback helper using generated backups
- Export-ready literature-review tables

## Contributing

Issues and pull requests are welcome. Good contributions include:

- Better classification heuristics
- Safer Zotero database handling
- Additional paper-domain presets
- Cleaner Chinese reading-note templates
- Tests for repeated runs and duplicate prevention

If this saves you from a long afternoon of Zotero housekeeping, a star would make the project easier for other researchers to find.
