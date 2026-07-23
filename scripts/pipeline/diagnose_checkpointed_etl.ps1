param(
  [string]$CheckpointDir = "data/checkpoints/etl_raw",
  [string]$UniverseManifest = "data/universe/universe_manifest.json",
  [string]$LogPattern = "logs/checkpointed_etl_fetch_*.out.log"
)

$ErrorActionPreference = "SilentlyContinue"

$processes = Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match "run_checkpointed_etl\.py" } |
  Select-Object ProcessId, CommandLine, CreationDate

if (-not $processes) {
  $processes = Get-Process python |
    Select-Object @{Name = "ProcessId"; Expression = { $_.Id } },
      @{Name = "CommandLine"; Expression = { "python process; command line unavailable in this shell" } },
      @{Name = "CreationDate"; Expression = { $_.StartTime } }
}

$supportedCount = $null
if (Test-Path $UniverseManifest) {
  $manifest = Get-Content $UniverseManifest -Raw | ConvertFrom-Json
  $supportedCount = $manifest.supportedCount
}

$batchFiles = @(Get-ChildItem "$CheckpointDir\batch_*.json" | Where-Object { $_.Name -notmatch "\.status\.json$" })
$completeBatches = 0
$partialBatches = 0
$attempted = 0
$processed = 0
$successful = 0
$failed = 0
$latestBatch = $null

foreach ($path in $batchFiles) {
  try {
    $statusPath = $path.FullName -replace "\.json$", ".status.json"
    $readPath = if (Test-Path $statusPath) { $statusPath } else { $path.FullName }
    $payload = Get-Content $readPath -Raw | ConvertFrom-Json
    $isComplete = $payload.status -eq "complete"
    if ($isComplete) {
      $completeBatches += 1
      $attempted += [int]$payload.attemptedTickers
    } else {
      $partialBatches += 1
    }
    $processed += [int]$payload.processedTickers
    $successful += [int]$payload.successfulTickers
    $failed += [int]$payload.failedTickers
    if (-not $latestBatch -or $path.LastWriteTime -gt $latestBatch.LastWriteTime) {
      $latestBatch = [pscustomobject]@{
        Path = $path.FullName
        LastWriteTime = $path.LastWriteTime
        Status = $payload.status
        StartOffset = $payload.startOffset
        EndOffsetExclusive = $payload.endOffsetExclusive
        ProcessedTickers = $payload.processedTickers
        SuccessfulTickers = $payload.successfulTickers
        FailedTickers = $payload.failedTickers
        MaxWorkers = $payload.maxWorkers
      }
    }
  } catch {
    $partialBatches += 1
  }
}

$latestLog = Get-ChildItem $LogPattern | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$latestLines = @()
if ($latestLog) {
  $latestLines = @(Get-Content $latestLog.FullName -Tail 8 | ForEach-Object { [string]$_ })
}

[pscustomobject]@{
  RunningProcesses = $processes
  SupportedUniverseCount = $supportedCount
  CheckpointDir = (Resolve-Path $CheckpointDir).Path
  BatchFiles = $batchFiles.Count
  CompleteBatches = $completeBatches
  PartialBatches = $partialBatches
  AttemptedTickersInCompleteBatches = $attempted
  ProcessedTickersIncludingPartial = $processed
  SuccessfulTickersIncludingPartial = $successful
  FailedTickersIncludingPartial = $failed
  LatestBatch = $latestBatch
  LatestLog = if ($latestLog) { $latestLog.FullName } else { $null }
  LatestLogLines = $latestLines
} | ConvertTo-Json -Depth 6
