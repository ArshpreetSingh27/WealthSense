# Setup Windows Task Scheduler for Daily Shadow Trading Pipeline

$Action = New-ScheduledTaskAction -Execute 'C:\Users\arshp\AppData\Local\Programs\Python\Python313\python.exe' `
    -Argument 'c:\Users\arshp\OneDrive\Desktop\Stock_recommendation_system\data\scripts\run_daily_pipeline.py'

# Run daily at 4:00 PM (after market close)
$Trigger = New-ScheduledTaskTrigger -Daily -At 4:00PM

Register-ScheduledTask -Action $Action -Trigger $Trigger -TaskName "ShadowTradingPipeline" -Description "Daily Stock Recommendation Pipeline"

Write-Host "Successfully scheduled ShadowTradingPipeline for 4:00 PM daily."
