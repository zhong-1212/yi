#!/usr/bin/env python3
"""梅花易数·时间起卦引擎（确定性计算层）。

依赖：Python 标准库 + lunar-python（MIT，历法/节气换算，无网络出口）。
LLM 只读本脚本输出做解读，禁止手算起卦。

起卦规则（邵康节时间起卦法）：
  上卦 = (年支序 + 农历月数 + 农历日数) mod 8      余0作8
  下卦 = (年支序 + 农历月数 + 农历日数 + 时辰序) mod 8  余0作8
  动爻 = (总数) mod 6                               余0作6，自下而上第 n 爻
  先天八卦数：乾1 兑2 离3 震4 巽5 坎6 艮7 坤8；年支/时辰序：子1…亥12。
  干支年/月按**节气分界**（立春换年、节令换月），与本机 qimen-dunjia /
  ziwei-doushu(year_divide=exact 口径)一致：由 lunar-python EightChar 提供，
  立春前出生仍算上一年的年支。农历闰月归本月计（--leap-month 仅影响公历反查）。
  体用：动爻所在经卦为用，另一经卦为体；以八卦五行论生克。
  互卦：本卦二三四爻为下互、三四五爻为上互；变卦：动爻阴阳互变。

用法：
  python meihua.py --solar 2024-2-5 --time-index 6
  python meihua.py --lunar 2023-12-26 --time-index 6 [--leap-month]
  python meihua.py --now
  python meihua.py --solar 2024-2-5 --time-index 6 --json-only
退出码：0 成功；2 参数错误；3 依赖缺失/输入非法。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

# GBK 控制台自治编码（教训固化）：入口 reconfigure，正文不用非 GBK 符号。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
TIME_RANGES = ["23:00~01:00", "01:00~03:00", "03:00~05:00", "05:00~07:00",
               "07:00~09:00", "09:00~11:00", "11:00~13:00", "13:00~15:00",
               "15:00~17:00", "17:00~19:00", "19:00~21:00", "21:00~23:00"]
# 先天八卦数 -> 卦名
XIANTIAN = {1: "乾", 2: "兑", 3: "离", 4: "震", 5: "巽", 6: "坎", 7: "艮", 8: "坤"}
# 卦名 -> 三爻（自下而上，1 阳 0 阴）：乾三连/兑上缺/离中虚/震仰盂/巽下断/坎中满/艮覆碗/坤六断
TRI_LINES = {"乾": (1, 1, 1), "兑": (1, 1, 0), "离": (1, 0, 1), "震": (1, 0, 0),
             "巽": (0, 1, 1), "坎": (0, 1, 0), "艮": (0, 0, 1), "坤": (0, 0, 0)}
LINES_TRI = {v: k for k, v in TRI_LINES.items()}
TRI_WUXING = {"乾": "金", "兑": "金", "离": "火", "震": "木",
              "巽": "木", "坎": "水", "艮": "土", "坤": "土"}
# 通行本六十四卦：(上卦, 下卦) -> (卦序, 卦名)。《周易》经文公有领域，表据朱熹
# 《周易本义》卦次序整理（与任何排盘软件通行的上下经卦组合表一致，可逐条复核）。
HEX_BY_TRIGRAMS = {
    ("乾", "乾"): (1, "乾为天"), ("坤", "坤"): (2, "坤为地"),
    ("坎", "震"): (3, "水雷屯"), ("艮", "坎"): (4, "山水蒙"),
    ("坎", "乾"): (5, "水天需"), ("乾", "坎"): (6, "天水讼"),
    ("坤", "坎"): (7, "地水师"), ("坎", "坤"): (8, "水地比"),
    ("巽", "乾"): (9, "风天小畜"), ("乾", "兑"): (10, "天泽履"),
    ("坤", "乾"): (11, "地天泰"), ("乾", "坤"): (12, "天地否"),
    ("乾", "离"): (13, "天火同人"), ("离", "乾"): (14, "火天大有"),
    ("坤", "艮"): (15, "地山谦"), ("震", "坤"): (16, "雷地豫"),
    ("兑", "震"): (17, "泽雷随"), ("艮", "巽"): (18, "山风蛊"),
    ("坤", "兑"): (19, "地泽临"), ("巽", "坤"): (20, "风地观"),
    ("离", "震"): (21, "火雷噬嗑"), ("艮", "离"): (22, "山火贲"),
    ("艮", "坤"): (23, "山地剥"), ("坤", "震"): (24, "地雷复"),
    ("乾", "震"): (25, "天雷无妄"), ("艮", "乾"): (26, "山天大畜"),
    ("艮", "震"): (27, "山雷颐"), ("兑", "巽"): (28, "泽风大过"),
    ("坎", "坎"): (29, "坎为水"), ("离", "离"): (30, "离为火"),
    ("兑", "艮"): (31, "泽山咸"), ("震", "巽"): (32, "雷风恒"),
    ("乾", "艮"): (33, "天山遁"), ("震", "乾"): (34, "雷天大壮"),
    ("离", "坤"): (35, "火地晋"), ("坤", "离"): (36, "地火明夷"),
    ("巽", "离"): (37, "风火家人"), ("离", "兑"): (38, "火泽睽"),
    ("坎", "艮"): (39, "水山蹇"), ("震", "坎"): (40, "雷水解"),
    ("艮", "兑"): (41, "山泽损"), ("巽", "震"): (42, "风雷益"),
    ("兑", "乾"): (43, "泽天夬"), ("乾", "巽"): (44, "天风姤"),
    ("兑", "坤"): (45, "泽地萃"), ("坤", "巽"): (46, "地风升"),
    ("兑", "坎"): (47, "泽水困"), ("坎", "巽"): (48, "水风井"),
    ("兑", "离"): (49, "泽火革"), ("离", "巽"): (50, "火风鼎"),
    ("震", "震"): (51, "震为雷"), ("艮", "艮"): (52, "艮为山"),
    ("巽", "艮"): (53, "风山渐"), ("震", "兑"): (54, "雷泽归妹"),
    ("震", "离"): (55, "雷火丰"), ("离", "艮"): (56, "火山旅"),
    ("巽", "巽"): (57, "巽为风"), ("兑", "兑"): (58, "兑为泽"),
    ("巽", "坎"): (59, "风水涣"), ("坎", "兑"): (60, "水泽节"),
    ("巽", "兑"): (61, "风泽中孚"), ("震", "艮"): (62, "雷山小过"),
    ("坎", "离"): (63, "水火既济"), ("离", "坎"): (64, "火水未济"),
}
# 六十四卦（上/下卦）-> 通行本原文键，与 references/hexagram-guide.md 同表；
# 经文公有领域，数据经 liujuntao123/yijing yijing.json 64/64 bits 映射校验。
HEX_TEXTS = {
    ("乾", "乾"): ("乾：元，亨，利，贞。", "天行健，君子以自强不息。"),
    ("坤", "坤"): ("坤：元亨，利牝马之贞。", "地势坤，君子以厚德载物。"),
    ("坎", "震"): ("屯：元亨利贞。勿用有攸往，利建侯。", "云雷屯，君子以经纶。"),
    ("艮", "坎"): ("蒙：亨。匪我求童蒙，童蒙求我。", "山下出泉，蒙。"),
    ("坎", "乾"): ("需：有孚，光亨，贞吉。利涉大川。", "云上於天，需。"),
    ("乾", "坎"): ("讼：有孚，窒惕，中吉。", "天与水违行，讼。"),
    ("坤", "坎"): ("师：贞，丈人吉，无咎。", "地中有水，师。"),
    ("坎", "坤"): ("比：吉。原筮元永贞，无咎。", "地上有水，比。"),
    ("巽", "乾"): ("小畜：亨。密云不雨，自我西郊。", "风行天上，小畜。"),
    ("乾", "兑"): ("履：虎尾不呥人，亨。", "上天下泽，履。"),
    ("坤", "乾"): ("泰：小往大来，吉亨。", "天地交，泰。"),
    ("乾", "坤"): ("否：否之匪人，不利君子贞。", "天地不交，否。"),
    ("乾", "离"): ("同人：同人于野，亨。利涉大川。", "天与火，同人。"),
    ("离", "乾"): ("大有：元亨。", "火在天上，大有。"),
    ("坤", "艮"): ("谦：亨，君子有终。", "地中有山，谦。"),
    ("震", "坤"): ("豫：利建侯行师。", "雷出地奋，豫。"),
    ("兑", "震"): ("随：元亨利贞，无咎。", "泽中有雷，随。"),
    ("艮", "巽"): ("蛊：元亨，利涉大川。", "山下有风，蛊。"),
    ("坤", "兑"): ("临：元亨利贞。至于八月有凶。", "泽上有地，临。"),
    ("巽", "坤"): ("观：盥而不荐，有孚顒若。", "风行地上，观。"),
    ("离", "震"): ("噬嗑：亨，小利贞。", "雷电噬嗑。"),
    ("艮", "离"): ("贲：亨，小利有攸往。", "山下有火，贲。"),
    ("艮", "坤"): ("剥：不利有攸往。", "山附於地，剥。"),
    ("坤", "震"): ("复：亨。出入疾，反复其道。", "雷在地中，复。"),
    ("乾", "震"): ("无妄：元亨利贞。", "天下雷行，物与无妄。"),
    ("艮", "乾"): ("大畜：利贞。不家食吉。利涉大川。", "天在山中，大畜。"),
    ("艮", "震"): ("颐：贞吉。观颐，自求口实。", "山下有雷，颐。"),
    ("兑", "巽"): ("大过：栋桡。利有攸往，亨。", "泽灭木，大过。"),
    ("坎", "坎"): ("习坎：有孚，维心亨，行有尚。", "水洊至，习坎。"),
    ("离", "离"): ("离：利贞，亨。畜牝牛吉。", "明两作，离。"),
    ("兑", "艮"): ("咸：亨，利贞。取女吉。", "山上有泽，咸。"),
    ("震", "巽"): ("恒：亨，无咎，利贞。", "雷风恒。"),
    ("乾", "艮"): ("遁：亨，小利贞。", "天下有山，遁。"),
    ("震", "乾"): ("大壮：利贞。", "雷在天上，大壮。"),
    ("离", "坤"): ("晋：康侯用锡马蕃庶，昼日三接。", "明出地上，晋。"),
    ("坤", "离"): ("明夷：利艰贞。", "明入地中，明夷。"),
    ("巽", "离"): ("家人：利女贞。", "风自火出，家人。"),
    ("离", "兑"): ("睽：小事吉。", "上火下泽，睽。"),
    ("坎", "艮"): ("蹇：利西南，不利东北。", "山上有水，蹇。"),
    ("震", "坎"): ("解：利西南。无所往，其来复吉。", "雷雨作，解。"),
    ("艮", "兑"): ("损：有孚，元吉。", "山下有泽，损。"),
    ("巽", "震"): ("益：利有攸往，利涉大川。", "风雷益。"),
    ("兑", "乾"): ("夬：扬于王庭。", "泽上於天，夬。"),
    ("乾", "巽"): ("姤：女壮，勿用取女。", "天下有风，姤。"),
    ("兑", "坤"): ("萃：王假有庙。利见大人。", "泽上於地，萃。"),
    ("坤", "巽"): ("升：元亨。用见大人，勿恤。", "地中生木，升。"),
    ("兑", "坎"): ("困：亨，贞，大人吉，无咎。", "泽无水，困。"),
    ("坎", "巽"): ("井：改邑不改井，无丧无得。", "木上於水，井。"),
    ("兑", "离"): ("革：已日乃孚。元亨利贞。", "泽中有火，革。"),
    ("离", "巽"): ("鼎：元吉，亨。", "木上有火，鼎。"),
    ("震", "震"): ("震：亨。震来虩虩，笑言哑哑。", "洊雷震，君子以恐惧修省。"),
    ("艮", "艮"): ("艮：其背不获其身，行其庭不见其人。", "兼山艮，君子以思不出其位。"),
    ("巽", "艮"): ("渐：女归吉，利贞。", "山上有木，渐。"),
    ("震", "兑"): ("归妹：征凶，无攸利。", "泽上有雷，归妹。"),
    ("震", "离"): ("丰：王假之，勿忧，宜日中。", "雷电皆至，丰。"),
    ("离", "艮"): ("旅：小吉。旅贞吉。", "山上有火，旅。"),
    ("巽", "巽"): ("巽：小亨。利有攸往，利见大人。", "随风巽，君子以申命行事。"),
    ("兑", "兑"): ("兑：亨，利贞。", "丽泽兑，君子以朋友讲习。"),
    ("巽", "坎"): ("涣：亨。王假有庙。利涉大川。", "风行水上，涣。"),
    ("坎", "兑"): ("节：亨。苦节不可贞。", "泽上有水，节。"),
    ("巽", "兑"): ("中孚：豚鱼吉。利涉大川。", "泽上有风，中孚。"),
    ("震", "艮"): ("小过：亨，利贞。可小事，不可大事。", "山上有雷，小过。"),
    ("坎", "离"): ("既济：亨小，利贞。初吉终乱。", "水在火上，既济。"),
    ("离", "坎"): ("未济：亨。小狐汔济，濡其尾。", "火在水上，未济。"),
}
assert len(HEX_TEXTS) == 64 and set(HEX_TEXTS) == set(HEX_BY_TRIGRAMS)
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}   # A 生 B
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}     # A 克 B


def relation(body: str, use: str) -> str:
    """体(b)/用(u) 五行关系，传统五断语。"""
    bw, uw = TRI_WUXING[body], TRI_WUXING[use]
    if bw == uw:
        return f"体用比和（{bw}{uw}），顺遂之基"
    if SHENG[uw] == bw:
        return f"用生体（{uw}生{bw}），得外力资助"
    if SHENG[bw] == uw:
        return f"体生用（{bw}泄向{uw}），付出多回报缓"
    if KE[uw] == bw:
        return f"用克体（{uw}克{bw}），阻力明显宜稳扎"
    if KE[bw] == uw:
        return f"体克用（{bw}克{uw}），可控局但耗力"
    return "关系待察"  # 理论不可达（五行穷尽）


def cast(solar_ymd: tuple[int, int, int], time_index: int) -> dict:
    from lunar_python import Solar
    y, m, d = solar_ymd
    # 日柱以当日为准（含晚子时归当日的简化口径，SKILL.md 已注明）；
    # 时辰仅参与起卦数计算，不改变日柱。取正午时刻构造农历对象最稳。
    lunar = Solar.fromYmdHms(y, m, d, 12, 0, 0).getLunar()
    ec = lunar.getEightChar()
    year_gz = ec.getYear()  # EightChar 年柱即立春分界口径（对照 Lunar.getYearInGanZhi 的正月初一口径）
    branch_idx = BRANCHES.index(year_gz[1]) + 1  # 年支序 子1…亥12
    lm, ld = lunar.getMonth(), lunar.getDay()
    leap = lm < 0
    lm_abs = abs(lm)
    total_up = branch_idx + lm_abs + ld
    total_down = total_up + (time_index + 1)  # 时辰序：子1…亥12
    up_n = total_up % 8 or 8
    down_n = total_down % 8 or 8
    moving = total_down % 6 or 6
    up_t, down_t = XIANTIAN[up_n], XIANTIAN[down_n]
    lines = list(TRI_LINES[down_t]) + list(TRI_LINES[up_t])  # 自下而上 6 爻
    flipped = lines[:]
    flipped[moving - 1] ^= 1
    hu_lower = LINES_TRI[tuple(lines[1:4])]
    hu_upper = LINES_TRI[tuple(lines[2:5])]
    bian_lower = LINES_TRI[tuple(flipped[0:3])]
    bian_upper = LINES_TRI[tuple(flipped[3:6])]
    body_trig, use_trig = (down_t, up_t) if moving <= 3 else (up_t, down_t)
    ben = HEX_BY_TRIGRAMS[(up_t, down_t)]
    hu = HEX_BY_TRIGRAMS[(hu_upper, hu_lower)]
    bian = HEX_BY_TRIGRAMS[(bian_upper, bian_lower)]
    tb = HEX_TEXTS[(up_t, down_t)]
    th = HEX_TEXTS[(hu_upper, hu_lower)]
    tg = HEX_TEXTS[(bian_upper, bian_lower)]
    return {
        "input": {"solarDate": f"{y}-{m}-{d}", "timeIndex": time_index,
                  "shichen": BRANCHES[time_index] + "时", "timeRange": TIME_RANGES[time_index]},
        "calendar": {"lunarYear": lunar.getYearInChinese(), "lunarMonth": lm_abs,
                     "lunarDay": ld,
                     "lunarMonthInChinese": lunar.getMonthInChinese(),
                     "lunarDayInChinese": lunar.getDayInChinese(),
                     "isLeapMonth": leap,
                     "yearGanZhiByTerm": year_gz, "monthGanZhiByTerm": ec.getMonth(),
                     "dayGanZhi": ec.getDay()},
        "numbers": {"branchIndex": branch_idx, "lunarMonth": lm_abs, "lunarDay": ld,
                    "timeSequence": time_index + 1,
                    "upperSum": total_up, "totalWithTime": total_down,
                    "upperTrigramNumber": up_n, "lowerTrigramNumber": down_n,
                    "movingLine": moving},
        "benGua": {"order": ben[0], "name": ben[1], "upper": up_t, "lower": down_t,
                   "guaci": tb[0], "daxiang": tb[1], "linesBottomUp": lines},
        "huGua": {"order": hu[0], "name": hu[1], "upper": hu_upper, "lower": hu_lower,
                  "guaci": th[0], "daxiang": th[1]},
        "bianGua": {"order": bian[0], "name": bian[1], "upper": bian_upper, "lower": bian_lower,
                    "guaci": tg[0], "daxiang": tg[1]},
        "tiYong": {"body": body_trig, "use": use_trig,
                   "bodyWuxing": TRI_WUXING[body_trig], "useWuxing": TRI_WUXING[use_trig],
                   "relation": relation(body_trig, use_trig)},
    }


def render_markdown(r: dict) -> str:
    i, c, n = r["input"], r["calendar"], r["numbers"]
    out = [f"# 梅花易数·时间起卦", ""]
    out.append(f"> 公历 {i['solarDate']} {i['shichen']}（{i['timeRange']}）｜ "
               f"农历 {c['lunarYear']}年{'闰' if c['isLeapMonth'] else ''}{c['lunarMonthInChinese']}月{c['lunarDayInChinese']} ｜ "
               f"节气年柱 {c['yearGanZhiByTerm']}（立春分界）")
    out.append("")
    out.append("## 起卦数（可复核）")
    out.append(f"- 上卦数 = 年支序{n['branchIndex']} + 月{n['lunarMonth']} + 日{n['lunarDay']} = {n['upperSum']}，"
               f"mod 8 = {n['upperTrigramNumber']} → **{XIANTIAN[n['upperTrigramNumber']]}**")
    out.append(f"- 下卦数 = {n['upperSum']} + 时辰序{n['totalWithTime'] - n['upperSum']} = {n['totalWithTime']}，"
               f"mod 8 = {n['lowerTrigramNumber']} → **{XIANTIAN[n['lowerTrigramNumber']]}**")
    out.append(f"- 动爻 = {n['totalWithTime']} mod 6 = {n['movingLine']}（自下而上第 {n['movingLine']} 爻）")
    b, h, g = r["benGua"], r["huGua"], r["bianGua"]
    out.append("")
    out.append("## 卦象")
    out.append(f"| | 本卦 | 互卦 | 变卦 |")
    out.append(f"|---|---|---|---|")
    out.append(f"| 卦名 | {b['name']}（第{b['order']}卦） | {h['name']}（第{h['order']}卦） | {g['name']}（第{g['order']}卦） |")
    out.append(f"| 上/下卦 | {b['upper']}/{b['lower']} | {h['upper']}/{h['lower']} | {g['upper']}/{g['lower']} |")
    out.append("")
    out.append("## 经文参考（《周易》公有领域）")
    out.append(f"- 本卦 {b['name']} 卦辞：{b['guaci']} 大象：{b['daxiang']}")
    out.append(f"- 互卦 {h['name']} 卦辞：{h['guaci']}")
    out.append(f"- 变卦 {g['name']} 卦辞：{g['guaci']} 大象：{g['daxiang']}")
    ty = r["tiYong"]
    out.append("")
    out.append("## 体用")
    out.append(f"- 体卦：**{ty['body']}（{ty['bodyWuxing']}）** ｜ 用卦：**{ty['use']}（{ty['useWuxing']}）** ｜ {ty['relation']}")
    out.append(f"- 动爻在第 {n['movingLine']} 爻（{'下' if n['movingLine'] <= 3 else '上'}卦），故{'下' if n['movingLine'] <= 3 else '上'}卦为用")
    out.append("")
    out.append("---")
    out.append("*卦象为时间起卦法的确定性推算结果，仅供自我探索与辅助决策参考。*")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="梅花易数时间起卦（确定性引擎）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--solar", help="公历 YYYY-M-D")
    g.add_argument("--lunar", help="农历 YYYY-M-D（负年自动处理闰月场景请用 --leap-month）")
    g.add_argument("--now", action="store_true", help="以当前本地时间起卦")
    ap.add_argument("--time-index", type=int, choices=range(12), metavar="0-11",
                    help="时辰索引 子0…亥11（--now 时可省略）")
    ap.add_argument("--leap-month", action="store_true", help="农历输入为闰月")
    ap.add_argument("--json-only", action="store_true")
    args = ap.parse_args(argv)

    ti: int | None = args.time_index
    try:
        if args.now and ti is None:
            now = dt.datetime.now()
            ti = ((now.hour + 1) // 2) % 12
        if ti is None:
            print("ERROR: 需要 --time-index（或使用 --now）", file=sys.stderr)
            return 2
        if args.now:
            now = dt.datetime.now()
            ymd = (now.year, now.month, now.day)
        elif args.solar:
            y, m, d = (int(x) for x in args.solar.split("-"))
            ymd = (y, m, d)
        else:
            from lunar_python import Lunar
            y, m, d = (int(x) for x in args.lunar.split("-"))
            lm = -m if args.leap_month else m
            sol = Lunar.fromYmdHms(y, lm, d, 12, 30, 0).getSolar()
            ymd = (sol.getYear(), sol.getMonth(), sol.getDay())
        result = cast(ymd, ti)
    except ImportError:
        print("ERROR: 缺少 lunar-python（pip install lunar-python）。勿手算起卦。", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"ERROR[{type(exc).__name__}]: {exc}", file=sys.stderr)
        return 3

    if args.json_only:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print(render_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
