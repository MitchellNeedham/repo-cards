# Put `repo-cards` on PATH on Windows. The Claude Code skill ships via /plugin.
#
# A .cmd shim rather than a symlink: symlinks on Windows need admin or Developer Mode,
# and a shim works from cmd, PowerShell and anything that shells out.
$ErrorActionPreference = 'Stop'

$src = Join-Path $PSScriptRoot 'bin\repo-cards'
if (-not (Test-Path $src)) { throw "$src not found; run this from the repo-cards checkout" }

$bin = if ($env:REPO_CARDS_BIN) { $env:REPO_CARDS_BIN } else { Join-Path $HOME '.local\bin' }
New-Item -ItemType Directory -Force -Path $bin | Out-Null

$shim = Join-Path $bin 'repo-cards.cmd'
"@echo off`r`nuv run --quiet --script `"$src`" %*" | Set-Content -Path $shim -Encoding ASCII
Write-Host "wrote $shim"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Warning "uv is not on PATH. repo-cards is a uv script and will not run without it."
    Write-Host '  install:  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"'
}

if (($env:PATH -split ';') -notcontains $bin) {
    Write-Warning "$bin is not on your PATH. Add it for the current user with:"
    Write-Host "  [Environment]::SetEnvironmentVariable('PATH', `"`$env:PATH;$bin`", 'User')"
}

Write-Host ""
Write-Host "Next:"
Write-Host "  1. /plugin marketplace add <path to this repo>"
Write-Host "     /plugin install repo-cards@repo-cards"
Write-Host "  2. repo-cards register C:\path\to\repo"
Write-Host "  3. In that repo, ask Claude: 'generate repo cards'"
