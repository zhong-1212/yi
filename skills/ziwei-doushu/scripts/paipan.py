#!/usr/bin/env python3
"""紫微斗数排盘脚本（确定性计算层）。

引擎：x-iztro（iztro 的 Rust 核 Python 绑定），安星/四化/格局全部由代码完成，
LLM 只读本脚本输出做解读。无网络出口、无外部 API。

用法：
  python paipan.py --solar 1990-1-1 --time-index 6 --gender male
  python paipan.py --lunar 2023-2-15 --time-index 6 --gender male --leap-month
  python paipan.py --solar 1990-1-1 --time-index 6 --gender male --horoscope 2026-10-27
  python paipan.py --solar 1990-1-1 --time-index 6 --gender male --json-only

时辰索引（time_index）：子0(23-1) 丑1(1-3) 寅2(3-5) 卯3(5-7) 辰4(7-9) 巳5(9-11)
午6(11-13) 未7(13-15) 申8(15-17) 酉9(17-19) 戌10(19-21) 亥11(21-23)

输出：默认 markdown（盘面表+逐宫明细+格局+可选运限），--json-only 输出纯 JSON。
退出码：0 成功；2 参数错误；3 引擎报错（IztroError，含机器可读 code）。
"""
from __future__ import annotations

import argparse
import json
import sys

# 中文 Windows 控制台默认代码页 GBK，直接 print 盘面符号会 UnicodeEncodeError。
# 入口处自治编码（Python 3.7+），调用方无需设置 PYTHONIOENCODING。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 流被替换或极老解释器：靠下方 ASCII 安全标记兜底

TIME_RANGES = [
    "23:00~01:00", "01:00~03:00", "03:00~05:00", "05:00~07:00",
    "07:00~09:00", "09:00~11:00", "11:00~13:00", "13:00~15:00",
    "15:00~17:00", "17:00~19:00", "19:00~21:00", "21:00~23:00",
]
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def build_chart(args: argparse.Namespace) -> dict:
    from x_iztro import Astro
    from x_iztro.config import ChartConfig

    config = None
    if args.year_divide != "normal":
        config = ChartConfig(year_divide=args.year_divide, day_divide=args.day_divide)

    astro = Astro()
    common = dict(time_index=args.time_index, gender=args.gender,
                  language=args.language, config=config)
    if args.solar:
        astrolabe = astro.by_solar(args.solar, fix_leap=not args.no_fix_leap, **common)
    else:
        astrolabe = astro.by_lunar(args.lunar, is_leap_month=args.leap_month,
                                   fix_leap=not args.no_fix_leap, **common)

    data = json.loads(astrolabe.to_json())

    # 格局判定（引擎内置规则库，确定性）
    try:
        palace_by_index = {p["index"]: p["name"] for p in data["palaces"]}
        data["patterns"] = [
            {"key": p.key, "name": p.name, "scope": p.scope,
             "palaceIndex": p.palace_index, "palaceName": p.palace_name,
             "broken": p.broken,
             "stars": [{"name": s.name, "brightness": s.brightness or "",
                        "palaceName": palace_by_index.get(s.palace_index, str(s.palace_index))}
                       for s in p.stars]}
            for p in astrolabe.patterns()
        ]
    except Exception as exc:  # 格局层失败不影响盘面主体
        data["patterns"] = []
        data["patternsError"] = f"{type(exc).__name__}: {exc}"

    # 运限（可选）。HoroscopeItem.mutagen 为四颗星名，按禄权科忌顺序对应。
    if args.horoscope:
        h = astro.get_horoscope(astrolabe, args.horoscope,
                                args.horoscope_time_index if args.horoscope_time_index is not None else 6)

        def _hp(item):
            return {"name": item.name,
                    "palace": item.heavenly_stem + item.earthly_branch,
                    "mutagenLuQuanKeJi": list(item.mutagen or [])}

        data["horoscope"] = {
            "targetSolar": args.horoscope,
            "decadal": _hp(h.decadal),
            "yearly": _hp(h.yearly),
            "monthly": _hp(h.monthly),
            "daily": _hp(h.daily),
        }
    return data


def render_markdown(d: dict) -> str:
    out: list[str] = []
    palaces = sorted(d["palaces"], key=lambda p: p["index"])

    out.append(f"# 紫微斗数命盘")
    out.append("")
    out.append(f"> 阳历 {d['solarDate']} ｜ 农历 {d['lunarDate']} ｜ 干支 {d['chineseDate']}"
               f" ｜ {d['time']}（{d['timeRange']}）｜ {d['gender']}")
    out.append(f"> 五行局：{d['fiveElementsClass']} ｜ 命主 {d['soul']} ｜ 身主 {d['body']}"
               f" ｜ 命宫在{d['earthlyBranchOfSoulPalace']} 身宫在{d['earthlyBranchOfBodyPalace']}"
               f" ｜ 生肖 {d['zodiac']}")
    out.append("")

    out.append("## 十二宫盘面")
    out.append("")
    out.append("| 宫位 | 干支 | 身宫 | 主星(亮度) | 辅星/煞星 | 生年四化 | 大限 |")
    out.append("|------|------|------|-----------|----------|---------|------|")
    for p in palaces:
        majors = ", ".join(s["name"] + (s.get("brightness") or "") for s in p["majorStars"]) or "—"
        minors = ", ".join(s["name"] for s in p["minorStars"]) or "—"
        mutas = ", ".join(s["name"] + s["mutagen"]
                          for s in p["majorStars"] + p["minorStars"] if s.get("mutagen")) or "—"
        dec = f"{p['decadal']['heavenlyStem']}{p['decadal']['earthlyBranch']} ({p['decadal']['range'][0]}-{p['decadal']['range'][1]}岁)" if p.get("decadal") else "—"
        body = "(身宫)" if p.get("isBodyPalace") else ""
        out.append(f"| {p['name']} | {p['heavenlyStem']}{p['earthlyBranch']} | {body} | {majors} | {minors} | {mutas} | {dec} |")

    pats = d.get("patterns", [])
    out.append("")
    out.append("## 格局")
    if pats:
        for pt in pats:
            tag = "（破格）" if pt.get("broken") else ""
            stars = "、".join(f"{s['name']}@{s['palaceName']}" for s in pt.get("stars", []))
            out.append(f"- **{pt['name']}**{tag}〔{pt['palaceName']}〕：{stars}")
    else:
        out.append("- 未检出内置格局（不代表无吉无凶，需结合星曜庙陷与四化人工判断）")
    if d.get("patternsError"):
        out.append(f"- （格局层提示：{d['patternsError']}）")

    if "horoscope" in d:
        h = d["horoscope"]
        out.append("")
        out.append(f"## 运限（目标日 {h['targetSolar']}）")

        def _line(label, item):
            mu = item["mutagenLuQuanKeJi"]
            mu_s = (" ｜ 四化(禄权科忌)：" + "、".join(mu)) if len(mu) == 4 else ""
            return f"- {label}：{item['palace']}（{item['name']}）{mu_s}"

        out.append(_line("大限", h["decadal"]))
        out.append(_line("流年", h["yearly"]))
        out.append(_line("流月", h["monthly"]))
        out.append(_line("流日", h["daily"]))

    out.append("")
    out.append("---")
    out.append("*盘面为传统术数体系的确定性推算结果，仅供自我探索与辅助决策参考，不构成医疗、法律、财务建议。*")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="紫微斗数排盘（x-iztro 引擎）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--solar", help="公历日期 YYYY-M-D")
    g.add_argument("--lunar", help="农历日期 YYYY-M-D（配合 --leap-month）")
    ap.add_argument("--time-index", type=int, required=True, choices=range(12), metavar="0-11",
                    help="时辰索引：子0…亥11")
    ap.add_argument("--gender", required=True, choices=["male", "female"])
    ap.add_argument("--leap-month", action="store_true", help="农历输入为闰月")
    ap.add_argument("--no-fix-leap", action="store_true", help="闰月不自动修正（默认修正）")
    ap.add_argument("--language", default="zh-CN",
                    choices=["zh-CN", "zh-TW", "ja-JP", "ko-KR", "en-US", "vi-VN"])
    ap.add_argument("--year-divide", default="normal", choices=["normal", "exact"],
                    help="年分界：normal=正月初一 / exact=立春")
    ap.add_argument("--day-divide", default="forward", choices=["forward", "current"],
                    help="晚子时归属：forward=次日 / current=当天")
    ap.add_argument("--horoscope", metavar="DATE", help="追加运限计算的目标公历日 YYYY-M-D")
    ap.add_argument("--horoscope-time-index", type=int, choices=range(12), default=None)
    ap.add_argument("--json-only", action="store_true", help="只输出结构化 JSON")
    args = ap.parse_args(argv)

    try:
        data = build_chart(args)
    except ImportError:
        print("ERROR: 缺少 x-iztro（pip install x-iztro）。勿手搓安星算法。", file=sys.stderr)
        return 3
    except Exception as exc:
        code = getattr(exc, "code", "")
        print(f"ERROR[{type(exc).__name__}{'/' + code if code else ''}]: {exc}", file=sys.stderr)
        return 3

    if args.json_only:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        print(render_markdown(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
