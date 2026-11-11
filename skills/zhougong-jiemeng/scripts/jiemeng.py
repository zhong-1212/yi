#!/usr/bin/env python3
"""周公解梦·梦象检索引擎（确定性数据层）。

数据：data/*.json（schemaVersion 1）
条目字段：kw(同义词) / cat(类目) / luck(吉中凶) / src(古|推) / text(古断语) / note(取象依据)

本脚本只做「检索、归类、校验」这一确定性部分。
解梦的解读由 LLM 依 references/ 展开；脚本不生成吉凶结论、不预测。

用法：
  python scripts/jiemeng.py 太阳 桥 掉落
  python scripts/jiemeng.py --text "我梦见在电梯里一直往下掉"
  python scripts/jiemeng.py --cat 天象
  python scripts/jiemeng.py --cats
  python scripts/jiemeng.py --stats
  python scripts/jiemeng.py --self-test
  python scripts/jiemeng.py 蛇 --json-only
退出码：0 正常（含未命中）；2 参数错误；3 数据缺失/非法。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ALLOWED_CATS = (
    "天象", "地理", "水火", "草木", "禽兽", "鱼虫", "居所营造", "器物衣食",
    "身体", "生命", "亲属", "婚恋", "争斗官讼", "财货", "言行情绪", "出行路遇",
    "鬼神异象", "现代物象",
)
ALLOWED_LUCK = ("吉", "中", "凶")
ALLOWED_SRC = ("古", "推")
REQUIRED = ("kw", "cat", "luck", "src", "text")


class DataError(Exception):
    pass


def load_entries() -> tuple[list[dict], list[Path]]:
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        raise DataError(f"未找到数据文件：{DATA_DIR}/*.json")
    entries: list[dict] = []
    for f in files:
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DataError(f"{f.name} JSON 解析失败：{exc}") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("entries"), list):
            raise DataError(f"{f.name} 缺少 entries 数组")
        for i, e in enumerate(raw["entries"]):
            if not isinstance(e, dict):
                raise DataError(f"{f.name} 第 {i} 条不是对象")
            missing = [k for k in REQUIRED if not e.get(k)]
            if missing:
                raise DataError(f"{f.name} 第 {i} 条缺字段 {missing}")
            if e["cat"] not in ALLOWED_CATS:
                raise DataError(f"{f.name} 第 {i} 条 cat 非法：{e['cat']}")
            if e["luck"] not in ALLOWED_LUCK:
                raise DataError(f"{f.name} 第 {i} 条 luck 非法：{e['luck']}")
            if e["src"] not in ALLOWED_SRC:
                raise DataError(f"{f.name} 第 {i} 条 src 非法：{e['src']}")
            e["_file"] = f.name
            entries.append(e)
    return entries, files


def search(entries: list[dict], query: str, limit: int = 12) -> list[tuple[int, dict]]:
    """关键词匹配：kw 全等 > kw 被包含于查询 > 查询被包含于 kw > 反序命中（动宾倒置）。"""
    q = query.strip()
    if not q:
        return []
    hits: list[tuple[int, dict]] = []
    for e in entries:
        best = 0
        for k in e["kw"]:
            if not isinstance(k, str) or not k:
                continue
            if q == k:
                best = max(best, 4)
            elif k in q:
                best = max(best, 3)
            elif len(q) >= 2 and q in k:
                best = max(best, 2)
            elif len(k) >= 2 and k[::-1] in q:
                # 「桥断了」之于「断桥」：中文动宾常倒置，反序再试一次
                best = max(best, 2)
        if best:
            hits.append((best, e))
    hits.sort(key=lambda t: (-t[0], -len(t[1]["text"])))
    return hits[:limit]


def fmt_entry(e: dict) -> str:
    head = f"### {e['kw'][0]}（{e['cat']}）｜{e['luck']}｜{e['src']}"
    alias = "、".join(e["kw"][1:])
    if alias:
        head += f"｜别名：{alias}"
    label = "古断" if e["src"] == "古" else "推演"
    line2 = f"- {label}：{e['text']}"
    line3 = f"- 取象：{e.get('note', '')}" if e.get("note") else ""
    return "\n".join(x for x in (head, line2, line3) if x)


def cmd_search(entries, tokens, text, limit, as_json) -> int:
    queries = list(tokens)
    if text:
        queries = [text]
    if not queries:
        print("ERROR: 需要关键词，或 --text 整句", file=sys.stderr)
        return 2
    payload = {"queries": []}
    any_hit = False
    for q in queries:
        hits = search(entries, q, limit)
        payload["queries"].append({"query": q, "matches": [e for _, e in hits]})
        if not as_json:
            print(f"## 命中：{q}（{len(hits)} 条）\n")
            if not hits:
                print("- 数据表中无直接对应梦象。请按 references/quxiang-fa.md 拆象取象，"
                      "结论标注为「推演」，不要硬套。\n")
            for _, e in hits:
                print(fmt_entry(e))
                print()
            # 整句检索只做字面命中：命中太少时提醒改用关键词补查核心动作，避免静默漏象。
            if text and hits and len(hits) <= 2:
                print("提示：整句检索只做字面命中，可能漏掉核心动作（如 坠落 / 断 / 追）。"
                      "建议再用关键词补查：`python scripts/jiemeng.py 动作词 物象词`。\n")
        any_hit = any_hit or bool(hits)
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    elif not any_hit:
        print("提示：全部未命中。可先用 --cats 浏览类目，或直接走取象法推演。")
    return 0


def cmd_cat(entries, cat, as_json) -> int:
    rows = [e for e in entries if e["cat"] == cat]
    if not rows:
        print(f"类目「{cat}」无条目。可用类目：{'、'.join(ALLOWED_CATS)}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps({"cat": cat, "count": len(rows), "entries": rows},
                         ensure_ascii=False, indent=1))
        return 0
    print(f"## 类目：{cat}（{len(rows)} 条）\n")
    for e in rows:
        print(fmt_entry(e))
        print()
    return 0


def cmd_cats(entries, as_json) -> int:
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["cat"]] = counts.get(e["cat"], 0) + 1
    if as_json:
        print(json.dumps(counts, ensure_ascii=False, indent=1))
        return 0
    print("## 类目分布\n")
    for cat in ALLOWED_CATS:
        n = counts.get(cat, 0)
        bar = "#" * min(n, 40)
        print(f"{cat:6s} {n:4d} {bar}")
    return 0


def cmd_stats(entries, files, as_json) -> int:
    by_cat: dict[str, int] = {}
    by_luck: dict[str, int] = {}
    by_src: dict[str, int] = {}
    for e in entries:
        by_cat[e["cat"]] = by_cat.get(e["cat"], 0) + 1
        by_luck[e["luck"]] = by_luck.get(e["luck"], 0) + 1
        by_src[e["src"]] = by_src.get(e["src"], 0) + 1
    dup: dict[str, int] = {}
    for e in entries:
        for k in e["kw"]:
            dup[k] = dup.get(k, 0) + 1
    dups = {k: v for k, v in dup.items() if v > 1}
    out = {
        "files": [f.name for f in files],
        "total": len(entries),
        "byCat": by_cat,
        "byLuck": by_luck,
        "bySrc": by_src,
        "duplicatePrimaryKw": dups,
    }
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    print(f"## 数据统计\n- 文件：{', '.join(out['files'])}\n- 总条数：{len(entries)}")
    print(f"- 吉凶：{by_luck}\n- 古/推：{by_src}")
    print(f"- 重复关键词：{dups or '无'}")
    return 0


def cmd_self_test(entries, files) -> int:
    problems: list[str] = []
    seen: dict[str, int] = {}
    for e in entries:
        for k in e["kw"]:
            if not isinstance(k, str) or not k.strip():
                problems.append(f"{e.get('_file')} 有空关键词")
                continue
            if len(k) > 6:
                problems.append(f"关键词过长：{k}")
            seen[k] = seen.get(k, 0) + 1
        if not (20 <= len(e["text"]) <= 160):
            problems.append(f"正文长度异常（{len(e['text'])}）：{e['kw'][0]}")
        if e["cat"] not in ALLOWED_CATS:
            problems.append(f"类目非法：{e['cat']}")
    dups = {k: v for k, v in seen.items() if v > 1}
    print(f"文件 {len(files)} 个，条目 {len(entries)} 条，关键词 {len(seen)} 个。")
    if dups:
        # 同一梦象在多类目各有一条属于「多路取象」，不是错误；报告给 LLM 时按 SKILL.md 处理。
        print(f"提示：{len(dups)} 个关键词跨类目重复（多路取象），例如："
              + "、".join(list(sorted(dups))[:8]) + "。")
    if problems:
        print(f"发现 {len(problems)} 处问题：")
        for p in problems[:40]:
            print(" -", p)
        return 3
    tag = f"（含 {len(dups)} 个多路取象关键词）" if dups else ""
    print(f"SELFTEST OK{tag}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="周公解梦·梦象检索（确定性数据层）")
    ap.add_argument("tokens", nargs="*", help="梦象关键词，可多个")
    ap.add_argument("--text", help="整句梦境描述，用于模糊命中")
    ap.add_argument("--cat", help="按类目列出")
    ap.add_argument("--cats", action="store_true", help="列出类目分布")
    ap.add_argument("--stats", action="store_true", help="数据统计")
    ap.add_argument("--self-test", action="store_true", help="校验数据完整性")
    ap.add_argument("--limit", type=int, default=12, help="每个关键词最多返回条数")
    ap.add_argument("--json-only", action="store_true")
    args = ap.parse_args(argv)

    try:
        entries, files = load_entries()
    except DataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    if args.self_test:
        return cmd_self_test(entries, files)
    if args.stats:
        return cmd_stats(entries, files, args.json_only)
    if args.cats:
        return cmd_cats(entries, args.json_only)
    if args.cat:
        return cmd_cat(entries, args.cat, args.json_only)
    return cmd_search(entries, args.tokens, args.text, args.limit, args.json_only)


if __name__ == "__main__":
    sys.exit(main())