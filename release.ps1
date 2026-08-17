param(
    [Parameter(Position = 0)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "Git command failed: git $($GitArgs -join ' ')" }
}

function Invoke-Poetry {
    param([Parameter(Mandatory = $true)][string[]]$PoetryArgs)
    if (Get-Command poetry -ErrorAction SilentlyContinue) {
        & poetry @PoetryArgs
    } elseif (Test-Path ".venv\Scripts\python.exe") {
        & ".venv\Scripts\python.exe" -m poetry @PoetryArgs
    } else {
        throw "Poetry is not installed. Run: pipx install poetry"
    }
    if ($LASTEXITCODE -ne 0) { throw "Poetry command failed: poetry $($PoetryArgs -join ' ')" }
}

try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git is not installed or is not available in PATH."
    }
    if (-not (Test-Path "version.py") -or -not (Test-Path "pyproject.toml")) {
        throw "version.py or pyproject.toml was not found in $PSScriptRoot."
    }

    $versionSource = [IO.File]::ReadAllText((Join-Path $PSScriptRoot "version.py"))
    $currentVersion = [regex]::Match($versionSource, '__version__\s*=\s*"([^"]+)"').Groups[1].Value
    if (-not $currentVersion) { throw "Could not read the current version from version.py." }

    if (-not $Version) { $Version = Read-Host "New version (current: $currentVersion)" }
    $Version = $Version.Trim()
    if ($Version -notmatch '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$') {
        throw "Version must use MAJOR.MINOR.PATCH format, for example 2.0.5."
    }
    if ($Version -eq $currentVersion) { throw "Version $Version is already set. Specify a new version." }

    $status = git status --porcelain
    if ($LASTEXITCODE -ne 0) { throw "Could not read Git status." }
    if ($status) {
        git status --short
        throw "Working tree is not clean. Commit or stash changes before creating a release."
    }

    $branch = (git branch --show-current).Trim()
    if ($branch -ne "master") { throw "Releases must be created from master. Current branch: $branch" }

    $remotes = @(git remote)
    if (-not $remotes) { throw "No Git remote is configured." }
    $remote = if ($remotes -contains "origin") { "origin" } else { $remotes[0].Trim() }
    $tag = "v$Version"

    Write-Host "Synchronizing $remote/$branch..." -ForegroundColor Cyan
    Invoke-Git -GitArgs @("fetch", $remote, $branch)
    $localHead = (git rev-parse "HEAD").Trim()
    $remoteHead = (git rev-parse "$remote/$branch").Trim()
    $mergeBase = (git merge-base "HEAD" "$remote/$branch").Trim()
    if ($localHead -eq $mergeBase -and $localHead -ne $remoteHead) {
        Invoke-Git -GitArgs @("merge", "--ff-only", "$remote/$branch")
    } elseif ($remoteHead -ne $mergeBase) {
        throw "Local $branch and $remote/$branch have diverged. Rebase or merge them before creating a release."
    }

    if (git tag --list $tag) { throw "Local tag $tag already exists." }
    $remoteTag = git ls-remote --tags $remote "refs/tags/$tag"
    if ($LASTEXITCODE -ne 0) { throw "Could not check tag $tag on remote $remote." }
    if ($remoteTag) { throw "Remote tag $tag already exists." }

    Write-Host "Checking Poetry configuration..." -ForegroundColor Cyan
    Invoke-Poetry -PoetryArgs @("check", "--lock")

    Write-Host "Updating version: $currentVersion -> $Version" -ForegroundColor Cyan
    Invoke-Poetry -PoetryArgs @("version", $Version)

    $utf8NoBom = [Text.UTF8Encoding]::new($false)
    $versionSource = [regex]::Replace(
        $versionSource,
        '__version__\s*=\s*"[^"]+"',
        "__version__ = `"$Version`""
    )
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot "version.py"), $versionSource, $utf8NoBom)

    Invoke-Poetry -PoetryArgs @("lock")
    Invoke-Poetry -PoetryArgs @("check", "--lock")

    $testFiles = @(Get-ChildItem -Path "tests" -Recurse -Filter "test_*.py" -ErrorAction SilentlyContinue)
    if ($testFiles.Count -gt 0) {
        Write-Host "Running tests..." -ForegroundColor Cyan
        Invoke-Poetry -PoetryArgs @("run", "pytest", "-q", "-p", "no:cacheprovider")
    } else {
        Write-Host "No tests found; skipping pytest." -ForegroundColor Yellow
    }

    Invoke-Git -GitArgs @("add", "version.py", "pyproject.toml", "poetry.lock")
    Invoke-Git -GitArgs @("commit", "-m", "release: $Version")
    # A changelog workflow may update master while checks are running.
    Invoke-Git -GitArgs @("fetch", $remote, $branch)
    Invoke-Git -GitArgs @("rebase", "$remote/$branch")
    Invoke-Git -GitArgs @("push", $remote, $branch)
    Invoke-Git -GitArgs @("tag", "-a", $tag, "-m", "Release $Version")
    Invoke-Git -GitArgs @("push", $remote, $tag)

    Write-Host ""
    Write-Host "Release $Version started successfully." -ForegroundColor Green
    Write-Host "GitHub Actions will build dist\main.exe and publish the release." -ForegroundColor Green
    Write-Host "Actions: https://github.com/vanitoo/pythonProject-OpenCV-PDF/actions" -ForegroundColor Cyan
    Write-Host "Releases: https://github.com/vanitoo/pythonProject-OpenCV-PDF/releases" -ForegroundColor Cyan
    Write-Host "Build releases: https://github.com/vanitoo/pythonProject-OpenCV-PDF-Build/releases" -ForegroundColor Cyan
}
catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Release stopped. Check git status and tags before retrying." -ForegroundColor Yellow
    exit 1
}
