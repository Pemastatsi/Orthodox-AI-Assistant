# Runbook: Local Smoke Test (run it on your own machine)

Status: Canonical
Date: 2026-06-14
Owner: anyone who wants to run the stack locally.

How to bring the whole app up on one machine and click around. Two paths: **WSL2** (closest to
CI; uses the `make` targets) and **native Windows** (PowerShell scripts). macOS/Linux users follow
the WSL2 commands directly (skip the `wsl` step).

## What you get

FastAPI backend (`:8000`) + Next.js web UI (`:3000`) + Postgres/Qdrant/Redis in Docker. Auth runs
in **dev mode** (no Clerk needed) and billing in **local mode** (no Stripe, no charges).

## Prerequisites

- **Docker Desktop** — installed and **running** (it provides `docker` + `docker compose`).
- **uv** — `irm https://astral.sh/uv/install.ps1 | iex` (Windows) or `curl -LsSf https://astral.sh/uv/install.sh | sh`. uv provisions Python 3.12 itself.
- **Node.js 20 + pnpm** — `nvm-windows` (`nvm install 20; nvm use 20`) then `corepack enable pnpm`.

For *real* question-answering you also need an **OpenAI** API key (embeddings) and an **Anthropic**
API key (A1 classification + A5 composition). Without them the app still runs and the deterministic
**safety gate** is testable — hard-trigger queries (e.g. self-harm phrasing) return the fixed safety
redirect with no LLM call.

---

## Path A — WSL2 / macOS / Linux (uses `make`)

On Windows, install WSL2 once (Administrator PowerShell, then reboot), then enable Docker Desktop's
WSL integration for your distro:

```powershell
wsl --install -d Ubuntu
```

Then in the Ubuntu (or macOS/Linux) shell, from the repo root:

```bash
make install          # uv sync + pnpm install
cp .env.example backend/.env
sed -i 's|^QDRANT_URL=.*|QDRANT_URL=http://localhost:6333|' backend/.env
printf 'NEXT_PUBLIC_AUTH_MODE=dev\nNEXT_PUBLIC_DEV_PRINCIPAL=tn_orthodoxethos:owner:usr_founder\nDEV_PRINCIPAL=tn_orthodoxethos:owner:usr_founder\n' > web/.env.local
make up && make migrate
python scripts/seed_beta_tenant.py --db-url postgresql://orthodox:orthodox@localhost:5432/orthodox \
    --clerk-org-id org_dev --clerk-user-id user_dev --email founder@example.com
make dev              # backend + web + worker
```

Open <http://localhost:3000>.

---

## Path B — Native Windows (PowerShell)

Two scripts do everything (run from the repo root). PowerShell blocks unsigned scripts by default,
so invoke them with `-ExecutionPolicy Bypass`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup-dev.ps1   # one-time: deps, .env, db, migrate, seed
powershell -ExecutionPolicy Bypass -File scripts\run-dev.ps1     # starts backend + web + worker (3 windows)
```

Open <http://localhost:3000>.

`setup-dev.ps1` writes `backend/.env` (with `QDRANT_URL=http://localhost:6333`) and `web/.env.local`
(dev auth + the `tn_orthodoxethos` owner principal), boots the databases, migrates, and seeds the
tenant/owner. `run-dev.ps1` opens three windows (backend, web, worker) — close them to stop.

---

## Try it

- **Without API keys:** open the chat and send a hard-trigger query (e.g. *"I want to hurt myself"*).
  You should get the fixed safety redirect — this exercises the safety gate with no LLM call. The
  admin pages at `/admin` (queries, flagged, corpus, audit) also load.
- **With API keys (real answers):** edit `backend/.env`, set `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`,
  restart the backend window. Then load a corpus:
  1. In `/admin` upload a born-digital PDF or `.txt` (scanned PDFs need Tesseract — skip for a smoke test).
  2. Wait for the ingest job, then **approve** chunks in `/admin/corpus`.
  3. Ask a question the corpus covers in the chat.

## Stop / reset

```powershell
docker compose -f infrastructure/docker-compose.yml down        # stop databases (keeps data)
docker compose -f infrastructure/docker-compose.yml down -v     # stop AND wipe data (fresh start)
```

## Troubleshooting

- **"Docker isn't running"** — start Docker Desktop, wait for the whale icon, re-run.
- **"running scripts is disabled"** — use the `-ExecutionPolicy Bypass` form above.
- **Web shows a Clerk/login error locally** — `web/.env.local` must contain `NEXT_PUBLIC_AUTH_MODE=dev`; restart `pnpm dev` after changing it.
- **Queries fail with a provider/503 error** — that's missing/invalid LLM keys in `backend/.env` (fine if you're only testing the safety gate).
- **"insufficient evidence" on every real question** — the corpus is empty or unapproved; approve chunks in `/admin/corpus`.
- **Port already in use (8000/3000/5432/6333/6379)** — stop the other process or change the port.
- **`docker compose` not found** — update Docker Desktop (Compose v2 ships with it); the v1 `docker-compose` binary is not used here.

## References

- `Makefile` — the `up` / `migrate` / `dev` targets Path A uses.
- `scripts/setup-dev.ps1`, `scripts/run-dev.ps1` — the Windows scripts.
- `scripts/seed_beta_tenant.py` — tenant/owner seeder.
- `docs/runbooks/private-beta-launch.md` — the production (deployed) beta, as opposed to this local smoke test.
