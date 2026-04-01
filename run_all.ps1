# Run Both Backend and Frontend
# This script starts both servers in the background

Write-Host "================================" -ForegroundColor Cyan
Write-Host "  STARTING FULL APPLICATION" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check if backend is already running
$backendCheck = Test-NetConnection -ComputerName localhost -Port 8000 -InformationLevel Quiet
if ($backendCheck) {
    Write-Host "⚠️  Port 8000 already in use (backend might be running)" -ForegroundColor Yellow
} else {
    Write-Host "✅ Port 8000 available" -ForegroundColor Green
}

# Start Backend in background job
Write-Host ""
Write-Host "Starting Backend API..." -ForegroundColor Green
$backendJob = Start-Job -ScriptBlock {
    Set-Location $args[0]
    Set-Location backend
    python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
} -ArgumentList (Get-Location)

Write-Host "   Job ID: $($backendJob.Id)" -ForegroundColor Gray
Write-Host "   API: http://localhost:8000" -ForegroundColor Gray
Write-Host "   Docs: http://localhost:8000/docs" -ForegroundColor Gray

# Wait a few seconds for backend to start
Write-Host ""
Write-Host "Waiting for backend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Start Frontend in background job
Write-Host ""
Write-Host "Starting Streamlit Frontend..." -ForegroundColor Green
$frontendJob = Start-Job -ScriptBlock {
    Set-Location $args[0]
    streamlit run frontend/streamlit_app.py
} -ArgumentList (Get-Location)

Write-Host "   Job ID: $($frontendJob.Id)" -ForegroundColor Gray
Write-Host "   UI: http://localhost:8501" -ForegroundColor Gray

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "  APPLICATION RUNNING" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend API:  http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend UI:  http://localhost:8501" -ForegroundColor Green
Write-Host "API Docs:     http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "To stop all services, run: Stop-Job -Job $($backendJob.Id), $($frontendJob.Id) | Stop-Job" -ForegroundColor Yellow
Write-Host ""
Write-Host "View logs:" -ForegroundColor Cyan
Write-Host "  Backend:  Receive-Job -Job $($backendJob.Id) -Keep" -ForegroundColor Gray
Write-Host "  Frontend: Receive-Job -Job $($frontendJob.Id) -Keep" -ForegroundColor Gray
Write-Host ""

# Keep this script running and show status
while ($true) {
    Start-Sleep -Seconds 10
    
    $backendState = (Get-Job -Id $backendJob.Id).State
    $frontendState = (Get-Job -Id $frontendJob.Id).State
    
    if ($backendState -ne "Running" -or $frontendState -ne "Running") {
        Write-Host ""
        Write-Host "⚠️  A service stopped!" -ForegroundColor Red
        Write-Host "Backend: $backendState | Frontend: $frontendState" -ForegroundColor Red
        break
    }
}
