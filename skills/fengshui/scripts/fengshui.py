#!/usr/bin/env python3
"""风水·阳宅排盘引擎（确定性计算层）。

只做「可以算出唯一答案」的部分：二十四山换算、八宅游年盘、命卦、三元九运、流年九星。
不给吉凶结论、不做恐吓、不替代现场勘测。解读由 LLM 依 references/ 展开。

口径（全部可复核）：
  二十四山：自壬起每山 15°，壬起于 337.5°（即正北 352.5°~7.5° 为子）。
  后天八卦方位：坎北 坤西南 震东 巽东南 中 乾西北 兑西 艮东北 离南。
  八宅游年：大游年歌「乾六天五祸绝延生」等八句，自伏位（坐山卦）起按后天八卦顺时针布八方。
  命卦：男 (100-年后两位) mod 9，女 (年后两位-4) mod 9；余 0 作 9；余 5 男寄坤、女寄艮。
        以立春为年界，立春前出生按上一年（本脚本不查节气，需调用方自行确认）。
  三元九运：上元一运始于 1864，每运 20 年；运 = ((年-1864)//20) mod 9 + 1。
  流年九星：入中之星 = (11 - 年数字和) mod 9（余 0 作 9），顺飞九宫。
  飞星次序：中→乾→兑→艮→离→坎→坤→震→巽（洛书数序 5→6→7→8→9→1→2→3→4）。

用法：
  python fengshui.py --zuoxiang 210
  python fengshui.py --zuoxiang 坤
  python fengshui.py --bazhai 210
  python fengshui.py --minggua 1990 --gender 男
  python fengshui.py --yun 2026
  python fengshui.py --sha 路冲
  python fengshui.py --sha-list
  python fengshui.py --self-test
退出码：0 正常；2 参数错误；3 数据缺失/非法或自检失败。
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

# 二十四山，自壬起顺时针，每山 15°，壬的起始角 337.5°
SHAN24 = ["壬", "子", "癸", "丑", "艮", "寅", "甲", "卯", "乙", "辰", "巽", "巳",
          "丙", "午", "丁", "未", "坤", "申", "庚", "酉", "辛", "戌", "乾", "亥"]
SHAN_START = 337.5

# 二十四山 → 后天八卦
SHAN_GUA = {
    "壬": "坎", "子": "坎", "癸": "坎",
    "丑": "艮", "艮": "艮", "寅": "艮",
    "甲": "震", "卯": "震", "乙": "震",
    "辰": "巽", "巽": "巽", "巳": "巽",
    "丙": "离", "午": "离", "丁": "离",
    "未": "坤", "坤": "坤", "申": "坤",
    "庚": "兑", "酉": "兑", "辛": "兑",
    "戌": "乾", "乾": "乾", "亥": "乾",
}

# 后天八卦：方位、五行、洛书数
GUA_INFO = {
    "坎": ("北", "水", 1), "坤": ("西南", "土", 2), "震": ("东", "木", 3),
    "巽": ("东南", "木", 4), "乾": ("西北", "金", 6), "兑": ("西", "金", 7),
    "艮": ("东北", "土", 8), "离": ("南", "火", 9),
}

# 后天八卦顺时针次序（自北起）
CLOCKWISE = ["坎", "艮", "震", "巽", "离", "坤", "兑", "乾"]

# 大游年歌：自伏位卦起，按后天八卦顺时针依次为 八方游年（伏位在首）
DAYOUNIAN = {
    "乾": ["伏位", "六煞", "天医", "五鬼", "祸害", "绝命", "延年", "生气"],
    "坎": ["伏位", "五鬼", "天医", "生气", "延年", "绝命", "祸害", "六煞"],
    "艮": ["伏位", "六煞", "绝命", "祸害", "生气", "延年", "天医", "五鬼"],
    "震": ["伏位", "延年", "生气", "祸害", "绝命", "五鬼", "天医", "六煞"],
    "巽": ["伏位", "天医", "五鬼", "六煞", "祸害", "生气", "绝命", "延年"],
    "离": ["伏位", "六煞", "五鬼", "绝命", "延年", "祸害", "生气", "天医"],
    "坤": ["伏位", "天医", "延年", "绝命", "生气", "祸害", "五鬼", "六煞"],
    "兑": ["伏位", "生气", "祸害", "延年", "绝命", "六煞", "五鬼", "天医"],
}

LUCK = {
    "伏位": "吉", "生气": "吉", "延年": "吉", "天医": "吉",
    "绝命": "凶", "五鬼": "凶", "六煞": "凶", "祸害": "凶",
}

MEANING = {
    "伏位": "安稳守成，宜作主位、书桌、久坐处",
    "生气": "生机与进势，宜门、床、书桌、常用动线",
    "延年": "和合与人际，宜卧室、会客、成双之物",
    "天医": "调养与修复，宜床位、休息区、餐饮",
    "绝命": "传统以为耗散，宜作储物、过道，不宜久卧久坐",
    "五鬼": "传统以为急变与口舌，宜作储物、卫浴，忌作久坐主位",
    "六煞": "传统以为牵缠是非，宜作储物、过道，忌作床头",
    "祸害": "传统以为小损与口舌，宜作次要功能，忌作主位",
}

# 飞星宫序（按洛书数序）
FLY_ORDER = ["中", "乾", "兑", "艮", "离", "坎", "坤", "震", "巽"]


class DataError(Exception):
    pass


# ---------- 基础换算 ----------

def normalize(deg: float) -> float:
    return deg % 360.0


def deg_to_shan(deg: float) -> tuple[str, float, float]:
    d = normalize(deg)
    idx = int(((d - SHAN_START) % 360.0) // 15.0)
    low = normalize(SHAN_START + idx * 15.0)
    high = normalize(low + 15.0)
    return SHAN24[idx], low, high


def shan_to_deg(shan: str) -> float:
    if shan not in SHAN24:
        raise ValueError(f"未知的山：{shan}")
    return normalize(SHAN_START + SHAN24.index(shan) * 15.0 + 7.5)


def parse_direction(text: str) -> tuple[str, float]:
    """接受 210 / 210.5 / 坤 / 坤山 等写法，返回 (山, 中点度数)。"""
    t = text.strip().replace("度", "").replace("°", "").replace("山", "")
    try:
        deg = normalize(float(t))
        shan, _, _ = deg_to_shan(deg)
        return shan, deg
    except ValueError:
        pass
    if t in SHAN24:
        return t, shan_to_deg(t)
    raise ValueError(f"无法识别的坐向：{text}（可给度数 0-360 或二十四山名）")


def gua_of(shan: str) -> str:
    return SHAN_GUA[shan]


def yun_of(year: int) -> dict:
    if not 1864 <= year <= 2043:
        raise ValueError("三元九运覆盖 1864-2043 年，超范围不排")
    n = (year - 1864) // 20
    yun = n % 9 + 1
    start = 1864 + n * 20
    return {"yun": yun, "start": start, "end": start + 19}


def year_star(year: int) -> int:
    s = 11 - sum(int(c) for c in str(year))
    s %= 9
    return 9 if s == 0 else s


def fly(center: int, reverse: bool = False) -> dict[str, int]:
    order = list(reversed(FLY_ORDER)) if reverse else FLY_ORDER
    return {palace: ((center - 1 + k) % 9) + 1 for k, palace in enumerate(order)}


def star_place(center: int, target: int) -> str:
    for palace, star in fly(center).items():
        if star == target:
            return palace
    raise ValueError("不可达")


# ---------- 八宅 ----------

def bazhai_rows(fuwei_gua: str) -> list[dict]:
    start = CLOCKWISE.index(fuwei_gua)
    rows = []
    for k, kind in enumerate(DAYOUNIAN[fuwei_gua]):
        gua = CLOCKWISE[(start + k) % 8]
        rows.append({
            "gua": gua,
            "fangwei": GUA_INFO[gua][0],
            "wuxing": GUA_INFO[gua][1],
            "kind": kind,
            "luck": LUCK[kind],
            "meaning": MEANING[kind],
        })
    return rows


def minggua(year: int, gender: str) -> dict:
    yy = year % 100
    if gender in ("男", "male", "m"):
        r = (100 - yy) % 9
        if r == 0:
            r = 9
        if r == 5:
            r, note = 2, "男命余五，寄坤"
        else:
            note = ""
    elif gender in ("女", "female", "f"):
        r = (yy - 4) % 9
        if r == 0:
            r = 9
        if r == 5:
            r, note = 8, "女命余五，寄艮"
        else:
            note = ""
    else:
        raise ValueError("性别只接受 男/女")
    gua = {1: "坎", 2: "坤", 3: "震", 4: "巽", 6: "乾", 7: "兑", 8: "艮", 9: "离"}[r]
    east = gua in ("坎", "震", "巽", "离")
    return {"gua": gua, "number": r, "group": "东四命" if east else "西四命", "note": note}


# ---------- 煞库 ----------

def load_sha() -> tuple[list[dict], list[Path]]:
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        raise DataError(f"未找到数据文件：{DATA_DIR}/*.json")
    entries = []
    for f in files:
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DataError(f"{f.name} JSON 解析失败：{exc}") from exc
        for e in raw.get("entries", []):
            for key in ("name", "cat", "cond", "effect", "fix"):
                if not e.get(key):
                    raise DataError(f"{f.name} 条目缺字段 {key}：{e}")
            e["_file"] = f.name
            entries.append(e)
    return entries, files


def sha_search(entries: list[dict], query: str, limit: int = 5) -> list[dict]:
    """先精确再模糊：名字全等 > 名字包含 > 查询包含名字 > 条件里包含；
    都没有时才按字面重叠兜底，避免「路冲」把「走廊直冲」全捞出来。"""
    q = query.strip()
    if not q:
        return []
    strong, weak = [], []
    for e in entries:
        name = e["name"]
        if q == name:
            strong.append((100, e))
        elif q in name:
            strong.append((80, e))
        elif name in q:
            strong.append((60, e))
        elif q in e["cond"]:
            strong.append((40, e))
        else:
            overlap = len(set(q) & set(name))
            if overlap:
                weak.append((overlap, e))
    if strong:
        strong.sort(key=lambda t: -t[0])
        return [e for _, e in strong[:limit]]
    weak.sort(key=lambda t: -t[0])
    return [e for _, e in weak[:limit]]


# ---------- 输出 ----------

def render_zuoxiang(shan: str, deg: float) -> str:
    sit_gua = gua_of(shan)
    xiang_deg = normalize(deg + 180.0)
    xiang_shan, _, _ = deg_to_shan(xiang_deg)
    xiang_gua = gua_of(xiang_shan)
    out = [
        "# 风水·坐向换算（确定性计算）",
        "",
        f"- 坐：{shan}山（{deg:.1f}°，{gua_of(shan)}卦，{GUA_INFO[sit_gua][0]}方）",
        f"- 向：{xiang_shan}山（{xiang_deg:.1f}°，{xiang_gua}卦，{GUA_INFO[xiang_gua][0]}方）",
        f"- 八宅宅卦：{sit_gua}宅（东四宅：坎震巽离；西四宅：乾坤艮兑）",
        "",
        "> 口径：二十四山各 15°，子山正北 352.5°~7.5°；向 = 坐 + 180°。",
    ]
    return "\n".join(out)


def render_bazhai(sit_gua: str) -> str:
    rows = bazhai_rows(sit_gua)
    out = [f"# 八宅游年盘：{sit_gua}宅（坐{sit_gua}）", "",
           "| 方位 | 卦 | 游年 | 吉凶 | 传统取用 |", "|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['fangwei']} | {r['gua']} | {r['kind']} | {r['luck']} | {r['meaning']} |")
    out += ["", "> 大游年歌口径；吉方宜门/床/桌/灶，凶方宜储物与过道，不必恐慌——「凶」是「宜静不宜久居」，不是灾祸。"]
    return "\n".join(out)


def render_minggua(info: dict, year: int, gender: str) -> str:
    rows = bazhai_rows(info["gua"])
    out = [f"# 命卦：{year} 年 {gender}命 → {info['gua']}卦（{info['group']}）", ""]
    if info["note"]:
        out.append(f"- 注：{info['note']}")
    out += ["| 方位 | 卦 | 游年 | 吉凶 | 传统取用 |", "|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['fangwei']} | {r['gua']} | {r['kind']} | {r['luck']} | {r['meaning']} |")
    out += ["", "> 命卦用于床位、书桌、门向的取用参考；同宅不同命不必强求一律。"]
    return "\n".join(out)


def render_yun(year: int) -> str:
    y = yun_of(year)
    st = year_star(year)
    chart = fly(st)
    wuhuang = star_place(st, 5)
    erhei = star_place(st, 2)
    out = [f"# 三元九运与流年九星：{year} 年", "",
           f"- 所处运：{y['yun']}运（{y['start']}-{y['end']} 年，当令星 {y['yun']}）",
           f"- 流年入中之星：{st}（口径：11 − 年数位和，取 mod 9，余 0 作 9）",
           f"- 五黄所在：{wuhuang}宫 ｜ 二黑所在：{erhei}宫", "",
           "| 宫位 | 星 |", "|---|---|"]
    for palace in FLY_ORDER:
        out.append(f"| {palace} | {chart[palace]} |")
    out += ["", "> 五黄方位的传统说法是「宜静不宜动、不宜动土久留」，现代做法就是别在那儿堆杂物、别久坐——不需要摆件，更不必恐慌。"]
    return "\n".join(out)


def render_sha(hits: list[dict]) -> str:
    if not hits:
        return ("未命中。可先用 `--sha-list` 看全部煞名，或按 references/xingfa.md 的形法要点自行判断。\n"
                "提示：没命中不等于没问题，形法判断以「看得见的形」为准。")
    out = []
    for e in hits:
        out += [f"## {e['name']}（{e['cat']}｜{e.get('src', '传统')}）",
                f"- 成立条件：{e['cond']}",
                f"- 传统与现代：{e['effect']}",
                f"- 可做的调整：{e['fix']}"]
        if e.get("note"):
            out.append(f"- 判断要点：{e['note']}")
        out.append("")
    return "\n".join(out)


def render_sha_list(entries: list[dict]) -> str:
    cats: dict[str, list[str]] = {}
    for e in entries:
        cats.setdefault(e["cat"], []).append(e["name"])
    out = [f"# 煞象库（{len(entries)} 条）", ""]
    for cat, names in cats.items():
        out.append(f"- **{cat}**：{'、'.join(names)}")
    return "\n".join(out)


# ---------- 自检 ----------

def self_test() -> int:
    problems: list[str] = []
    # 1) 二十四山覆盖 360°
    if len(SHAN24) != 24 or len(set(SHAN24)) != 24:
        problems.append("二十四山数量或重名异常")
    if set(SHAN_GUA) != set(SHAN24):
        problems.append("二十四山→卦 映射不完整")
    for i, s in enumerate(SHAN24):
        expect = normalize(SHAN_START + i * 15.0)
        got, low, high = deg_to_shan(shan_to_deg(s))
        if got != s or abs(normalize(low - expect)) > 1e-6:
            problems.append(f"山位换算错：{s} -> {got}")
    # 2) 大游年互反性（生气/延年/天医/绝命/五鬼/六煞/祸害 必须成对）
    for a in DAYOUNIAN:
        idx_a = CLOCKWISE.index(a)
        for k, kind in enumerate(DAYOUNIAN[a]):
            if k == 0:
                continue
            b = CLOCKWISE[(idx_a + k) % 8]
            kb = DAYOUNIAN[b][(idx_a - CLOCKWISE.index(b)) % 8]
            if kb != kind:
                problems.append(f"游年不成对：{a}-{b} 为 {kind} / {kb}")
    # 3) 每个宅卦的八方唯一
    for g in DAYOUNIAN:
        if sorted(DAYOUNIAN[g]) != sorted(set(DAYOUNIAN[g])) or len(DAYOUNIAN[g]) != 8:
            problems.append(f"{g} 游年配置异常")
    # 4) 流年九星口径锚点
    for yr, expect in ((2020, 7), (2024, 3), (2025, 2), (2026, 1)):
        if year_star(yr) != expect:
            problems.append(f"年星口径异常：{yr} -> {year_star(yr)}，应为 {expect}")
    # 5) 三元九运锚点
    if yun_of(2024)["yun"] != 9 or yun_of(2004)["yun"] != 8 or yun_of(1984)["yun"] != 7:
        problems.append("三元九运锚点异常")
    # 6) 命卦范围
    for yr in range(1950, 2010):
        for g in ("男", "女"):
            info = minggua(yr, g)
            if info["gua"] not in GUA_INFO:
                problems.append(f"命卦异常：{yr}{g}")
    # 7) 数据
    try:
        entries, files = load_sha()
        if not entries:
            problems.append("煞库为空")
        ids = [e.get("id") for e in entries if e.get("id")]
        if len(ids) != len(set(ids)):
            problems.append("煞库 id 重复")
        print(f"煞库 {len(files)} 文件 / {len(entries)} 条。")
    except DataError as exc:
        problems.append(str(exc))
    if problems:
        print(f"自检发现 {len(problems)} 处问题：")
        for p in problems[:30]:
            print(" -", p)
        return 3
    print("SELFTEST OK（二十四山/游年互反/年星锚点/三元九运/命卦/煞库）")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="风水·阳宅排盘（确定性计算层）")
    ap.add_argument("--zuoxiang", help="坐向：度数或二十四山名，如 210 / 坤")
    ap.add_argument("--bazhai", help="八宅游年盘：坐向")
    ap.add_argument("--minggua", type=int, metavar="YEAR", help="出生年（立春为界）")
    ap.add_argument("--gender", help="男/女（配合 --minggua）")
    ap.add_argument("--yun", type=int, metavar="YEAR", help="三元九运 + 流年九星")
    ap.add_argument("--sha", help="检索煞象库关键词")
    ap.add_argument("--sha-list", action="store_true", help="列出煞象库全部条名")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json-only", action="store_true")
    args = ap.parse_args(argv)

    try:
        if args.self_test:
            return self_test()
        if args.sha_list:
            entries, _ = load_sha()
            print(json.dumps(entries, ensure_ascii=False, indent=1) if args.json_only else render_sha_list(entries))
            return 0
        if args.sha:
            entries, _ = load_sha()
            hits = sha_search(entries, args.sha)
            print(json.dumps(hits, ensure_ascii=False, indent=1) if args.json_only else render_sha(hits))
            return 0
        if args.minggua:
            if not args.gender:
                print("ERROR: --minggua 需要 --gender 男|女", file=sys.stderr)
                return 2
            info = minggua(args.minggua, args.gender)
            print(json.dumps(info, ensure_ascii=False, indent=1) if args.json_only
                  else render_minggua(info, args.minggua, args.gender))
            return 0
        if args.yun:
            info = {"yun": yun_of(args.yun), "yearStar": year_star(args.yun),
                    "chart": fly(year_star(args.yun))}
            print(json.dumps(info, ensure_ascii=False, indent=1) if args.json_only else render_yun(args.yun))
            return 0
        if args.bazhai:
            shan, deg = parse_direction(args.bazhai)
            print(json.dumps({"shan": shan, "deg": deg, "rows": bazhai_rows(gua_of(shan))},
                             ensure_ascii=False, indent=1) if args.json_only
                  else render_zuoxiang(shan, deg) + "\n\n" + render_bazhai(gua_of(shan)))
            return 0
        if args.zuoxiang:
            shan, deg = parse_direction(args.zuoxiang)
            if args.json_only:
                xiang_shan, _, _ = deg_to_shan(deg + 180)
                print(json.dumps({"sitShan": shan, "sitDeg": deg, "sitGua": gua_of(shan),
                                  "xiangShan": xiang_shan, "xiangGua": gua_of(xiang_shan)},
                                 ensure_ascii=False, indent=1))
            else:
                print(render_zuoxiang(shan, deg))
            return 0
    except DataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())