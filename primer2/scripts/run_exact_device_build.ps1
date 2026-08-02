[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GwSh,

    [string]$Python = "python",

    [string]$EvidenceDir = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$primer2Root = Join-Path $repoRoot "primer2"
$gowinDir = Join-Path $primer2Root "gowin"
$runTcl = Join-Path $gowinDir "run.tcl"

if (-not (Test-Path -LiteralPath $GwSh -PathType Leaf)) {
    throw "gw_sh executable not found: $GwSh"
}
if (-not (Test-Path -LiteralPath $runTcl -PathType Leaf)) {
    throw "Primer #2 Gowin script not found: $runTcl"
}

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $EvidenceDir = Join-Path $primer2Root "local_evidence\exact-build-$stamp"
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
    $EvidenceDir = Join-Path $repoRoot $EvidenceDir
}
$EvidenceDir = [System.IO.Path]::GetFullPath($EvidenceDir)
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$buildLog = Join-Path $EvidenceDir "gowin-build.log"
$summaryPath = Join-Path $EvidenceDir "PRIMER2_EXACT_BUILD_SUMMARY.txt"
$gitGuardPath = Join-Path $EvidenceDir "git-guard.txt"
$reportExtractPath = Join-Path $EvidenceDir "report-extract.txt"

$sourceCommit = (& git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Unable to resolve Git HEAD"
}

& $Python (Join-Path $primer2Root "scripts\static_rtl_checks.py")
if ($LASTEXITCODE -ne 0) { throw "Primer #2 static RTL checks failed" }
& $Python (Join-Path $primer2Root "scripts\reference_checks.py")
if ($LASTEXITCODE -ne 0) { throw "Primer #2 reference checks failed" }

$buildExitCode = 99
Push-Location $gowinDir
try {
    & $GwSh $runTcl 2>&1 | Tee-Object -FilePath $buildLog
    $buildExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

$implDir = Join-Path $gowinDir "impl"
$bitstream = Join-Path $implDir "pnr\trinity_primer2.fs"
$bitstreamPresent = Test-Path -LiteralPath $bitstream -PathType Leaf
$bitstreamSha256 = "NOT_AVAILABLE"
if ($bitstreamPresent) {
    $bitstreamSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $bitstream).Hash.ToLowerInvariant()
}

$reportFiles = @()
if (Test-Path -LiteralPath $implDir -PathType Container) {
    $reportFiles = @(Get-ChildItem -LiteralPath $implDir -Recurse -File |
        Where-Object { $_.Extension -in @(".rpt", ".log", ".txt", ".html") })
}

$patterns = @(
    "WNS", "TNS", "setup", "hold", "utilization", "resource",
    "unconstrained", "unrouted", "multiple driver", "latch", "inferred clock",
    "timing met", "timing violation", "ERROR", "WARNING"
)
$reportExtract = @()
foreach ($report in $reportFiles) {
    $matches = Select-String -LiteralPath $report.FullName -Pattern $patterns -SimpleMatch -ErrorAction SilentlyContinue
    foreach ($match in $matches) {
        $relative = $report.FullName.Substring($repoRoot.Length).TrimStart('\')
        $reportExtract += "${relative}:$($match.LineNumber): $($match.Line.Trim())"
    }
}
$reportExtract | Set-Content -Encoding UTF8 -LiteralPath $reportExtractPath

$gitStatus = & git -C $repoRoot status --short
$gitStatusRc = $LASTEXITCODE
$workingDiffCheck = & git -C $repoRoot diff --check 2>&1
$workingDiffCheckRc = $LASTEXITCODE
$committedDiffCheck = & git -C $repoRoot diff --check `
    36822a09c234f509adfa5dace6aa05e4bbd40d54..HEAD -- `
    primer2 .github/workflows/primer2-rtl-verification.yml 2>&1
$committedDiffCheckRc = $LASTEXITCODE
$primer1Guard = & git -C $repoRoot diff --exit-code `
    c8135b5304c0318c7ec24787484dc8a4c4aa0278..HEAD -- `
    primer1/rtl primer1/tb primer1/scripts primer1/constraints `
    primer1/gowin/trinity_primer1.gprj 2>&1
$primer1GuardRc = $LASTEXITCODE

@(
    "source_commit=$sourceCommit",
    "build_exit_code=$buildExitCode",
    "git_status_rc=$gitStatusRc",
    "working_diff_check_rc=$workingDiffCheckRc",
    "committed_diff_check_rc=$committedDiffCheckRc",
    "primer1_protected_path_guard_rc=$primer1GuardRc",
    "",
    "git_status:",
    ($gitStatus -join [Environment]::NewLine),
    "",
    "working_git_diff_check:",
    ($workingDiffCheck -join [Environment]::NewLine),
    "",
    "committed_git_diff_check:",
    ($committedDiffCheck -join [Environment]::NewLine),
    "",
    "primer1_guard:",
    ($primer1Guard -join [Environment]::NewLine)
) | Set-Content -Encoding UTF8 -LiteralPath $gitGuardPath

$summary = @(
    "Primer #2 exact-device build evidence",
    "source_commit=$sourceCommit",
    "device=GW2A-LV18PG256C8/I7",
    "device_database=GW2A-18C / gw2a18c-011",
    "device_version=C",
    "clock_hz=27000000",
    "top=primer2_top",
    "gw_sh=$GwSh",
    "build_exit_code=$buildExitCode",
    "bitstream_present=$bitstreamPresent",
    "bitstream_path=$bitstream",
    "bitstream_sha256=$bitstreamSha256",
    "report_file_count=$($reportFiles.Count)",
    "working_diff_check_rc=$workingDiffCheckRc",
    "committed_diff_check_rc=$committedDiffCheckRc",
    "primer1_protected_path_guard_rc=$primer1GuardRc",
    "build_log=$buildLog",
    "report_extract=$reportExtractPath",
    "git_guard=$gitGuardPath"
)
$summary | Set-Content -Encoding UTF8 -LiteralPath $summaryPath
$summary | ForEach-Object { Write-Host $_ }

if ($buildExitCode -ne 0) {
    throw "Gowin build failed with exit code $buildExitCode. See $buildLog"
}
if (-not $bitstreamPresent) {
    throw "Gowin returned success but trinity_primer2.fs was not found"
}
if ($workingDiffCheckRc -ne 0 -or $committedDiffCheckRc -ne 0) {
    throw "git diff --check failed. See $gitGuardPath"
}
if ($primer1GuardRc -ne 0) {
    throw "Protected Primer #1 implementation paths differ from qualified source"
}

Write-Host "BUILD ARTIFACT GENERATED. Review report-extract.txt before claiming timing PASS."
