# Run Streamlit Frontend
# This script starts the Streamlit UI on http://localhost:8501

Write-Host "================================" -ForegroundColor Cyan
Write-Host "  STARTING STREAMLIT FRONTEND" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Make sure the backend API is running on http://localhost:8000" -ForegroundColor Yellow
Write-Host ""
Write-Host "Starting Streamlit on http://localhost:8501" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

streamlit run frontend/streamlit_app.py
