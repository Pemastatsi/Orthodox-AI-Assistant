#Requires -Version 5.1
<#
.SYNOPSIS
  One-shot local dev bootstrap for the Orthodox AI Assistant on Windows.

.DESCRIPTION
  The Windows equivalent of the Linux `make install && make up && make migrate` flow:
    * installs backend (uv) and web (pnpm) dependencies
    * writes backend/.env and web/.env.local for local dev
    * boots Postgres / Qdrant / Redis via Docker Compose
    * runs database migrations
    * seeds the dev tenant + owner (tn_orthodoxethos / usr_founder)
  When it finishes, run scripts\run-dev.ps1 to start the app.

.NOTES
  Prerequisites (the script checks and tells you which are missing):
    * Docker Desktop  - https://www.docker.com/products/docker-desktop/  (must be RUNNING)
    * uv              - https://astral.sh/uv   (irm https://astral.sh/uv/install.ps1 | iex)
    * Node.js 20      - nvm-windows: `nvm install 20; nvm use 20`
    * pnpm            - `corepack enable pnpm`

  Run from the repo root, e.g.:
    powershell -ExecutionPolicy Bypass -File scripts\setup-dev.ps1
#>
$ErrorActionPreference = "Stop"

function Test-Cmd($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }

$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
Write-Host "Repo root: $Root" -ForegroundColor DarkGray

# --- Preflight: required tools ----------------------------------------------
$missing = @()
if (-not (Test-Cmd docker)) { $missing += "docker  - install Docker Desktop and start it" }
if (-not (Test-Cmd uv))     { $missing += "uv      - irm https://astral.sh/uv/install.ps1 | iex" }
if (-not (Test-Cmd node))   { $missing += "node 20 - nvm-windows: nvm install 20; nvm use 20" }
if (-not (Test-Cmd pnpm))   { $missing += "pnpm    - corepack enable pnpm" }
if ($missing.Count -gt 0) {
    Write-Host "Missing prerequisites:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    throw "Install the items above, then re-run this script."
}

Write-Host "==> Checking Docker is running" -ForegroundColor Cyan
& docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop isn't running. Start it, wait for the whale icon, then re-run." }

# --- Backend + web dependencies ---------------------------------------------
Write-Host "==> Installing backend deps (uv sync)" -ForegroundColor Cyan
Push-Location backend; & uv sync; $code = $LASTEXITCODE; Pop-Location
if ($code -ne 0) { throw "uv sync failed (exit $code)" }

Write-Host "==> Installing web deps (pnpm install)" -ForegroundColor Cyan
Push-Location web
& pnpm install
if ($LASTEXITCODE -ne 0) {
    # Newer pnpm (10+) blocks dependency build scripts by default (ERR_PNPM_IGNORED_BUILDS).
    # Those builds aren't needed to run the dev server, so retry skipping them.
    Write-Host "    pnpm blocked dependency build scripts; retrying with --ignore-scripts (fine for local dev)..." -ForegroundColor Yellow
    & pnpm install --ignore-scripts
}
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { throw "pnpm install failed (exit $code)" }

# --- Env files (ascii = no BOM, which dotenv parsers dislike) ----------------
# Backend reads `.env` from its own working dir (uvicorn runs in backend/).
if (-not (Test-Path "backend/.env")) {
    Write-Host "==> Writing backend/.env" -ForegroundColor Cyan
    (Get-Content ".env.example") -replace '^QDRANT_URL=.*$', 'QDRANT_URL=http://localhost:6333' |
        Set-Content "backend/.env" -Encoding ascii
    Write-Host "    For real answers, edit backend/.env: set OPENAI_API_KEY + ANTHROPIC_API_KEY." -ForegroundColor Yellow
} else {
    Write-Host "==> backend/.env exists - leaving as-is (ensure QDRANT_URL=http://localhost:6333)" -ForegroundColor DarkGray
}

# Next.js reads `.env.local` from the web/ dir. Without NEXT_PUBLIC_AUTH_MODE=dev it
# defaults to Clerk mode and won't work locally. DEV_PRINCIPAL aligns chat + admin to the seeded owner.
if (-not (Test-Path "web/.env.local")) {
    Write-Host "==> Writing web/.env.local (dev auth + dev principal)" -ForegroundColor Cyan
    @(
        "NEXT_PUBLIC_AUTH_MODE=dev",
        "NEXT_PUBLIC_DEV_PRINCIPAL=tn_orthodoxethos:owner:usr_founder",
        "DEV_PRINCIPAL=tn_orthodoxethos:owner:usr_founder"
    ) | Set-Content "web/.env.local" -Encoding ascii
} else {
    Write-Host "==> web/.env.local exists - leaving as-is" -ForegroundColor DarkGray
}

# --- Infrastructure ----------------------------------------------------------
Write-Host "==> Starting Postgres / Qdrant / Redis (docker compose up -d)" -ForegroundColor Cyan
& docker compose -f infrastructure/docker-compose.yml up -d
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed (exit $LASTEXITCODE)" }

Write-Host "==> Waiting for Postgres to accept connections" -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    & docker compose -f infrastructure/docker-compose.yml exec -T postgres pg_isready -U orthodox -d orthodox *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { throw "Postgres did not become ready within ~60s. Check 'docker compose -f infrastructure/docker-compose.yml logs postgres'." }

# --- Migrate + seed ----------------------------------------------------------
Write-Host "==> Applying migrations (alembic upgrade head)" -ForegroundColor Cyan
Push-Location backend; & uv run alembic upgrade head; $code = $LASTEXITCODE; Pop-Location
if ($code -ne 0) { throw "alembic upgrade failed (exit $code)" }

Write-Host "==> Seeding dev tenant + owner (tn_orthodoxethos / usr_founder)" -ForegroundColor Cyan
Push-Location backend
& uv run python ../scripts/seed_beta_tenant.py --db-url "postgresql://orthodox:orthodox@localhost:5432/orthodox" --clerk-org-id "org_dev" --clerk-user-id "user_dev" --email "founder@example.com"
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { throw "seed_beta_tenant failed (exit $code)" }

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next:  powershell -ExecutionPolicy Bypass -File scripts\run-dev.ps1" -ForegroundColor Green
Write-Host "Then open http://localhost:3000  (admin: http://localhost:3000/admin)" -ForegroundColor Green
Write-Host "No API keys? The safety gate still works. Real answers need OPENAI/ANTHROPIC keys in backend/.env + an approved corpus." -ForegroundColor DarkGray
