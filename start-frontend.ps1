# Start the dashboard.
#
#   .\start-frontend.ps1
#
# Run this in a SECOND window; the backend needs its own. Vite proxies /api to
# 127.0.0.1:8001, so this alone renders the login screen but cannot sign anyone
# in -- that is the "server is not responding" message.

# Vite logs to stderr; Stop would turn that into a fatal error.
$ErrorActionPreference = "Continue"
Set-Location -Path (Join-Path $PSScriptRoot "frontend")

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies (first run only)..." -ForegroundColor DarkGray
    npm install
}

Write-Host ""
Write-Host "  Dashboard : http://localhost:3000" -ForegroundColor Cyan
Write-Host "  API proxy : http://127.0.0.1:8001  (start-backend.ps1)" -ForegroundColor Cyan
Write-Host ""

npm run dev
