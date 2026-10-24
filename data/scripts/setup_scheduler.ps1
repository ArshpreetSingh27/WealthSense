# Schedule the read-only market refresh. Legacy shared paper trading stays paused.

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Python = (Get-Command python -ErrorAction Stop).Source
$Script = Join-Path $PSScriptRoot 'run_market_pipeline.py'
$Action = New-ScheduledTaskAction -Execute $Python -Argument ('"' + $Script + '"') -WorkingDirectory $ProjectRoot

# Run daily at 4:00 PM (after market close)
$Trigger = New-ScheduledTaskTrigger -Daily -At 4:00PM
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -Action $Action -Trigger $Trigger -Settings $Settings -TaskName "MarketDataPipeline" -Description "Daily market research refresh and opted-in paper bots" -Force | Out-Null
$OldTask = Get-ScheduledTask -TaskName "ShadowTradingPipeline" -ErrorAction SilentlyContinue
if ($OldTask) {
    Disable-ScheduledTask -TaskName "ShadowTradingPipeline" | Out-Null
}

Write-Host "Scheduled MarketDataPipeline for 4:00 PM daily; legacy paper task disabled."
