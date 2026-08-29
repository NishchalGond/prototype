# Start the API against the local SQLite database.
#
#   .\start-backend.ps1
#
# Exists because the settings live in environment variables that only last as
# long as the window that set them. Forgetting them is silent: the app falls
# back to the Supabase URL in .env, your local accounts are not there, and the
# login fails for a reason the screen cannot explain.
#
# Leave this window open. The server runs in it; closing it stops the backend.

# NOT "Stop": alembic and uvicorn log to stderr, and with Stop in force
# PowerShell promotes a native command's stderr line to a terminating error --
# so the script dies on the first INFO message and the server never binds.
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

$env:DATABASE_URL = "sqlite:///./local.db"
$env:APP_ENV = "development"
$env:PORT = "8001"

# Without a stable key every restart invalidates existing sessions, so you get
# signed out on each restart -- which looks like broken login but is not.
# Generated once and kept in .secret.local, which is gitignored.
$keyFile = Join-Path $PSScriptRoot ".secret.local"
if (-not (Test-Path $keyFile)) {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    [Convert]::ToBase64String($bytes) | Out-File -FilePath $keyFile -Encoding utf8 -NoNewline
    Write-Host "Generated a SECRET_KEY in .secret.local (gitignored)." -ForegroundColor DarkGray
}
$env:SECRET_KEY = (Get-Content $keyFile -Raw).Trim()

Write-Host ""
Write-Host "  Database : $env:DATABASE_URL" -ForegroundColor Cyan
Write-Host "  API      : http://127.0.0.1:$env:PORT" -ForegroundColor Cyan
Write-Host "  Frontend : run .\start-frontend.ps1 in a SECOND window" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Look for 'database ready: sqlite' below. If it says postgresql," -ForegroundColor DarkGray
Write-Host "  something overrode DATABASE_URL and your accounts will not be found." -ForegroundColor DarkGray
Write-Host ""

python run.py
