#!/usr/bin/env python3
"""一键发布准备（顺序固定，避免行尾/校验和漂移）：

    1. 把 git 跟踪的所有文本文件归一为 LF（按字节写，避开 Windows 新行转换）
    2. 重算 SHA256SUMS（基于归一后的真实字节）
    3. git archive 打 zip（不含 .git）
    4. 解包到临时目录 → 跑 verify.py → 跑 install.ps1 的完整性校验
    5. 打印 zip 的 sha256，供 Release 说明引用

用法：
    python release.py                 # 版本号取自 CHANGELOG 最新标题
    python release.py --version 1.0.1 --out D:/dist
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent
TEXT_SUFFIX = {".md", ".py", ".ps1", ".sh", ".json", ".txt", ".yml", ".yaml"}


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def normalize_lf(files: list[str]) -> list[str]:
    changed = []
    for rel in files:
        p = ROOT / rel
        if not p.exists() or p.is_dir():
            continue
        if p.suffix.lower() not in TEXT_SUFFIX and p.name not in (".gitattributes", "LICENSE", "NOTICE"):
            continue
        raw = p.read_bytes()
        fixed = raw.replace(b"\r\n", b"\n")
        if fixed != raw:
            p.write_bytes(fixed)
            changed.append(rel)
    return changed


def write_sums(files: list[str]) -> int:
    lines = []
    for rel in sorted(files):
        p = ROOT / rel
        if not p.exists() or rel == "SHA256SUMS":
            continue
        lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {rel}")
    (ROOT / "SHA256SUMS").write_bytes(("\n".join(lines) + "\n").encode())
    return len(lines)


def version_from_changelog() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^## v([0-9]+\.[0-9]+\.[0-9]+)", text, re.M)
    return m.group(1) if m else "0.0.0"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=None)
    ap.add_argument("--out", default=str(ROOT.parent))
    args = ap.parse_args()

    version = args.version or version_from_changelog()
    files = tracked()
    changed = normalize_lf(files)
    if changed:
        # 归一后重新取列表（内容变了，但路径不变）
        pass
    n = write_sums(files)
    print(f"[1] LF normalized: {len(changed)} file(s)" + (f" -> {', '.join(changed)}" if changed else ""))
    print(f"[2] SHA256SUMS: {n} entries")

    zip_path = Path(args.out) / f"yi-{version}.zip"
    if zip_path.exists():
        zip_path.unlink()
    # 关键顺序：归一与校验和必须先落到提交里，git archive 只打包 HEAD
    subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
    if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        subprocess.run(["git", "-c", "user.name=yi", "-c", "user.email=yi@users.noreply.github.com",
                        "commit", "-q", "-m", f"chore(release): normalize LF + checksums (v{version})"],
                       cwd=ROOT, check=True)
        print("[2.5] committed normalization + checksums")
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit(f"工作区仍不干净，拒绝打包：\n{dirty}")
    subprocess.run(["git", "archive", "--format=zip", "--prefix=", f"--output={zip_path}", "HEAD"], cwd=ROOT, check=True)
    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    print(f"[3] {zip_path.name}: {zip_path.stat().st_size:,} bytes\n    sha256 {sha}")

    # [4] 解包自检
    tmp = Path(tempfile.mkdtemp(prefix="yi-release-"))
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        r = subprocess.run([sys.executable, "verify.py"], cwd=tmp, capture_output=True, encoding="utf-8", errors="replace")
        last = (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else ""
        print(f"[4] verify.py in extracted zip -> {'PASS' if r.returncode == 0 else 'FAIL'}: {last}")
        dest = tmp / "_install"
        pw = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "install.ps1",
                             "-Copy", "-Dest", str(dest)],
                            cwd=tmp, capture_output=True, encoding="utf-8", errors="replace")
        ok = pw.returncode == 0
        print(f"[5] install.ps1 -Copy -> {'PASS' if ok else 'FAIL'}")
        if not ok:
            print((pw.stdout or "")[-400:], (pw.stderr or "")[-400:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nRESULT " + json.dumps({"version": version, "zip": str(zip_path), "sha256": sha}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())