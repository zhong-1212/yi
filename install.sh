#!/usr/bin/env bash
# yi installer for macOS / Linux
#   ./install.sh                # symlink skills into ${DSH_HOME:-$HOME/.dsh}/skills
#   ./install.sh --copy         # copy instead of symlink
#   ./install.sh --dest <path>  # explicit target skills root
#   ./install.sh --only fengshui
#   ./install.sh --check        # dependency check only
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$ROOT/skills"
DEST="${DSH_HOME:-$HOME/.dsh}/skills"
COPY=0
CHECK=0
ONLY=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --copy) COPY=1; shift ;;
    --check) CHECK=1; shift ;;
    --dest) DEST="$2"; shift 2 ;;
    --only) ONLY+=("$2"); shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

step() { printf '[*] %s\n' "$1"; }
ok()   { printf '[+] %s\n' "$1"; }
warn() { printf '[!] %s\n' "$1"; }
err()  { printf '[-] %s\n' "$1" >&2; }

[[ -d "$SRC" ]] || { err "skills/ not found next to install.sh"; exit 1; }

# 1) integrity
if [[ -f "$ROOT/SHA256SUMS" ]]; then
  step "verifying SHA256SUMS"
  ( cd "$ROOT" && sha256sum -c SHA256SUMS --quiet ) || { err "integrity check failed"; exit 1; }
  ok "integrity ok"
else
  warn "SHA256SUMS not found, skipping integrity check"
fi

# 2) deps
MISSING=()
for pair in "meihua-yishu:lunar_python:lunar-python" "ziwei-doushu:x_iztro:x-iztro"; do
  s="${pair%%:*}"; rest="${pair#*:}"; mod="${rest%%:*}"; pkg="${rest##*:}"
  [[ -d "$SRC/$s" ]] || continue
  if python3 -c "import $mod" >/dev/null 2>&1; then ok "dependency ok: $pkg"; else MISSING+=("$pkg"); warn "dependency missing: $pkg  ->  pip install $pkg"; fi
done
if [[ $CHECK -eq 1 ]]; then
  step "--check given, nothing installed"
  [[ ${#MISSING[@]} -gt 0 ]] && warn "install with: pip install ${MISSING[*]}"
  exit 0
fi

# 3) dest
mkdir -p "$DEST"
step "target skills root: $DEST"

# 4) install
count=0
for dir in "$SRC"/*/; do
  name="$(basename "$dir")"
  if [[ ${#ONLY[@]} -gt 0 ]]; then
    match=0; for o in "${ONLY[@]}"; do [[ "$o" == "$name" ]] && match=1; done
    [[ $match -eq 1 ]] || continue
  fi
  target="$DEST/$name"
  rm -rf "$target"
  if [[ $COPY -eq 1 ]]; then
    cp -R "$dir" "$target"; ok "$name copied"
  else
    ln -s "$dir" "$target"; ok "$name linked"
  fi
  count=$((count+1))
done

echo
ok "installed $count skill(s) into $DEST"
[[ ${#MISSING[@]} -gt 0 ]] && warn "missing python deps: pip install ${MISSING[*]}"
step "next: restart the agent session so the skill catalog refreshes"
step "verify: python3 verify.py"