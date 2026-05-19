$ErrorActionPreference = "Stop"

param(
  [string]$SearchQuery = "",
  [string]$Keywords = "",
  [string]$DateRange = "recent_7_days",
  [int]$MaxSearchCandidates = 50,
  [switch]$NoOpen
)

function Find-Winget {
  $cmd = Get-Command winget -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  throw "未找到 winget，无法自动静默安装 Python/Node.js/Chrome。请使用 Windows 10/11，并确认 Microsoft App Installer 可用。"
}

function Install-WithWinget {
  param([string]$PackageId)
  $winget = Find-Winget
  & $winget install --id $PackageId --exact --silent --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) {
    throw "winget 静默安装失败：$PackageId"
  }
}

function Refresh-Path {
  $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  $extra = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312",
    "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts",
    "$env:ProgramFiles\nodejs"
  ) -join ";"
  $env:Path = "$extra;$machinePath;$userPath"
}

function Get-PythonExe {
  Refresh-Path
  $candidates = @("python", "python3", "py")
  foreach ($name in $candidates) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
  }
  return $null
}

function Ensure-Python {
  $python = Get-PythonExe
  if (-not $python) {
    Install-WithWinget "Python.Python.3.12"
    $python = Get-PythonExe
  }
  if (-not $python) {
    throw "Python 自动安装后仍不可用，请重新启动 Agent 后再运行。"
  }
  if ((Split-Path -Leaf $python).ToLower() -eq "py.exe") {
    return @($python, "-3.12")
  }
  return @($python)
}

function Ensure-Node {
  Refresh-Path
  $node = Get-Command node -ErrorAction SilentlyContinue
  $npm = Get-Command npm -ErrorAction SilentlyContinue
  if (-not $node -or -not $npm) {
    Install-WithWinget "OpenJS.NodeJS.LTS"
    Refresh-Path
  }
  if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js 自动安装后仍不可用，请重新启动 Agent 后再运行。"
  }
}

function Ensure-Chrome {
  $paths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
  )
  foreach ($path in $paths) {
    if ($path -and (Test-Path $path)) { return }
  }
  if (-not (Get-Command chrome -ErrorAction SilentlyContinue) -and -not (Get-Command chrome.exe -ErrorAction SilentlyContinue)) {
    Install-WithWinget "Google.Chrome"
  }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$launchWizard = Join-Path $scriptDir "launch_wizard.py"
$pythonCmd = Ensure-Python
Ensure-Node
Ensure-Chrome

$pythonExe = $pythonCmd[0]
$pythonArgs = @()
if ($pythonCmd.Length -gt 1) {
  $pythonArgs = $pythonCmd[1..($pythonCmd.Length - 1)]
}

$argsList = @($launchWizard, "--date-range", $DateRange, "--max-search-candidates", "$MaxSearchCandidates")
if ($SearchQuery) {
  $argsList += @("--search-query", $SearchQuery, "--auto-start")
}
if ($Keywords) {
  $argsList += @("--keywords", $Keywords)
}
if ($NoOpen) {
  $argsList += "--no-open"
}

& $pythonExe @pythonArgs @argsList
if ($LASTEXITCODE -ne 0) {
  throw "小红书采集向导启动失败。"
}
