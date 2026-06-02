# Zotero Literature Organizer Workflow

## Purpose

This skill turns a Zotero collection into a usable literature-review workspace. It is designed for local Zotero Desktop and a folder of local PDFs.

## Collection Rules

- Prefer 3-5 child collections unless the user requests more detail.
- Child collections represent the main topic bucket, not every keyword.
- Each paper should normally be assigned to exactly one child collection.
- Reuse existing child collections by name.
- Do not remove the paper from its original parent collection.

## Tag Rules

- Tags are cross-cutting retrieval facets.
- Total generated tags must be no more than `--max-tags` and defaults to 10.
- Merge synonyms and algorithm variants when the tag vocabulary would become noisy.
- Prefer concepts that help later filtering, such as:
  - 方法 family: 深度强化学习, 多智能体强化学习, 图神经网络, Transformer与注意力
  - problem facets: 动态扰动, 多目标优化, 分布式与运输, 柔性作业车间
  - resources/context: 人机资源约束, 综述与前沿
- Do not create one tag per paper-specific keyword.
- Do not delete user-created tags. If a prior run created too many tags, ask before pruning anything not clearly managed by the workflow.

## Note Rules

Create one child note under every top-level item. The default title is `调度研究解读（Codex）`.

Use this fixed structure:

1. 困境/难点：state the production/scheduling challenge.
2. 方法：state the model, algorithm, representation, and training method when known.
3. 解决的问题：state the specific scheduling decision or objective.
4. 效果对比：state reported comparisons. If the abstract/PDF does not provide details, say so honestly.
5. 原理与创新点：explain how the method works and what is novel.

Avoid overclaiming. When the evidence comes from title/keywords only, explicitly say the metadata is limited.

## Apply Rules

Before any write:

1. Close Zotero Desktop.
2. Locate the actual Zotero data directory from profile preferences.
3. Back up `zotero.sqlite` to `codex-backups`.
4. Write collections, tags, and notes.
5. Restart Zotero unless `--keep-zotero-closed` is passed.
6. Verify counts from the database or the local API.
