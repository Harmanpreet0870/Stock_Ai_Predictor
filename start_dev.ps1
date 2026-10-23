# ── Stock AI Predictor — Dev Startup ──────────────────────────────
# Run from project root: .\start_dev.ps1

$root = $PSScriptRoot

# Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$root\Backend'; python -m uvicorn main:app --reload --port 8000" `
    -WindowStyle Normal

Start-Sleep -Seconds 2

# Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$root\Frontend'; npm run dev" `
    -WindowStyle Normal

Write-Host ""
Write-Host "  Backend  → http://localhost:8000"
Write-Host "  Frontend → http://localhost:5173"
Write-Host "  API Docs → http://localhost:8000/docs"
Write-Host ""
