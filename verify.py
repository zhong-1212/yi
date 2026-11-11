#!/usr/bin/env python3
"""fortune-suite 自检：结构 / 编译 / 零依赖引擎自检 / 依赖可用时的冒烟。

用法：python verify.py [-Root <bundle 根>] [--json]
退出码：0 全绿（含跳过依赖的项）；1 有失败。
"""
from __future__ import annotations

import argparse
import json
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REQUIRED = ("name:", "description:")
ZERO_DEP_TESTS = {
    "zhougong-jiemeng": ["scripts/jiemeng.py", "--self-test"],
    "fengshui": ["scripts/fengshui.py", "--self-test"],
}
DEP_TESTS = {
    "meihua-yishu": (["scripts/meihua.py", "--solar", "2024-2-5", "--time-index", "6", "--json-only"],
                     "lunar_python", "lunar-python"),
    "ziwei-doushu": (["scripts/paipan.py", "--solar", "1990-6-15", "--time-index", "6",
                      "--gender", "male", "--json-only"],
                     "x_iztro", "x-iztro"),
}


def check_frontmatter(skill_dir: Path) -> tuple[bool, str]:
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return False, "缺少 SKILL.md"
    text = md.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return False, "SKILL.md 无 frontmatter"
    head = text.split("---", 2)[1]
    missing = [k for k in REQUIRED if k not in head]
    if missing:
        return False, f"frontmatter 缺 {missing}"
    name = ""
    for line in head.splitlines():
        if line.strip().startswith("name:"):
            name = line.split(":", 1)[1].strip()
    if name != skill_dir.name:
        return False, f"name({name}) 与目录名不一致"
    return True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-Root", "--root", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    skills_root = root / "skills"
    if not skills_root.is_dir():
        print(f"ERROR: {skills_root} 不存在", file=sys.stderr)
        return 1

    rows, fails = [], 0
    for d in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        ok, msg = check_frontmatter(d)
        rows.append((d.name, "structure", "PASS" if ok else "FAIL", msg))
        fails += 0 if ok else 1

        # 编译所有脚本
        py_files = sorted(d.rglob("*.py")) + sorted(d.rglob("*.cjs"))
        for f in py_files:
            if f.suffix != ".py":
                continue
            try:
                py_compile.compile(str(f), cfile=str(Path(tempfile.gettempdir()) / (f.name + "c")),
                                   doraise=True)
                rows.append((d.name, f"compile {f.name}", "PASS", ""))
            except Exception as exc:  # noqa: BLE001
                rows.append((d.name, f"compile {f.name}", "FAIL", str(exc)[:120]))
                fails += 1

        # 零依赖引擎自检
        if d.name in ZERO_DEP_TESTS:
            cmd = [sys.executable, str(d / ZERO_DEP_TESTS[d.name][0])] + ZERO_DEP_TESTS[d.name][1:]
            r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
            ok = r.returncode == 0
            tail = (r.stdout or r.stderr).strip().splitlines()[-1][:100] if (r.stdout or r.stderr) else ""
            rows.append((d.name, "engine --self-test", "PASS" if ok else "FAIL", tail))
            fails += 0 if ok else 1

        # 需要第三方库的引擎：有库就冒烟，没有就 SKIP
        if d.name in DEP_TESTS:
            cmd, mod, pkg = DEP_TESTS[d.name]
            try:
                __import__(mod)
                has = True
            except Exception:  # noqa: BLE001
                has = False
            if not has:
                rows.append((d.name, "engine smoke", "SKIP", f"未安装 {pkg}（pip install {pkg}）"))
            else:
                r = subprocess.run([sys.executable, str(d / cmd[0])] + cmd[1:],
                                   capture_output=True, encoding="utf-8", errors="replace")
                ok = r.returncode == 0
                rows.append((d.name, "engine smoke", "PASS" if ok else "FAIL",
                             (r.stderr or r.stdout).strip().splitlines()[-1][:100] if (r.stderr or r.stdout) else ""))
                fails += 0 if ok else 1

        # 数据文件合法性
        for jf in sorted(d.rglob("*.json")):
            try:
                json.loads(jf.read_text(encoding="utf-8"))
                rows.append((d.name, f"json {jf.name}", "PASS", ""))
            except Exception as exc:  # noqa: BLE001
                rows.append((d.name, f"json {jf.name}", "FAIL", str(exc)[:120]))
                fails += 1

    if args.json:
        print(json.dumps({"failures": fails,
                          "rows": [dict(zip(("skill", "check", "status", "detail"), r)) for r in rows]},
                         ensure_ascii=False, indent=1))
    else:
        w = max(len(r[1]) for r in rows) if rows else 10
        for skill, check, status, detail in rows:
            mark = {"PASS": "PASS", "SKIP": "SKIP", "FAIL": "FAIL"}[status]
            print(f"{mark}  {skill:<18} {check:<{w}}  {detail}")
        print()
        if fails:
            print(f"FAILED: {fails} 项未通过")
        else:
            print("ALL GREEN（跳过项仅因缺少第三方库，不影响零依赖技能）")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())