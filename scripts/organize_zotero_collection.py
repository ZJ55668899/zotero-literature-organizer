#!/usr/bin/env python3
"""Organize a Zotero collection into subcollections, tags, and Chinese notes.

The script defaults to dry-run. Use --apply to mutate Zotero's local SQLite DB.
"""

from __future__ import annotations

import argparse
import difflib
import html
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_URL = "http://127.0.0.1:23119"
LOCAL_USER = "/api/users/0"
DEFAULT_NOTE_TITLE = "调度研究解读（Codex）"
DEFAULT_DRAFT = "zotero-literature-organizer-draft.json"
KEY_ALPHABET = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"


@dataclass
class Paper:
    key: str
    item_id: int | None
    item_type: str
    title: str
    abstract: str = ""
    date: str = ""
    zotero_tags: list[str] = field(default_factory=list)
    pdf_file: str | None = None
    pdf_text: str = ""
    keyword_text: str = ""


TAGS = [
    "深度强化学习",
    "多智能体强化学习",
    "图神经网络",
    "Transformer与注意力",
    "动态扰动",
    "多目标优化",
    "分布式与运输",
    "柔性作业车间",
    "人机资源约束",
    "综述与前沿",
]


TAG_PATTERNS: dict[str, list[str]] = {
    "深度强化学习": [
        "deep reinforcement learning",
        "drl",
        "double deep q",
        "deep q",
        "ddqn",
        "dqn",
        "ddpg",
        "td3",
        "ppo",
        "sac",
        "qmix",
    ],
    "多智能体强化学习": [
        "multi-agent",
        "multi agent",
        "madrl",
        "marl",
        "collaborative agent",
        "qmix",
        "cooperation",
    ],
    "图神经网络": [
        "graph neural",
        "gnn",
        "heterogeneous graph",
        "disjunctive graph",
        "meta-path",
        "graph-based",
    ],
    "Transformer与注意力": [
        "transformer",
        "attention",
        "gat",
        "graph attention",
        "cross-attention",
        "difformer",
    ],
    "动态扰动": [
        "dynamic",
        "job arrival",
        "new job",
        "urgent",
        "insertion",
        "breakdown",
        "disturbance",
        "rescheduling",
        "real-time",
        "repair",
    ],
    "多目标优化": [
        "multi-objective",
        "multi objective",
        "multitarget",
        "energy",
        "tardiness",
        "makespan",
        "cost",
        "load",
        "quantum annealing",
    ],
    "分布式与运输": [
        "distributed",
        "transfer",
        "transport",
        "transportation",
        "agv",
        "vehicle",
        "automated guided",
        "factory",
    ],
    "柔性作业车间": [
        "flexible job shop",
        "flexible job-shop",
        "fjsp",
        "fjssp",
        "dfjsp",
        "flexible scheduling",
    ],
    "人机资源约束": [
        "worker",
        "human",
        "fatigue",
        "skill",
        "dual-resource",
        "cooperation",
        "operator",
    ],
    "综述与前沿": [
        "review",
        "survey",
        "systematic literature review",
        "future direction",
        "comprehensive review",
    ],
}


CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("综述与趋势", ["综述与前沿"]),
    ("图网络与注意力", ["图神经网络", "Transformer与注意力"]),
    ("多智能体协同", ["多智能体强化学习"]),
    ("多目标与资源约束", ["多目标优化", "人机资源约束", "分布式与运输"]),
    ("动态扰动调度", ["动态扰动"]),
]


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def slug(text: str) -> str:
    text = re.sub(r"\.pdf$", "", text, flags=re.I)
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def request_json(path: str, timeout: int = 10) -> tuple[Any, dict[str, str]]:
    url = BASE_URL + path
    req = urllib.request.Request(url, headers={"Zotero-API-Version": "3"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
        headers = {k: v for k, v in response.headers.items()}
    return data, headers


def zotero_api_ready() -> bool:
    try:
        req = urllib.request.Request(BASE_URL + "/api/")
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def find_collection(collection_name: str | None, collection_key: str | None) -> dict[str, Any]:
    collections, _ = request_json(f"{LOCAL_USER}/collections?limit=100")
    if collection_key:
        matches = [c for c in collections if c.get("key") == collection_key]
    else:
        matches = [c for c in collections if c.get("data", {}).get("name") == collection_name]
    if not matches:
        fail(f"No Zotero collection matched: {collection_key or collection_name}")
    if len(matches) > 1:
        keys = ", ".join(f"{c['data']['name']}={c['key']}" for c in matches)
        fail(f"Multiple collections matched. Use --collection-key. Matches: {keys}")
    return matches[0]


def creator_names(creators: list[dict[str, Any]]) -> list[str]:
    names = []
    for creator in creators:
        if creator.get("creatorType") not in (None, "author"):
            continue
        if creator.get("name"):
            names.append(creator["name"])
        else:
            names.append((creator.get("firstName", "") + " " + creator.get("lastName", "")).strip())
    return [n for n in names if n]


def load_papers(collection_key: str) -> list[Paper]:
    params = urllib.parse.urlencode({"limit": "100", "include": "data", "sort": "title", "direction": "asc"})
    items, _ = request_json(f"{LOCAL_USER}/collections/{collection_key}/items/top?{params}")
    papers: list[Paper] = []
    for item in items:
        data = item.get("data", {})
        title = data.get("title") or f"Untitled {data.get('key')}"
        papers.append(
            Paper(
                key=data.get("key") or item.get("key"),
                item_id=None,
                item_type=data.get("itemType", ""),
                title=title,
                abstract=data.get("abstractNote") or "",
                date=data.get("date") or "",
                zotero_tags=[t.get("tag", "") for t in data.get("tags", []) if t.get("tag")],
            )
        )
    return papers


def pdf_text(path: Path, max_pages: int = 3) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return ""
    try:
        reader = PdfReader(str(path))
        chunks = []
        for i in range(min(max_pages, len(reader.pages))):
            chunks.append(reader.pages[i].extract_text() or "")
        return "\n".join(chunks)
    except Exception:
        return ""


def extract_keywords(text: str) -> str:
    clean = re.sub(r"[ \t]+", " ", text or "")
    match = re.search(r"(?is)(keywords?|key words?|author keywords?)\s*[:：]?\s*(.{0,900})", clean)
    if not match:
        return ""
    segment = match.group(2)
    segment = re.split(
        r"(?i)\n\s*(1\.?\s+introduction|introduction|abstract|acknowledg|references|conflict|funding)\b",
        segment,
    )[0]
    return segment.strip()


def match_pdfs(papers: list[Paper], pdf_dir: Path) -> None:
    if not pdf_dir.exists():
        return
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        return
    pdf_slugs = [(path, slug(path.name)) for path in pdfs]
    for paper in papers:
        title_slug = slug(paper.title)
        best_path: Path | None = None
        best_score = 0.0
        for path, name_slug in pdf_slugs:
            score = difflib.SequenceMatcher(None, title_slug, name_slug).ratio()
            if title_slug and title_slug in name_slug:
                score = max(score, 0.96)
            if score > best_score:
                best_score = score
                best_path = path
        if best_path and best_score >= 0.45:
            paper.pdf_file = str(best_path)
            paper.pdf_text = pdf_text(best_path)
            paper.keyword_text = extract_keywords(paper.pdf_text)


def evidence_text(paper: Paper) -> str:
    return "\n".join([paper.title, paper.abstract, paper.keyword_text, " ".join(paper.zotero_tags)]).lower()


def assign_tags(paper: Paper, max_tags: int) -> list[str]:
    evidence = evidence_text(paper)
    scored: list[tuple[int, str]] = []
    for tag, patterns in TAG_PATTERNS.items():
        score = sum(1 for pattern in patterns if pattern.lower() in evidence)
        if tag == "深度强化学习" and "reinforcement learning" in evidence and "quantum annealing" not in evidence:
            score = max(score, 1)
        if score:
            scored.append((score, tag))
    scored.sort(key=lambda pair: (-pair[0], TAGS.index(pair[1]) if pair[1] in TAGS else 999))
    tags = [tag for _, tag in scored]
    if "深度强化学习" in tags and "综述与前沿" in tags and "deep reinforcement learning" not in evidence:
        tags.remove("深度强化学习")
    return tags[: min(max_tags, 5)]


def choose_category(tags: list[str], max_subcollections: int) -> str:
    for category, category_tags in CATEGORY_RULES[:max_subcollections]:
        if any(tag in tags for tag in category_tags):
            return category
    return "其他调度研究"


def sentence_with(text: str, patterns: list[str]) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return ""
    parts = re.split(r"(?<=[.!?。！？])\s+", normalized)
    for part in parts:
        low = part.lower()
        if any(pattern in low for pattern in patterns):
            return part.strip()
    return parts[0].strip() if parts else ""


def note_for(paper: Paper, tags: list[str]) -> dict[str, str]:
    text = (paper.abstract or paper.pdf_text or "").lower()
    tag_text = "、".join(tags) if tags else "论文元数据不足，需人工补充标签"
    problem = "调度问题"
    if "柔性作业车间" in tags:
        problem = "柔性作业车间调度问题"
    elif "分布式与运输" in tags:
        problem = "分布式/运输耦合调度问题"
    elif "multi-objective quantum" in text or "quantum annealing" in text:
        problem = "多目标作业车间调度问题"
    elif "flow shop" in text or "flow-shop" in text:
        problem = "流水车间调度问题"

    difficulties: list[str] = []
    if "动态扰动" in tags:
        difficulties.append("生产过程中存在新工件到达、插单、设备故障或需求变化等动态扰动")
    if "柔性作业车间" in tags:
        difficulties.append("工序可由多台机器加工，工序选择与机器分配相互耦合")
    if "多目标优化" in tags:
        difficulties.append("完工时间、拖期、能耗、成本等目标之间需要权衡")
    if "分布式与运输" in tags:
        difficulties.append("加工资源与跨工厂/AGV/运输资源同时约束调度结果")
    if "人机资源约束" in tags:
        difficulties.append("工人技能、疲劳或协作因素会影响加工时间和资源分配")
    if not difficulties:
        difficulties.append("组合搜索空间大，传统规则难以在不同规模实例上稳定取得高质量解")
    challenge = "；".join(difficulties) + "。"

    methods: list[str] = []
    if "深度强化学习" in tags:
        methods.append("将调度过程建模为马尔可夫决策过程，并用深度强化学习学习状态到调度动作的映射")
    if "多智能体强化学习" in tags:
        methods.append("把机器、工序或资源拆成多个协同智能体进行训练与执行")
    if "图神经网络" in tags:
        methods.append("用图神经网络刻画工序、机器、车辆或人员之间的关系")
    if "Transformer与注意力" in tags:
        methods.append("引入Transformer/注意力机制捕捉关键资源和候选动作之间的依赖")
    if "多目标优化" in tags:
        methods.append("通过奖励函数或策略结构表达多目标权衡")
    if not methods:
        methods.append("根据题名、关键词和摘要构建调度优化模型，并采用相应智能优化方法求解")
    method = "；".join(methods) + "。"

    solved = f"论文面向{problem}，希望在复杂约束下提升调度解质量、实时响应能力和跨实例泛化能力。"

    if any(word in text for word in ["outperform", "superior", "better than", "exceeds", "优于", "更优"]):
        comparison = "摘要/关键词显示，作者将方法与传统调度规则、启发式/元启发式或已有学习方法进行了比较，并报告所提方法在解质量、效率或泛化性上更优。"
    elif any(word in text for word in ["review", "survey", "systematic literature review"]):
        comparison = "这是综述类工作，重点不是单一算法实验对比，而是比较不同AI/强化学习调度路线的适用场景、优势和局限。"
    else:
        comparison = "当前可读取摘要中未明确给出完整对比结果，建议阅读实验章节后补充具体基准方法和指标。"

    innovations: list[str] = []
    if "图神经网络" in tags:
        innovations.append("以图结构替代手工特征，更完整表达工序-机器-资源关系")
    if "Transformer与注意力" in tags:
        innovations.append("用注意力权重突出关键候选工序、机器或资源竞争关系")
    if "多智能体强化学习" in tags:
        innovations.append("用多智能体结构分解复杂决策并增强协作")
    if "动态扰动" in tags:
        innovations.append("把动态事件纳入状态转移或重调度机制")
    if "多目标优化" in tags:
        innovations.append("把多个生产目标统一到奖励/策略选择中")
    if not innovations:
        innovations.append("围绕特定调度场景重新设计状态、动作或搜索机制")
    principle = "其原理是把调度状态、资源关系和优化目标转化为可学习/可搜索的决策过程；创新点主要体现在" + "、".join(innovations) + "。"
    return {
        "困境/难点": challenge,
        "方法": method,
        "解决的问题": solved,
        "效果对比": comparison,
        "原理与创新点": principle,
    }


def make_draft(args: argparse.Namespace, collection: dict[str, Any], papers: list[Paper]) -> dict[str, Any]:
    for paper in papers:
        tags = assign_tags(paper, args.max_tags)
        if len(tags) > args.max_tags:
            tags = tags[: args.max_tags]
        setattr(paper, "generated_tags", tags)
        setattr(paper, "category", choose_category(tags, args.max_subcollections))
        setattr(paper, "note", note_for(paper, tags))
    all_tags: list[str] = []
    for tag in TAGS:
        if any(tag in getattr(p, "generated_tags") for p in papers):
            all_tags.append(tag)
    all_tags = all_tags[: args.max_tags]
    for paper in papers:
        paper.generated_tags = [tag for tag in paper.generated_tags if tag in all_tags]
        if not paper.generated_tags and all_tags:
            paper.generated_tags = [all_tags[0]]
    categories = []
    for paper in papers:
        if paper.category not in categories:
            categories.append(paper.category)
    categories = categories[: args.max_subcollections]
    fallback = categories[-1] if categories else "其他调度研究"
    for paper in papers:
        if paper.category not in categories:
            paper.category = fallback
    return {
        "collection": {"key": collection["key"], "name": collection.get("data", {}).get("name", "")},
        "limits": {"max_subcollections": args.max_subcollections, "max_tags": args.max_tags},
        "note_title": args.note_title,
        "subcollections": categories,
        "tags": all_tags,
        "items": [
            {
                "key": p.key,
                "title": p.title,
                "item_type": p.item_type,
                "category": p.category,
                "tags": p.generated_tags,
                "pdf_file": p.pdf_file,
                "note": p.note,
            }
            for p in papers
        ],
    }


def write_draft(draft: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = path.with_suffix(".md")
    lines = [
        f"# Zotero Literature Organizer Draft",
        "",
        f"- Collection: {draft['collection']['name']} ({draft['collection']['key']})",
        f"- Items: {len(draft['items'])}",
        f"- Subcollections: {', '.join(draft['subcollections'])}",
        f"- Tags: {', '.join(draft['tags'])}",
        "",
    ]
    for item in draft["items"]:
        lines.append(f"## {item['title']}")
        lines.append(f"- Key: `{item['key']}`")
        lines.append(f"- Subcollection: {item['category']}")
        lines.append(f"- Tags: {', '.join(item['tags'])}")
        for heading, body in item["note"].items():
            lines.append(f"- {heading}: {body}")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def appdata() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))


def profile_dirs() -> list[Path]:
    root = appdata() / "Zotero" / "Zotero" / "Profiles"
    return sorted(root.glob("*")) if root.exists() else []


def parse_data_dir_from_prefs(prefs: Path) -> Path | None:
    if not prefs.exists():
        return None
    text = prefs.read_text(encoding="utf-8", errors="ignore")
    use_data_dir = 'user_pref("extensions.zotero.useDataDir", true)' in text
    match = re.search(r'user_pref\("extensions\.zotero\.dataDir",\s*"([^"]+)"\);', text)
    if use_data_dir and match:
        raw = match.group(1).replace("\\\\", "\\")
        return Path(raw)
    return None


def zotero_data_dir() -> Path:
    for profile in profile_dirs():
        data_dir = parse_data_dir_from_prefs(profile / "prefs.js")
        if data_dir and (data_dir / "zotero.sqlite").exists():
            return data_dir
    candidates = [Path.home() / "Zotero", Path("D:/zotero")]
    for candidate in candidates:
        if (candidate / "zotero.sqlite").exists():
            return candidate
    fail("Could not locate Zotero data directory containing zotero.sqlite")


def close_zotero() -> str | None:
    exe_path = None
    if os.name == "nt":
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-Process -Name zotero -ErrorAction SilentlyContinue | Select-Object -First 1).Path",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            exe_path = result.stdout.strip() or None
        except Exception:
            exe_path = None
        subprocess.run(["taskkill", "/IM", "zotero.exe", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
    return exe_path


def start_zotero(exe_path: str | None) -> None:
    if os.name != "nt":
        return
    candidates = [exe_path, "D:/Program Files/Zotero/zotero.exe", "C:/Program Files/Zotero/zotero.exe", "zotero.exe"]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            subprocess.Popen([candidate], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            continue


def backup_db(data_dir: Path) -> Path:
    db = data_dir / "zotero.sqlite"
    if not db.exists():
        fail(f"Zotero database not found: {db}")
    backup_dir = data_dir / "codex-backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"zotero.sqlite.before-literature-organizer-{stamp}"
    shutil.copy2(db, backup)
    return backup


def new_key(cur: sqlite3.Cursor, table: str, library_id: int) -> str:
    while True:
        key = "".join(secrets.choice(KEY_ALPHABET) for _ in range(8))
        cur.execute(f"select 1 from {table} where libraryID=? and key=?", (library_id, key))
        if not cur.fetchone():
            return key


def note_html(note_title: str, note: dict[str, str]) -> str:
    parts = [f'<div class="zotero-note znv1"><h1>{html.escape(note_title)}</h1>']
    for heading in ["困境/难点", "方法", "解决的问题", "效果对比", "原理与创新点"]:
        parts.append(f"<p><strong>{html.escape(heading)}：</strong>{html.escape(note.get(heading, ''))}</p>")
    parts.append("</div>")
    return "".join(parts)


def apply_draft(draft: dict[str, Any], keep_zotero_closed: bool) -> dict[str, Any]:
    exe_path = close_zotero()
    data_dir = zotero_data_dir()
    backup = backup_db(data_dir)
    db = data_dir / "zotero.sqlite"
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("select itemTypeID from itemTypes where typeName='note'")
    note_type_id = cur.fetchone()[0]
    cur.execute("select collectionID, libraryID from collections where key=?", (draft["collection"]["key"],))
    row = cur.fetchone()
    if not row:
        fail("Target collection is missing from database")
    parent_collection_id, library_id = row
    cur.execute(
        "select i.itemID, i.key from items i join collectionItems ci on ci.itemID=i.itemID where ci.collectionID=?",
        (parent_collection_id,),
    )
    item_ids = {key: item_id for item_id, key in cur.fetchall()}
    collection_ids: dict[str, int] = {}
    for name in draft["subcollections"]:
        cur.execute(
            "select collectionID from collections where parentCollectionID=? and collectionName=?",
            (parent_collection_id, name),
        )
        row = cur.fetchone()
        if row:
            collection_ids[name] = row[0]
        else:
            cur.execute(
                "insert into collections(collectionName,parentCollectionID,libraryID,key,version,synced) values(?,?,?,?,0,0)",
                (name, parent_collection_id, library_id, new_key(cur, "collections", library_id)),
            )
            collection_ids[name] = cur.lastrowid
    tag_ids: dict[str, int] = {}
    for tag in draft["tags"]:
        cur.execute("select tagID from tags where name=?", (tag,))
        row = cur.fetchone()
        if row:
            tag_ids[tag] = row[0]
        else:
            cur.execute("insert into tags(name) values(?)", (tag,))
            tag_ids[tag] = cur.lastrowid
    created_notes = 0
    updated_notes = 0
    linked_collections = 0
    linked_tags = 0
    for item in draft["items"]:
        item_id = item_ids.get(item["key"])
        if not item_id:
            continue
        category_id = collection_ids[item["category"]]
        cur.execute(
            "insert or ignore into collectionItems(collectionID,itemID,orderIndex) values(?,?,0)",
            (category_id, item_id),
        )
        linked_collections += max(cur.rowcount, 0)
        for tag in item["tags"]:
            if tag not in tag_ids:
                continue
            cur.execute("insert or ignore into itemTags(itemID,tagID,type) values(?,?,0)", (item_id, tag_ids[tag]))
            linked_tags += max(cur.rowcount, 0)
        content = note_html(draft["note_title"], item["note"])
        cur.execute(
            "select i.itemID from itemNotes n join items i on i.itemID=n.itemID where n.parentItemID=? and n.title=?",
            (item_id, draft["note_title"]),
        )
        row = cur.fetchone()
        if row:
            note_id = row[0]
            cur.execute("update itemNotes set note=?, title=? where itemID=?", (content, draft["note_title"], note_id))
            cur.execute(
                "update items set synced=0, clientDateModified=CURRENT_TIMESTAMP, dateModified=CURRENT_TIMESTAMP where itemID=?",
                (note_id,),
            )
            updated_notes += 1
        else:
            cur.execute(
                "insert into items(itemTypeID, libraryID, key, version, synced) values(?,?,?,?,0)",
                (note_type_id, library_id, new_key(cur, "items", library_id), 0),
            )
            note_id = cur.lastrowid
            cur.execute(
                "insert into itemNotes(itemID,parentItemID,note,title) values(?,?,?,?)",
                (note_id, item_id, content, draft["note_title"]),
            )
            created_notes += 1
        cur.execute(
            "update items set synced=0, clientDateModified=CURRENT_TIMESTAMP, dateModified=CURRENT_TIMESTAMP where itemID=?",
            (item_id,),
        )
    con.commit()
    cur.execute(
        "select count(*) from itemNotes n join collectionItems ci on ci.itemID=n.parentItemID and ci.collectionID=? where n.title=?",
        (parent_collection_id, draft["note_title"]),
    )
    verified_notes = cur.fetchone()[0]
    con.close()
    if not keep_zotero_closed:
        start_zotero(exe_path)
    return {
        "backup": str(backup),
        "linked_collections": linked_collections,
        "linked_tags": linked_tags,
        "created_notes": created_notes,
        "updated_notes": updated_notes,
        "verified_notes": verified_notes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--collection-name")
    target.add_argument("--collection-key")
    parser.add_argument("--pdf-dir", default=".")
    parser.add_argument("--max-subcollections", type=int, default=5)
    parser.add_argument("--max-tags", type=int, default=10)
    parser.add_argument("--draft-out", default=DEFAULT_DRAFT)
    parser.add_argument("--note-title", default=DEFAULT_NOTE_TITLE)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--keep-zotero-closed", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_tags > 10:
        fail("--max-tags must be 10 or less")
    if args.max_subcollections < 1:
        fail("--max-subcollections must be at least 1")
    if not zotero_api_ready():
        fail("Zotero local API is not running. Start Zotero Desktop and enable the local API.")
    collection = find_collection(args.collection_name, args.collection_key)
    papers = load_papers(collection["key"])
    match_pdfs(papers, Path(args.pdf_dir))
    draft = make_draft(args, collection, papers)
    draft_path = Path(args.draft_out).resolve()
    write_draft(draft, draft_path)
    result = {
        "mode": "apply" if args.apply else "dry-run",
        "draft": str(draft_path),
        "markdown": str(draft_path.with_suffix(".md")),
        "collection": draft["collection"],
        "items": len(draft["items"]),
        "subcollections": draft["subcollections"],
        "tags": draft["tags"],
    }
    if args.apply:
        result["apply_result"] = apply_draft(draft, args.keep_zotero_closed)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
