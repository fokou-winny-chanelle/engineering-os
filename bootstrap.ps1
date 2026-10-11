# engineering-os bootstrap for Windows (Windows PowerShell 5.1 or PowerShell 7+). ASCII only: 5.1 reads
# BOM-less scripts in the ANSI code page.
#
#   git clone https://github.com/<you>/engineering-os "$HOME\engineering-os"
#   powershell -ExecutionPolicy Bypass -File "$HOME\engineering-os\bootstrap.ps1" --tools "cursor,cline"
#
# Quote comma lists ("cursor,cline"): unquoted, PowerShell turns them into arrays (this script re-joins them anyway).
# Paths with spaces (C:\Users\Jane Doe) are fine. Re-run it after editing personal/PROFILE.user.md,
# mcp/servers.json or secrets.env.
# Notes:
#   - Cline hooks are macOS/Linux only today; on Windows the guard runs for Cursor and Claude Code.
#   - What it installs, only if missing and only for your user (no admin): uv (official installer, or winget if
#     you pass -UseWinget), then pre-commit at the version pinned in versions.toml (via uv). With Cline among the
#     tools (the default), `eos bootstrap` also installs the Cline extension into Cursor through Cursor's CLI.
#   - Cursor reads MCP keys from Windows user environment variables (${env:NAME} in ~\.cursor\mcp.json). This
#     script copies those keys from secrets.env into your user environment (values never printed). -NoEnv skips it.
#   - New PC from scratch: docs/NEW-MACHINE.md.
param(
  [switch]$UseWinget,
  [switch]$NoPath,
  [switch]$NoEnv,
  [Parameter(ValueFromRemainingArguments = $true)] $Rest
)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }
$localBin = Join-Path $HOME ".local\bin"

function Test-Cmd([string]$name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Invoke-Native([string]$exe, [string[]]$argList, [string]$what) {
  & $exe @argList
  if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE)" }
}

# --- git ---
if (-not (Test-Cmd git)) { throw "git is required: winget install --id Git.Git -e" }

# --- Python >= 3.10 (the Microsoft Store 'python' alias stub does not count) ---
$py = $null
foreach ($cand in @("python", "py")) {
  if (Test-Cmd $cand) {
    $probe = if ($cand -eq "py") { @("-3", "-c", "import sys; print(sys.executable)") } else { @("-c", "import sys; print(sys.executable)") }
    $exe = & $cand @probe 2>$null
    if ($LASTEXITCODE -eq 0 -and $exe) { $py = ($exe | Select-Object -First 1).Trim(); break }
  }
}
if (-not $py) { throw "Python >= 3.10 is required: winget install --id Python.Python.3.13 -e   (then open a new terminal)" }
& $py -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python >= 3.10 is required (found $py)" }
Write-Host "python: $py"
if (-not (Test-Cmd python)) {
  Write-Warning "'python' is not on PATH (only 'py' is). Agent hooks and pre-commit call 'python': re-run the Python installer with 'Add python.exe to PATH', or: winget install --id Python.Python.3.13 -e"
}

# --- uv ---
if (-not (Test-Cmd uv)) {
  if ($UseWinget -and (Test-Cmd winget)) {
    Write-Host "Installing uv with winget (astral-sh.uv)."
    Invoke-Native "winget" @("install", "--id", "astral-sh.uv", "-e", "--accept-source-agreements", "--accept-package-agreements") "winget install uv"
  } else {
    Write-Host "Installing uv with the official installer (https://docs.astral.sh/uv/getting-started/installation/)."
    Write-Host "Prefer winget? Re-run with -UseWinget, or: winget install --id astral-sh.uv -e"
    Invoke-Native "powershell" @("-NoProfile", "-ExecutionPolicy", "ByPass", "-Command", "irm https://astral.sh/uv/install.ps1 | iex") "uv installer"
  }
  $env:Path = "$localBin;$env:Path"
  if (-not (Test-Cmd uv)) { throw "uv was installed but is not on PATH yet: open a new terminal and re-run this script" }
}

# --- pre-commit (pinned) ---
if (-not (Test-Cmd pre-commit)) {
  $m = Select-String -Path (Join-Path $here "versions.toml") -Pattern '^"pre-commit" = "([^"]+)"'
  if (-not $m) { throw "pre-commit pin not found in versions.toml" }
  $pin = $m.Matches[0].Groups[1].Value
  Write-Host "Installing pre-commit $pin with uv (uv tool install)."
  Invoke-Native "uv" @("tool", "install", "pre-commit==$pin") "uv tool install pre-commit"
  $env:Path = "$localBin;$env:Path"
}

# --- arguments: re-join arrays that PowerShell made from unquoted comma lists ---
$fwd = @()
foreach ($a in @($Rest)) {
  if ($null -eq $a) { continue }
  if ($a -is [System.Array]) { $fwd += ($a -join ",") } else { $fwd += [string]$a }
}

Invoke-Native $py (@((Join-Path $here "bin\eos.py"), "bootstrap") + $fwd) "eos bootstrap"

# --- user env vars for Cursor: the keys ~\.cursor\mcp.json references as ${env:NAME}, copied from secrets.env ---
$secretsFile = Join-Path $HOME ".config\engineering-os\secrets.env"
$mcpJson = Join-Path $HOME ".cursor\mcp.json"
$testRun = ($fwd -contains "--dry-run") -or (@($fwd | Where-Object { $_ -like "--home*" }).Count -gt 0)
if (-not $NoEnv -and -not $testRun -and (Test-Path $secretsFile) -and (Test-Path $mcpJson)) {
  $wanted = @([regex]::Matches((Get-Content -Raw $mcpJson), '\$\{env:([A-Za-z0-9_]+)\}') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
  $setAny = $false
  foreach ($line in (Get-Content $secretsFile)) {
    if ($line -notmatch '^\s*(export\s+)?([A-Za-z0-9_]+)\s*=(.*)$') { continue }
    $name = $Matches[2]
    $val = $Matches[3].Trim().Trim('"').Trim("'")
    if (-not $val -or ($wanted -notcontains $name)) { continue }
    if ([Environment]::GetEnvironmentVariable($name, "User") -ne $val) {
      [Environment]::SetEnvironmentVariable($name, $val, "User")
      Write-Host "Set user environment variable $name for Cursor (value not shown)."
      $setAny = $true
    }
  }
  if ($setAny) { Write-Host "Restart Cursor (close every window) so it sees the new environment variables." }
}

# --- user PATH (no admin): add ~\.local\bin so 'eos', 'uv' and 'pre-commit' work in new terminals ---
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }
$parts = $userPath.Split(";") | Where-Object { $_ -ne "" }
if ($parts -notcontains $localBin) {
  if ($NoPath) {
    Write-Host "Add $localBin to your user PATH so 'eos' works in new terminals (skipped: -NoPath)."
  } else {
    [Environment]::SetEnvironmentVariable("Path", (($parts + $localBin) -join ";"), "User")
    Write-Host "Added $localBin to your user PATH. Open a new terminal, then run: eos doctor"
  }
} else {
  Write-Host "Done. Open a new terminal (or this one) and run: eos doctor"
}
