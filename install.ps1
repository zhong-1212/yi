# yi installer  (PowerShell 5.1+ / PowerShell 7)
# ASCII-only on purpose: Windows PowerShell 5.1 mis-decodes UTF-8 without BOM.
#
#   .\install.ps1                 # junction skills into $env:DSH_HOME\skills (or ~\.dsh\skills)
#   .\install.ps1 -Copy           # copy instead of junction (for other agents / USB)
#   .\install.ps1 -Dest <path>    # explicit target skills root
#   .\install.ps1 -Only fengshui  # install selected skills only
#   .\install.ps1 -Check          # dependency check only, do not install
param(
    [string]$Dest = "",
    [switch]$Copy,
    [string[]]$Only = @(),
    [switch]$Check
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillsSrc = Join-Path $Root "skills"

function Write-Step($m) { Write-Host "[*] $m" }
function Write-Ok($m)   { Write-Host "[+] $m" -ForegroundColor Green }
function Write-Warn2($m){ Write-Host "[!] $m" -ForegroundColor Yellow }
function Write-Err($m)  { Write-Host "[-] $m" -ForegroundColor Red }

if (-not (Test-Path $SkillsSrc)) { Write-Err "skills/ not found next to install.ps1"; exit 1 }

# ---------- 1) integrity check ----------
$sumFile = Join-Path $Root "SHA256SUMS"
if (Test-Path $sumFile) {
    Write-Step "verifying SHA256SUMS"
    $bad = 0; $n = 0
    foreach ($line in Get-Content $sumFile -Encoding UTF8) {
        if ($line -match '^\s*([0-9a-fA-F]{64})\s+\*?(.+?)\s*$') {
            $want = $Matches[1].ToLower(); $rel = $Matches[2]; $n++
            $p = Join-Path $Root ($rel -replace '/', '\')
            if (-not (Test-Path $p)) { Write-Err "missing: $rel"; $bad++; continue }
            $got = (Get-FileHash $p -Algorithm SHA256).Hash.ToLower()
            if ($got -ne $want) { Write-Err "hash mismatch: $rel"; $bad++ }
        }
    }
    if ($bad -gt 0) { Write-Err "$bad of $n files failed integrity check"; exit 1 }
    Write-Ok "integrity ok ($n files)"
} else {
    Write-Warn2 "SHA256SUMS not found, skipping integrity check"
}

# ---------- 2) dependencies ----------
$deps = @(
    @{ Skill = "meihua-yishu";    Import = "lunar_python"; Pkg = "lunar-python" },
    @{ Skill = "ziwei-doushu";    Import = "x_iztro";      Pkg = "x-iztro" }
)
$missing = @()
foreach ($d in $deps) {
    if (-not (Test-Path (Join-Path $SkillsSrc $d.Skill))) { continue }
    $ok = $false
    try { python -c "import $($d.Import)" 2>$null; if ($LASTEXITCODE -eq 0) { $ok = $true } } catch { }
    if ($ok) { Write-Ok "dependency ok: $($d.Pkg)" } else { $missing += $d.Pkg; Write-Warn2 "dependency missing: $($d.Pkg)  ->  pip install $($d.Pkg)" }
}
if ($Check) {
    Write-Step "-Check given, nothing installed"
    if ($missing.Count -gt 0) { Write-Warn2 ("install with: pip install " + ($missing -join " ")) }
    exit 0
}

# ---------- 3) destination ----------
if ([string]::IsNullOrWhiteSpace($Dest)) {
    if ($env:DSH_HOME) { $Dest = Join-Path $env:DSH_HOME "skills" }
    else { $Dest = Join-Path $HOME ".dsh\skills" }
}
if (-not (Test-Path $Dest)) { New-Item -ItemType Directory -Path $Dest -Force | Out-Null }
Write-Step "target skills root: $Dest"

# ---------- 4) install ----------
$installed = 0
foreach ($dir in Get-ChildItem $SkillsSrc -Directory) {
    $name = $dir.Name
    if ($Only.Count -gt 0 -and ($Only -notcontains $name)) { continue }
    $target = Join-Path $Dest $name
    if (Test-Path $target) {
        $item = Get-Item $target -Force
        if ($item.LinkType -eq "Junction" -or $item.LinkType -eq "SymbolicLink") {
            cmd /c rmdir "$target" | Out-Null
        } else {
            Remove-Item $target -Recurse -Force
        }
    }
    if ($Copy) {
        Copy-Item $dir.FullName $target -Recurse -Force
        Write-Ok "$name copied"
    } else {
        cmd /c mklink /J "$target" "$($dir.FullName)" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Copy-Item $dir.FullName $target -Recurse -Force
            Write-Ok "$name copied (junction unavailable)"
        } else {
            Write-Ok "$name linked"
        }
    }
    $installed++
}

Write-Host ""
Write-Ok "installed $installed skill(s) into $Dest"
if ($missing.Count -gt 0) {
    Write-Warn2 ("missing python deps: pip install " + ($missing -join " "))
}
Write-Step "next: restart the agent session (or send one message) so the skill catalog refreshes"
Write-Step "verify: python verify.py -Root `"$Root`""