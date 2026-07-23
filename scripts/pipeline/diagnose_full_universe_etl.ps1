param(
  [int]$ProcessIdToCheck = 14524,
  [string]$RunStamp = "20260721-150552",
  [switch]$Json
)

$ErrorActionPreference = "SilentlyContinue"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$logPrefix = Join-Path $repoRoot "logs\manual_all_etl_$RunStamp"
$stdoutPath = "$logPrefix.out.log"
$stderrPath = "$logPrefix.err.log"

function Convert-BytesToMB($value) {
  if ($null -eq $value) { return $null }
  return [math]::Round([double]$value / 1MB, 1)
}

function Read-JsonFile($path) {
  if (-not (Test-Path $path)) { return $null }
  try { return Get-Content -LiteralPath $path -Raw | ConvertFrom-Json } catch { return $null }
}

function Get-FileSummary($relativePath) {
  $path = Join-Path $repoRoot $relativePath
  if (-not (Test-Path $path)) {
    return [pscustomobject]@{ path = $relativePath; exists = $false; bytes = $null; lastWriteTime = $null }
  }
  $item = Get-Item -LiteralPath $path
  return [pscustomobject]@{
    path = $relativePath
    exists = $true
    bytes = $item.Length
    lastWriteTime = $item.LastWriteTime.ToString("s")
  }
}

$proc = Get-Process -Id $ProcessIdToCheck
$processSummary = if ($proc) {
  $elapsed = (Get-Date) - $proc.StartTime
  [pscustomobject]@{
    running = $true
    id = $proc.Id
    startTime = $proc.StartTime.ToString("s")
    elapsedMinutes = [math]::Round($elapsed.TotalMinutes, 1)
    cpuSeconds = [math]::Round($proc.CPU, 1)
    workingSetMB = Convert-BytesToMB $proc.WorkingSet64
  }
} else {
  [pscustomobject]@{
    running = $false
    id = $ProcessIdToCheck
    startTime = $null
    elapsedMinutes = $null
    cpuSeconds = $null
    workingSetMB = $null
  }
}

$stderrTail = if (Test-Path $stderrPath) { @(Get-Content -LiteralPath $stderrPath -Tail 40) } else { @() }
$stdoutTail = if (Test-Path $stdoutPath) { @(Get-Content -LiteralPath $stdoutPath -Tail 40) } else { @() }

$manifest = Read-JsonFile (Join-Path $repoRoot "data\universe\universe_manifest.json")
$etlReport = Read-JsonFile (Join-Path $repoRoot "public\data\etl_report.json")
$coverage = Read-JsonFile (Join-Path $repoRoot "public\data\universe_coverage_report.json")
$stockFiles = @(Get-ChildItem -LiteralPath (Join-Path $repoRoot "public\data\stocks") -Filter "*.json" | Where-Object { $_.Name -ne "summary.json" })

$requestedTickers = $etlReport.requestedTickers
$successfulTickers = $etlReport.successfulTickers
$fullUniverseComplete = $false
if ($null -ne $requestedTickers -and [int]$requestedTickers -ge 6000) { $fullUniverseComplete = $true }
if ($null -ne $successfulTickers -and [int]$successfulTickers -ge 5000) { $fullUniverseComplete = $true }

$recommendedNextStep = if ($processSummary.running) {
  "ETL is still running. Do not start BM25/forecast/build/deploy yet."
} elseif ($fullUniverseComplete) {
  "ETL appears to have written full-universe artifacts. Continue with BM25, forecasts, audits, build, commit, push, deploy."
} elseif ($stderrTail.Count -gt 0) {
  "ETL is not running and stderr has output. Inspect stderr before deciding whether to restart or implement checkpointed ETL."
} else {
  "ETL is not running, but public artifacts still look like the older capped run. Treat the full-universe attempt as incomplete."
}

$diagnostic = [pscustomobject]@{
  checkedAt = (Get-Date).ToString("s")
  repoRoot = $repoRoot.Path
  runStamp = $RunStamp
  process = $processSummary
  logs = [pscustomobject]@{
    stdout = Get-FileSummary ("logs\manual_all_etl_$RunStamp.out.log")
    stderr = Get-FileSummary ("logs\manual_all_etl_$RunStamp.err.log")
    stderrTail = $stderrTail
    stdoutTail = $stdoutTail
  }
  universeManifest = if ($manifest) {
    [pscustomobject]@{
      createdAt = $manifest.createdAt
      universeMode = $manifest.universeMode
      requestedLimit = $manifest.requestedLimit
      companyCount = $manifest.companyCount
      supportedCount = $manifest.supportedCount
      unsupportedCount = $manifest.unsupportedCount
    }
  } else { $null }
  currentPublicEtlReport = if ($etlReport) {
    [pscustomobject]@{
      status = $etlReport.status
      runFinishedAt = $etlReport.runFinishedAt
      requestedTickers = $etlReport.requestedTickers
      successfulTickers = $etlReport.successfulTickers
      failedTickers = $etlReport.failedTickers
    }
  } else { $null }
  coverageCounts = $coverage.counts
  generatedStockDetailFileCount = $stockFiles.Count
  keyArtifacts = @(
    Get-FileSummary "public\data\dashboard.json"
    Get-FileSummary "public\data\features.json"
    Get-FileSummary "public\data\signals.json"
    Get-FileSummary "public\data\etl_report.json"
    Get-FileSummary "public\data\universe_coverage_report.json"
    Get-FileSummary "public\data\stocks\summary.json"
    Get-FileSummary "public\data\search_index.json"
    Get-FileSummary "public\data\forecasts\summary.json"
  )
  fullUniverseArtifactsLikelyWritten = $fullUniverseComplete
  recommendedNextStep = $recommendedNextStep
}

if ($Json) {
  $diagnostic | ConvertTo-Json -Depth 8
} else {
  Write-Host "ValueSignal full-universe ETL diagnostic" -ForegroundColor Cyan
  Write-Host "Checked: $($diagnostic.checkedAt)"
  Write-Host "Process running: $($processSummary.running)"
  if ($processSummary.running) {
    Write-Host "PID: $($processSummary.id), elapsed minutes: $($processSummary.elapsedMinutes), CPU seconds: $($processSummary.cpuSeconds), memory MB: $($processSummary.workingSetMB)"
  }
  Write-Host "Universe supported count: $($diagnostic.universeManifest.supportedCount)"
  Write-Host "Current public ETL requested/success/failed: $($diagnostic.currentPublicEtlReport.requestedTickers) / $($diagnostic.currentPublicEtlReport.successfulTickers) / $($diagnostic.currentPublicEtlReport.failedTickers)"
  Write-Host "Generated stock detail files: $($diagnostic.generatedStockDetailFileCount)"
  Write-Host "Full-universe artifacts likely written: $($diagnostic.fullUniverseArtifactsLikelyWritten)"
  Write-Host "Recommended next step: $recommendedNextStep" -ForegroundColor Yellow
  if ($stderrTail.Count -gt 0) {
    Write-Host ""
    Write-Host "stderr tail:" -ForegroundColor Red
    $stderrTail | ForEach-Object { Write-Host $_ }
  }
}
