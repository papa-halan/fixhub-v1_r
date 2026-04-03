param(
    [string]$Branch = "codex/event-spine-night",
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [switch]$AllowDirtyPromptFilesOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Fail($msg) {
    Write-Host ""
    Write-Host "ERROR: $msg" -ForegroundColor Red
    exit 1
}

function Info($msg) {
    Write-Host ""
    Write-Host "== $msg ==" -ForegroundColor Cyan
}

function Ensure-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Fail "Required command not found: $name"
    }
}

function Get-ChangedFiles {
    $lines = git diff --name-only --cached
    $unstaged = git diff --name-only
    @($lines + $unstaged) | Where-Object { $_ -and $_.Trim() -ne "" } | Sort-Object -Unique
}

function Get-UncommittedFiles {
    $lines = git status --porcelain
    $files = @()
    foreach ($line in $lines) {
        if ($line.Length -ge 4) {
            $files += $line.Substring(3).Trim()
        }
    }
    $files | Sort-Object -Unique
}

function Assert-CleanWorktree {
    param(
        [string[]]$AllowedDirty = @()
    )

    $dirty = Get-UncommittedFiles
    if (-not $dirty -or $dirty.Count -eq 0) {
        return
    }

    $unexpected = @()
    foreach ($f in $dirty) {
        $ok = $false
        foreach ($a in $AllowedDirty) {
            if ($f -eq $a) { $ok = $true; break }
        }
        if (-not $ok) {
            $unexpected += $f
        }
    }

    if ($unexpected.Count -gt 0) {
        Fail ("Worktree not clean. Unexpected dirty files:`n - " + ($unexpected -join "`n - "))
    }
}

function Matches-AllowedPath {
    param(
        [string]$File,
        [string[]]$AllowedPaths
    )

    foreach ($allowed in $AllowedPaths) {
        if ($allowed.EndsWith("/")) {
            $prefix = $allowed.Replace("/", "\")
            $candidate = $File.Replace("/", "\")
            if ($candidate.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                return $true
            }
        } else {
            if ($File.Replace("/", "\") -ieq $allowed.Replace("/", "\")) {
                return $true
            }
        }
    }
    return $false
}

function Assert-ChangedFilesWithinScope {
    param(
        [string[]]$AllowedPaths
    )

    $changed = Get-UncommittedFiles
    if (-not $changed -or $changed.Count -eq 0) {
        return
    }

    $violations = @()
    foreach ($f in $changed) {
        if (-not (Matches-AllowedPath -File $f -AllowedPaths $AllowedPaths)) {
            $violations += $f
        }
    }

    if ($violations.Count -gt 0) {
        Fail ("Agent edited files outside allowed scope:`n - " + ($violations -join "`n - "))
    }
}

function Run-TestCommand {
    param([string]$Cmd)

    Info "Running tests: $Cmd"
    Invoke-Expression $Cmd
    if ($LASTEXITCODE -ne 0) {
        Fail "Test command failed: $Cmd"
    }
}

function Ensure-Branch {
    param([string]$Name)

    Info "Checking out branch $Name"
    git rev-parse --verify $Name *> $null
    if ($LASTEXITCODE -eq 0) {
        git checkout $Name
    } else {
        git checkout -b $Name
    }
}

function Run-CodexPrompt {
    param([string]$PromptPath)

    if (-not (Test-Path $PromptPath)) {
        Fail "Prompt file not found: $PromptPath"
    }

    $prompt = Get-Content $PromptPath -Raw
    if ([string]::IsNullOrWhiteSpace($prompt)) {
        Fail "Prompt file is empty: $PromptPath"
    }

    Info "Running Codex prompt $PromptPath"
    codex run --full-auto $prompt
    if ($LASTEXITCODE -ne 0) {
        Fail "Codex failed for prompt: $PromptPath"
    }
}

function Commit-IfChanges {
    param([string]$Message)

    $dirty = Get-UncommittedFiles
    if (-not $dirty -or $dirty.Count -eq 0) {
        Info "No changes to commit"
        return
    }

    git add -A
    git commit -m $Message
    if ($LASTEXITCODE -ne 0) {
        Fail "Git commit failed: $Message"
    }
}

function Check-AlembicSingleHead {
    Info "Checking Alembic head count"
    $output = & $PythonExe -m alembic heads 2>&1
    if ($LASTEXITCODE -ne 0) {
        Fail "Could not inspect Alembic heads.`n$output"
    }

    $headLines = @($output | Where-Object { $_ -match '^[0-9a-f_]+\s+\(head\)$|^[0-9a-f_]+.*\(head\)' })
    if ($headLines.Count -ne 1) {
        Fail ("Expected exactly one Alembic head. Output:`n" + ($output -join "`n"))
    }
}

$agents = @(
    @{
        Name = "agent-01-schema-enforcer"
        Prompt = "agents/01_schema_enforcer.md"
        Allowed = @(
            "app/models/event.py",
            "app/schema/event.py",
            "app/schema/__init__.py",
            "alembic/versions/",
            "tests/test_schema.py",
            "tests/test_migrations.py"
        )
        Tests = @(
            "$PythonExe -m pytest tests\test_schema.py tests\test_migrations.py -q"
        )
        CheckAlembic = $true
    },
    @{
        Name = "agent-02-state-deriver"
        Prompt = "agents/02_state_deriver.md"
        Allowed = @(
            "app/services/projections.py",
            "app/services/__init__.py",
            "tests/test_event_projection.py"
        )
        Tests = @(
            "$PythonExe -m pytest tests\test_event_projection.py -q"
        )
        CheckAlembic = $false
    },
    @{
        Name = "agent-03-event-builder"
        Prompt = "agents/03_event_builder.md"
        Allowed = @(
            "app/services/workflow.py",
            "app/services/__init__.py",
            "app/api/jobs.py",
            "app/api/deps.py",
            "tests/test_app.py"
        )
        Tests = @(
            "$PythonExe -m pytest tests\test_app.py -q"
        )
        CheckAlembic = $false
    },
    @{
        Name = "agent-04-test-guard"
        Prompt = "agents/04_test_guard.md"
        Allowed = @(
            "tests/test_event_projection.py",
            "tests/test_app.py",
            "tests/test_schema.py",
            "tests/test_migrations.py",
            "tests/support.py"
        )
        Tests = @(
            "$PythonExe -m pytest -q"
        )
        CheckAlembic = $true
    }
)

Ensure-Command git
Ensure-Command codex

if (-not (Test-Path $PythonExe)) {
    Fail "Python executable not found: $PythonExe"
}

$allowedDirtyAtStart = @()
if ($AllowDirtyPromptFilesOnly) {
    $allowedDirtyAtStart = @(
        "spec/core.md",
        "agents/01_schema_enforcer.md",
        "agents/02_state_deriver.md",
        "agents/03_event_builder.md",
        "agents/04_test_guard.md",
        "scripts/run_codex_milestone.ps1"
    )
}

Assert-CleanWorktree -AllowedDirty $allowedDirtyAtStart
Ensure-Branch -Name $Branch

Info "Installing project"
& $PythonExe -m pip install -e .
if ($LASTEXITCODE -ne 0) {
    Fail "Failed to install project"
}

foreach ($agent in $agents) {
    Info "Starting $($agent.Name)"

    Assert-CleanWorktree -AllowedDirty @()
    Run-CodexPrompt -PromptPath $agent.Prompt
    Assert-ChangedFilesWithinScope -AllowedPaths $agent.Allowed

    foreach ($testCmd in $agent.Tests) {
        Run-TestCommand -Cmd $testCmd
    }

    if ($agent.CheckAlembic) {
        Check-AlembicSingleHead
    }

    Commit-IfChanges -Message $agent.Name
}

Info "Running final full suite"
& $PythonExe -m pytest -q
if ($LASTEXITCODE -ne 0) {
    Fail "Final full test suite failed"
}

Info "Milestone completed successfully"
git log --oneline -n 5