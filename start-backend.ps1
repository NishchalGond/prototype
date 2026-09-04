# Start the API against the local PostgreSQL database.
#
#   .\start-backend.ps1
#
# Runs against the local PostgreSQL instance (port 5432).
# Leave this window open. The server runs in it; closing it stops the backend.

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

if (-not $env:DATABASE_URL) {
    $envFile = Join-Path $PSScriptRoot ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match "^\s*DATABASE_URL\s*=\s*['`"]?([^'`"]+)['`"]?") {
                $env:DATABASE_URL = $matches[1].Trim()
            }
        }
    }
}
if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/datalink"
}
$env:APP_ENV = "development"
$env:PORT = "8001"

$keyFile = Join-Path $PSScriptRoot ".secret.local"
if (-not (Test-Path $keyFile)) {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    [Convert]::ToBase64String($bytes) | Out-File -FilePath $keyFile -Encoding utf8 -NoNewline
    Write-Host "Generated a SECRET_KEY in .secret.local (gitignored)." -ForegroundColor DarkGray
}
$env:SECRET_KEY = (Get-Content $keyFile -Raw).Trim()

Write-Host ""
Write-Host "  Database : Local PostgreSQL (datalink)" -ForegroundColor Cyan
Write-Host "  API      : http://127.0.0.1:$env:PORT" -ForegroundColor Cyan
Write-Host "  Frontend : run .\start-frontend.ps1 in a SECOND window" -ForegroundColor Cyan
Write-Host ""

python run.py
