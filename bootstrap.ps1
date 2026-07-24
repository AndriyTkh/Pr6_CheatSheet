<#
.SYNOPSIS
    One-shot dev bootstrap for CheatSheet (backend + frontend), with diagnostics.

.DESCRIPTION
    Idempotent: safe to re-run. Brings a fresh checkout to "tests pass" -
    backend venv + deps, local Postgres, migrations + queue schema, and the
    frontend node_modules. Mirrors the manual steps in backend/CLAUDE.md and
    frontend/CLAUDE.md so nobody loses a session to the host traps documented
    there (127.0.0.1 not localhost; CHEATSHEET_DB_PORT shifts only the host side).

    Debug surface (the /appdebug skill drives these):
      -Diagnose  preflight only, mutate nothing - prints tool versions, who owns
                 the DB host port, container publish state, and the CS_* env vars.
      -AutoPort  if the requested host port is owned by a NON-Docker listener
                 (a native Postgres - the exact trap that fails auth), pick the
                 next free port automatically instead of colliding.
      -LogFile   tee a full transcript to a file an agent can read back.
    Every run ends with a PASS/FAIL step summary and a matching exit code.

.PARAMETER Backend
    Bootstrap only the backend (venv, deps, DB, migrations).

.PARAMETER Frontend
    Bootstrap only the frontend (npm install).

.PARAMETER SkipDb
    Skip Docker/Postgres/migrations. Pure tests still run; DB tests skip.

.PARAMETER DbPort
    Host port to publish Postgres on. Default 5432. The container port never
    moves; only the host side of the URL changes. See -AutoPort.

.PARAMETER AutoPort
    If DbPort is taken by a non-Docker process, scan upward from 55432 for a
    free host port and use that.

.PARAMETER Test
    After setup, run the verification lines (pytest, npm run build).

.PARAMETER Diagnose
    Run preflight diagnostics only and exit. No venv, no Docker, no migrations.

.PARAMETER LogFile
    Path to tee a full transcript to. Defaults to logs/bootstrap-<timestamp>.log
    at the repo root (git-ignored). Use -NoLog to disable.

.PARAMETER NoLog
    Do not write a transcript file.

.EXAMPLE
    ./bootstrap.ps1
    Full setup, default port.

.EXAMPLE
    ./bootstrap.ps1 -AutoPort -Test
    Full setup; dodge a native Postgres on 5432 automatically, then verify.

.EXAMPLE
    ./bootstrap.ps1 -Diagnose
    Just tell me why it is broken - change nothing.
#>
[CmdletBinding()]
param(
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$SkipDb,
    [int]$DbPort = 5432,
    [switch]$AutoPort,
    [switch]$Test,
    [switch]$Diagnose,
    [string]$LogFile,
    [switch]$NoLog
)

$ErrorActionPreference = 'Stop'
$RepoRoot = $PSScriptRoot

# No -Backend/-Frontend flag means "do both".
$doBackend  = $Backend -or -not ($Backend -or $Frontend)
$doFrontend = $Frontend -or -not ($Backend -or $Frontend)

# --- output helpers -------------------------------------------------------
function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Dbg($msg)  { Write-Host "  [dbg] $msg" -ForegroundColor DarkGray }
function Write-Warn($msg) { Write-Host "  [!] $msg"   -ForegroundColor Yellow }
function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

# Step ledger - every phase records PASS/FAIL so the tail of the run is a
# machine-readable summary an agent can grep instead of scraping stack traces.
$script:Steps = [System.Collections.Generic.List[object]]::new()
function Complete-Step($name, $ok, $detail = '') {
    $script:Steps.Add([pscustomobject]@{ Name = $name; Ok = [bool]$ok; Detail = $detail })
    $tag = if ($ok) { 'PASS' } else { 'FAIL' }
    $col = if ($ok) { 'Green' } else { 'Red' }
    Write-Host ("  [{0}] {1}{2}" -f $tag, $name, $(if ($detail) { " - $detail" } else { '' })) -ForegroundColor $col
}

function Get-CmdVersion($cmd, [string[]]$verArgs) {
    if (-not (Have $cmd)) { return $null }
    try { (& $cmd @verArgs 2>&1 | Select-Object -First 1) } catch { '(version query failed)' }
}

# Native tools (docker) write to stderr on ordinary non-fatal states ("service
# db is not running"). Under ErrorActionPreference='Stop' PS 5.1 promotes that
# stderr to a terminating error even with 2>$null, which would abort preflight.
# Run such calls with the preference relaxed and hand back stdout + exit code.
function Invoke-Native([scriptblock]$Block) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $Block 2>$null
        return [pscustomobject]@{ Out = $out; Code = $LASTEXITCODE }
    } finally { $ErrorActionPreference = $prev }
}

# Who, if anyone, is listening on a host TCP port - the single most useful fact
# when the DB "won't connect". A native `postgres` here is the auth-fail trap.
function Get-PortListener([int]$Port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
            Select-Object -First 1
    } catch { return $null }
    if (-not $conn) { return $null }
    $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    [pscustomobject]@{ Port = $Port; ProcId = $conn.OwningProcess; Name = $proc.ProcessName }
}

function Find-FreePort([int]$Start) {
    for ($p = $Start; $p -lt $Start + 100; $p++) {
        if (-not (Get-PortListener $p)) { return $p }
    }
    throw "no free host port found near $Start"
}

# A listener owned by Docker's plumbing is our container; anything else on the
# DB port is a foreign server we must NOT talk to.
function Test-IsDockerListener($listener) {
    return $listener -and ($listener.Name -match 'docker|vpnkit|wslrelay|com\.docker')
}

# --- preflight ------------------------------------------------------------
function Invoke-Preflight([int]$Port) {
    Write-Step 'Preflight diagnostics'
    Write-Dbg  ("OS            : {0}" -f [System.Environment]::OSVersion.VersionString)
    Write-Dbg  ("PowerShell    : {0}" -f $PSVersionTable.PSVersion)
    Write-Dbg  ("RepoRoot      : {0}" -f $RepoRoot)
    Write-Dbg  ("python        : {0}" -f (Get-CmdVersion 'python' @('--version')))
    Write-Dbg  ("node          : {0}" -f (Get-CmdVersion 'node' @('--version')))
    Write-Dbg  ("npm           : {0}" -f (Get-CmdVersion 'npm' @('--version')))
    Write-Dbg  ("docker        : {0}" -f (Get-CmdVersion 'docker' @('--version')))

    $venvPy = Join-Path $RepoRoot 'backend\.venv\Scripts\python.exe'
    Write-Dbg ("backend .venv : {0}" -f $(if (Test-Path $venvPy) { 'present' } else { 'absent' }))

    Write-Dbg ("CS_DATABASE_URL      : {0}" -f $(if ($env:CS_DATABASE_URL) { $env:CS_DATABASE_URL } else { '(unset)' }))
    Write-Dbg ("CS_TEST_DATABASE_URL : {0}" -f $(if ($env:CS_TEST_DATABASE_URL) { $env:CS_TEST_DATABASE_URL } else { '(unset)' }))
    Write-Dbg ("CHEATSHEET_DB_PORT   : {0}" -f $(if ($env:CHEATSHEET_DB_PORT) { $env:CHEATSHEET_DB_PORT } else { '(unset)' }))

    # Host port ownership - the verdict that would have saved the last session.
    $listener = Get-PortListener $Port
    if (-not $listener) {
        Write-Dbg ("host port {0}   : free" -f $Port)
    } elseif (Test-IsDockerListener $listener) {
        Write-Dbg ("host port {0}   : Docker ({1}, pid {2})" -f $Port, $listener.Name, $listener.ProcId)
    } else {
        Write-Warn ("host port {0} owned by NON-Docker '{1}' (pid {2}) - a native server here answers with different creds and fails auth. Use -AutoPort or -DbPort <free>." -f $Port, $listener.Name, $listener.ProcId)
    }

    # Container publish state, if compose is up.
    if (Have docker) {
        Push-Location (Join-Path $RepoRoot 'backend')
        try {
            $r = Invoke-Native { docker compose port db 5432 }
            if ($r.Code -eq 0 -and $r.Out) {
                Write-Dbg ("container db published at : {0}" -f $r.Out)
            } else {
                Write-Dbg 'container db published at : (not published / not running)'
            }
        } finally { Pop-Location }
    }
    return $listener
}

# --- transcript -----------------------------------------------------------
# Log by default so every run leaves a readable trail; -NoLog opts out.
$transcriptOn = $false
if (-not $NoLog) {
    if (-not $LogFile) {
        $logDir = Join-Path $RepoRoot 'logs'
        if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
        $LogFile = Join-Path $logDir ("bootstrap-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    }
    try {
        Start-Transcript -Path $LogFile -Force | Out-Null
        $transcriptOn = $true
        Write-Dbg "logging to $LogFile"
    } catch { Write-Warn "could not start transcript: $_" }
}

try {
    # Resolve the effective host port (AutoPort may move it) before anything
    # that bakes it into a URL or a container publish.
    $preListener = Invoke-Preflight $DbPort
    if ($AutoPort -and $preListener -and -not (Test-IsDockerListener $preListener)) {
        $free = Find-FreePort 55432
        Write-Warn ("port {0} taken by '{1}' - AutoPort switching to {2}." -f $DbPort, $preListener.Name, $free)
        $DbPort = $free
    }

    # 127.0.0.1, never localhost (Docker IPv6 publish black-holes ::1 for ~21s).
    $DbUrl = "postgresql+asyncpg://cheatsheet:cheatsheet@127.0.0.1:$DbPort/cheatsheet"
    Write-Dbg "effective DbPort : $DbPort"
    Write-Dbg "effective DbUrl  : $DbUrl"

    if ($Diagnose) {
        Write-Step 'Diagnose only - no changes made'
        Complete-Step 'preflight' $true "DbPort=$DbPort"
    }
    else {
        # ---------------------------------------------------------- backend ---
        if ($doBackend) {
            $backendDir = Join-Path $RepoRoot 'backend'
            $venv = Join-Path $backendDir '.venv'
            $py   = Join-Path $venv 'Scripts\python.exe'

            Write-Step 'Backend: virtualenv + dependencies'
            if (-not (Have python)) { throw 'python not on PATH.' }
            if (-not (Test-Path $py)) {
                Write-Dbg 'Creating .venv ...'
                python -m venv $venv
            } else {
                Write-Dbg '.venv present - reusing.'
            }
            & $py -m pip install --quiet --upgrade pip
            & $py -m pip install --quiet -e "$backendDir[dev]"
            Complete-Step 'backend-deps' ($LASTEXITCODE -eq 0)

            if (-not $SkipDb) {
                Write-Step "Backend: Postgres (host port $DbPort)"
                if (-not (Have docker)) { throw 'docker not on PATH. Re-run with -SkipDb to skip DB.' }
                $env:CHEATSHEET_DB_PORT = "$DbPort"
                Push-Location $backendDir
                try {
                    docker compose up -d
                    $published = (Invoke-Native { docker compose port db 5432 }).Out
                    Write-Dbg "container db published at : $published"

                    Write-Host '  Waiting for Postgres to accept connections ...' -NoNewline
                    $ready = $false
                    foreach ($i in 1..30) {
                        $probe = Invoke-Native { docker compose exec -T db pg_isready -U cheatsheet }
                        if ($probe.Code -eq 0) { $ready = $true; break }
                        Start-Sleep -Seconds 1
                        Write-Host '.' -NoNewline
                    }
                    Write-Host ''
                    if (-not $ready) { throw 'Postgres did not become ready in 30s.' }
                    Complete-Step 'db-up' $true "published $published"

                    Write-Step 'Backend: migrations + queue schema'
                    # Migrations read CS_DATABASE_URL; config default carries no creds.
                    $env:CS_DATABASE_URL = $DbUrl
                    & $py scripts/apply_migrations.py
                    & $py scripts/apply_queue_schema.py
                    Complete-Step 'migrations' ($LASTEXITCODE -eq 0)
                } finally {
                    Pop-Location
                }
            } else {
                Write-Warn 'Skipping Docker/DB (-SkipDb).'
            }
        }

        # --------------------------------------------------------- frontend ---
        if ($doFrontend) {
            $frontendDir = Join-Path $RepoRoot 'frontend'
            if (Test-Path (Join-Path $frontendDir 'package.json')) {
                Write-Step 'Frontend: npm install'
                if (-not (Have npm)) { throw 'npm not on PATH. Re-run with -Backend to skip frontend.' }
                Push-Location $frontendDir
                try { npm install } finally { Pop-Location }
                Complete-Step 'frontend-deps' ($LASTEXITCODE -eq 0)
            } else {
                Write-Warn 'No frontend/package.json yet - skipping.'
            }
        }

        # ------------------------------------------------------------- test ---
        if ($Test) {
            if ($doBackend) {
                Write-Step 'Verify: pytest'
                $py = Join-Path $RepoRoot 'backend\.venv\Scripts\python.exe'
                Push-Location (Join-Path $RepoRoot 'backend')
                try {
                    # DB tests need this; without it they skip (a skip is not a pass).
                    # Set BOTH: the fixtures read CS_TEST_DATABASE_URL, but the queue
                    # test's module-level procrastinate_app singleton is built from
                    # CS_DATABASE_URL - leave that unset and it falls back to the config
                    # default (localhost:5432) and hits whatever native Postgres answers.
                    if (-not $SkipDb) {
                        $env:CS_DATABASE_URL = $DbUrl
                        $env:CS_TEST_DATABASE_URL = $DbUrl
                    }
                    & $py -m pytest -q
                    Complete-Step 'pytest' ($LASTEXITCODE -eq 0)
                } finally { Pop-Location }
            }
            if ($doFrontend -and (Test-Path (Join-Path $RepoRoot 'frontend\package.json'))) {
                Write-Step 'Verify: npm run build'
                Push-Location (Join-Path $RepoRoot 'frontend')
                try { npm run build } finally { Pop-Location }
                Complete-Step 'npm-build' ($LASTEXITCODE -eq 0)
            }
        }

        if ($doBackend -and -not $SkipDb) {
            Write-Step 'Bootstrap complete'
            Write-Host "DB URL: $DbUrl"
            Write-Host 'Run tests later with:' -ForegroundColor DarkGray
            Write-Host "  cd backend; .venv\Scripts\Activate.ps1" -ForegroundColor DarkGray
            Write-Host "  `$env:CS_DATABASE_URL = '$DbUrl'" -ForegroundColor DarkGray
            Write-Host "  `$env:CS_TEST_DATABASE_URL = '$DbUrl'; pytest -q" -ForegroundColor DarkGray
        }
    }
}
finally {
    if ($transcriptOn) { try { Stop-Transcript | Out-Null } catch {} }
}

# --- summary + exit code --------------------------------------------------
Write-Step 'Summary'
$failed = @($script:Steps | Where-Object { -not $_.Ok })
foreach ($s in $script:Steps) {
    $tag = if ($s.Ok) { 'PASS' } else { 'FAIL' }
    Write-Host ("  {0}  {1}{2}" -f $tag, $s.Name, $(if ($s.Detail) { " - $($s.Detail)" } else { '' }))
}
if ($failed.Count -gt 0) {
    Write-Host ("RESULT: FAIL ({0} step(s))" -f $failed.Count) -ForegroundColor Red
    exit 1
}
Write-Host 'RESULT: OK' -ForegroundColor Green
exit 0
