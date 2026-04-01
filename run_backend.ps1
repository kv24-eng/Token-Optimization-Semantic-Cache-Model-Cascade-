# Run Backend API Server
# This script starts the FastAPI backend on http://localhost:8000

Write-Host "================================" -ForegroundColor Cyan
Write-Host "  STARTING BACKEND API SERVER" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to backend directory
Set-Location backend

# Start the API server
Write-Host "Starting FastAPI server on http://localhost:8000" -ForegroundColor Green
Write-Host "Documentation available at http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
