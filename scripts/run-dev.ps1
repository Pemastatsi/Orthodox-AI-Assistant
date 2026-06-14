#Requires -Version 5.1
<#
.SYNOPSIS
  Start the Orthodox AI Assistant locally on Windows: backend API, web UI, and the
  retention worker, each in its own window. Run scripts\setup-dev.ps1 first.

.DESCRIPTION
  The Windows equivalent of `make dev`. PowerShell can't background processes like the
  bash Makefile does, so this opens three windows. Close them (or Ctrl+C in each) to stop.

.NOTES
  Run from the repo root, e.g.:
    powershell -ExecutionPolicy Bypass -File scripts\run-dev.ps1
#>
$ErrorActionPreference = "Stop"

$Root  = Split-Path $PSScriptRoot -Parent
$Shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }
$Backend = Join-Path $Root "backend"
$Web     = Join-Path $Root "web"

if (-not (Test-Path (Join-Path $Backend ".env"))) {
    Write-Host "backend/.env not found - run scripts\setup-dev.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Starting backend, web, and worker in separate windows..." -ForegroundColor Cyan
Start-Process $Shell -WorkingDirectory $Backend -ArgumentList '-NoExit','-Command','uv run uvicorn app.main:app --reload --port 8000'
Start-Process $Shell -WorkingDirectory $Web     -ArgumentList '-NoExit','-Command','pnpm dev'
Start-Process $Shell -WorkingDirectory $Backend -ArgumentList '-NoExit','-Command','uv run arq app.workers.retention_worker.WorkerSettings'

Write-Host ""
Write-Host "  Backend API : http://localhost:8000  (health: http://localhost:8000/health)" -ForegroundColor Green
Write-Host "  Web UI      : http://localhost:3000" -ForegroundColor Green
Write-Host "  Admin       : http://localhost:3000/admin" -ForegroundColor Green
Write-Host ""
Write-Host "Stop: close those three windows. Stop the databases with:" -ForegroundColor DarkGray
Write-Host "  docker compose -f infrastructure/docker-compose.yml down" -ForegroundColor DarkGray
